"""Pluggable model backends for the evaluation harness.

Two backends are supported, both behind the same ``ModelClient`` interface:

- ``AnthropicClient``    — frontier Claude models via the Anthropic SDK.
- ``OpenAICompatClient`` — any server exposing the OpenAI ``/v1/chat/completions``
  schema. This covers the realistic local-hosting stack: vLLM, Ollama,
  LM Studio, TGI, llama.cpp's server, plus aggregators like OpenRouter and
  Together. Point ``base_url`` at the server and you can evaluate a local 14B /
  32B / 70B exactly as you would a hosted model.

The OpenAI-compatible client is implemented directly on ``httpx`` so the harness
adds no new dependency (the backend already vendors ``anthropic`` and ``httpx``).
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass

import httpx

# Mirror the production generator (BaseGenerator.MAX_CONTINUATION_ROUNDS): when a
# model truncates at its max_tokens budget, resume the response up to this many
# times. Keeping this in lockstep with production means the eval measures the
# same behavior the live pipeline exhibits — truncation is handled, not scored
# as model failure.
MAX_CONTINUATION_ROUNDS = 4

# Resume instruction (matches BaseGenerator._CONTINUE_INSTRUCTION). The partial
# output is replayed as a prior assistant turn and the model is asked to emit
# only the remainder, which is concatenated. This avoids assistant-message
# prefill, which current Claude models reject.
_CONTINUE_INSTRUCTION = (
    "Your previous response was cut off because it hit the length limit. "
    "Continue the JSON output from exactly where you stopped. Output only the "
    "remaining characters — do not repeat any prior content and do not wrap the "
    "output in markdown fences."
)


@dataclass
class CompletionResult:
    """Outcome of a completion (possibly spanning several continuation calls),
    with the telemetry the harness scores on. ``text`` is the concatenated whole;
    ``latency_s`` and token counts are summed across continuation rounds."""

    text: str
    input_tokens: int | None
    output_tokens: int | None
    latency_s: float
    error: str | None = None
    continuation_rounds: int = 0


class ModelClient(ABC):
    """A model backend. One instance corresponds to one model under test."""

    #: Human-readable label used in reports (e.g. "qwen2.5-72b-instruct").
    label: str
    #: Free-text tier annotation surfaced in reports (e.g. "70B-local", "frontier").
    tier: str

    @abstractmethod
    async def complete(
        self, *, system_prompt: str, user_prompt: str, max_tokens: int
    ) -> CompletionResult:
        """Run one completion. Never raises for model/transport errors —
        failures are returned as a ``CompletionResult`` with ``error`` set so a
        single dead endpoint cannot abort an entire sweep."""
        ...

    async def aclose(self) -> None:
        """Release any held resources. Safe to call multiple times."""
        return None


class AnthropicClient(ModelClient):
    """Frontier Claude models via the Anthropic Messages API."""

    def __init__(
        self,
        *,
        model_id: str,
        api_key: str,
        label: str | None = None,
        tier: str = "frontier",
        timeout_s: float = 600.0,
        temperature: float = 0.0,
        max_tokens_cap: int | None = None,
    ) -> None:
        # Imported lazily so the harness loads even if the SDK is absent.
        import anthropic

        self._model_id = model_id
        self._client = anthropic.AsyncAnthropic(api_key=api_key, timeout=timeout_s)
        self._temperature = temperature
        self._max_tokens_cap = max_tokens_cap
        self.label = label or model_id
        self.tier = tier

    async def complete(
        self, *, system_prompt: str, user_prompt: str, max_tokens: int
    ) -> CompletionResult:
        from anthropic.types import TextBlock

        if self._max_tokens_cap:
            max_tokens = min(max_tokens, self._max_tokens_cap)
        accumulated = ""
        in_tok = 0
        out_tok = 0
        start = time.monotonic()

        for round_index in range(MAX_CONTINUATION_ROUNDS + 1):
            if accumulated:
                messages = [
                    {"role": "user", "content": user_prompt},
                    {"role": "assistant", "content": accumulated},
                    {"role": "user", "content": _CONTINUE_INSTRUCTION},
                ]
            else:
                messages = [{"role": "user", "content": user_prompt}]
            try:
                resp = await self._client.messages.create(
                    model=self._model_id,
                    max_tokens=max_tokens,
                    temperature=self._temperature,
                    system=system_prompt,
                    messages=messages,
                )
            except Exception as exc:  # noqa: BLE001 — endpoint failures are data, not crashes
                return CompletionResult(
                    text=accumulated,
                    input_tokens=in_tok or None,
                    output_tokens=out_tok or None,
                    latency_s=time.monotonic() - start,
                    error=f"{type(exc).__name__}: {exc}",
                    continuation_rounds=round_index,
                )
            block = resp.content[0] if resp.content else None
            accumulated += block.text if isinstance(block, TextBlock) else ""
            in_tok += getattr(resp.usage, "input_tokens", 0) or 0
            out_tok += getattr(resp.usage, "output_tokens", 0) or 0
            if getattr(resp, "stop_reason", None) != "max_tokens":
                return CompletionResult(
                    text=accumulated,
                    input_tokens=in_tok or None,
                    output_tokens=out_tok or None,
                    latency_s=time.monotonic() - start,
                    continuation_rounds=round_index,
                )
            accumulated = accumulated.rstrip()

        # Still truncated after the budget — return what we have, flagged.
        return CompletionResult(
            text=accumulated,
            input_tokens=in_tok or None,
            output_tokens=out_tok or None,
            latency_s=time.monotonic() - start,
            error=f"still truncated after {MAX_CONTINUATION_ROUNDS} continuations",
            continuation_rounds=MAX_CONTINUATION_ROUNDS,
        )

    async def aclose(self) -> None:
        await self._client.close()


class OpenAICompatClient(ModelClient):
    """Any OpenAI ``/v1/chat/completions``-compatible server.

    For local models set ``base_url`` to the server root including ``/v1``:
      - vLLM:      http://localhost:8000/v1
      - Ollama:    http://localhost:11434/v1
      - LM Studio: http://localhost:1234/v1
      - TGI:       http://localhost:8080/v1
    ``api_key`` may be a dummy string for local servers that ignore it.
    """

    def __init__(
        self,
        *,
        model_id: str,
        base_url: str,
        api_key: str = "not-needed",
        label: str | None = None,
        tier: str = "local",
        timeout_s: float = 600.0,
        temperature: float = 0.0,
        max_tokens_cap: int | None = None,
    ) -> None:
        self._model_id = model_id
        self._base_url = base_url.rstrip("/")
        self._temperature = temperature
        self._max_tokens_cap = max_tokens_cap
        self._client = httpx.AsyncClient(
            timeout=timeout_s,
            headers={"Authorization": f"Bearer {api_key}"},
        )
        self.label = label or model_id
        self.tier = tier

    async def complete(
        self, *, system_prompt: str, user_prompt: str, max_tokens: int
    ) -> CompletionResult:
        if self._max_tokens_cap:
            max_tokens = min(max_tokens, self._max_tokens_cap)
        accumulated = ""
        in_tok = 0
        out_tok = 0
        start = time.monotonic()

        for round_index in range(MAX_CONTINUATION_ROUNDS + 1):
            messages = [{"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}]
            if accumulated:
                # Replay the partial output and ask the model to continue (the
                # request must end with a user message).
                messages.append({"role": "assistant", "content": accumulated})
                messages.append({"role": "user", "content": _CONTINUE_INSTRUCTION})
            payload = {
                "model": self._model_id,
                "max_tokens": max_tokens,
                "temperature": self._temperature,
                "messages": messages,
            }
            try:
                resp = await self._client.post(
                    f"{self._base_url}/chat/completions", json=payload
                )
                resp.raise_for_status()
                data = resp.json()
            except Exception as exc:  # noqa: BLE001 — endpoint failures are data, not crashes
                return CompletionResult(
                    text=accumulated,
                    input_tokens=in_tok or None,
                    output_tokens=out_tok or None,
                    latency_s=time.monotonic() - start,
                    error=f"{type(exc).__name__}: {exc}",
                    continuation_rounds=round_index,
                )
            try:
                choice = data["choices"][0]
                accumulated += choice["message"]["content"] or ""
                finish_reason = choice.get("finish_reason")
            except (KeyError, IndexError, TypeError):
                return CompletionResult(
                    text=accumulated,
                    input_tokens=in_tok or None,
                    output_tokens=out_tok or None,
                    latency_s=time.monotonic() - start,
                    error=f"unexpected response shape: {str(data)[:300]}",
                    continuation_rounds=round_index,
                )
            usage = data.get("usage") or {}
            in_tok += usage.get("prompt_tokens") or 0
            out_tok += usage.get("completion_tokens") or 0
            # OpenAI schema reports truncation as finish_reason == "length".
            if finish_reason != "length":
                return CompletionResult(
                    text=accumulated,
                    input_tokens=in_tok or None,
                    output_tokens=out_tok or None,
                    latency_s=time.monotonic() - start,
                    continuation_rounds=round_index,
                )
            accumulated = accumulated.rstrip()

        return CompletionResult(
            text=accumulated,
            input_tokens=in_tok or None,
            output_tokens=out_tok or None,
            latency_s=time.monotonic() - start,
            error=f"still truncated after {MAX_CONTINUATION_ROUNDS} continuations",
            continuation_rounds=MAX_CONTINUATION_ROUNDS,
        )

    async def aclose(self) -> None:
        await self._client.aclose()


def build_client(spec: dict, *, anthropic_api_key: str) -> ModelClient:
    """Construct a ``ModelClient`` from a roster entry (see models.example.yaml).

    Required keys: ``provider`` ("anthropic" | "openai_compat") and ``model_id``.
    Optional: ``label``, ``tier``, ``base_url`` (openai_compat only),
    ``api_key`` (openai_compat only), ``temperature``.
    """
    provider = spec.get("provider")
    model_id = spec.get("model_id")
    if not model_id:
        raise ValueError(f"roster entry missing 'model_id': {spec}")

    if provider == "anthropic":
        return AnthropicClient(
            model_id=model_id,
            api_key=anthropic_api_key,
            label=spec.get("label"),
            tier=spec.get("tier", "frontier"),
            temperature=spec.get("temperature", 0.0),
            max_tokens_cap=spec.get("max_tokens_cap"),
        )
    if provider == "openai_compat":
        base_url = spec.get("base_url")
        if not base_url:
            raise ValueError(
                f"openai_compat entry '{model_id}' requires 'base_url'"
            )
        return OpenAICompatClient(
            model_id=model_id,
            base_url=base_url,
            api_key=spec.get("api_key", "not-needed"),
            label=spec.get("label"),
            tier=spec.get("tier", "local"),
            temperature=spec.get("temperature", 0.0),
            max_tokens_cap=spec.get("max_tokens_cap"),
        )
    raise ValueError(
        f"unknown provider '{provider}' (expected 'anthropic' or 'openai_compat')"
    )
