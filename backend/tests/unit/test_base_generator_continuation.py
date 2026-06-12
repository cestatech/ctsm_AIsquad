"""Unit tests for _call_claude continuation on max_tokens truncation.

These guard the fix for outputs that exceed a single max_tokens window: the
generator must resume the truncated response and return the concatenated whole,
rather than handing a partial (unparseable) JSON blob to the parser.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.generators.base_generator import BaseGenerator
from app.services.generators.sap_generator import SAPGenerator


def _response(text: str, stop_reason: str) -> SimpleNamespace:
    """Mimic the shape of an Anthropic Messages response: .content[0].text and
    .stop_reason. A plain object with a .text attribute is treated as a
    TextBlock by isinstance? No — so we patch TextBlock check via a real block."""
    from anthropic.types import TextBlock

    block = TextBlock(type="text", text=text)
    return SimpleNamespace(content=[block], stop_reason=stop_reason)


def _make_generator() -> SAPGenerator:
    gen = SAPGenerator(MagicMock())
    gen._settings = SimpleNamespace(AI_JOB_TIMEOUT_SECONDS=300)
    return gen


@pytest.mark.asyncio
async def test_returns_single_response_when_not_truncated():
    gen = _make_generator()
    gen._client = MagicMock()
    gen._client.messages.create = AsyncMock(
        return_value=_response('{"document_type": "SAP"}', "end_turn")
    )

    out = await gen._call_claude(
        system_prompt="sys", user_prompt="user", model_id="claude-sonnet-4-6"
    )

    assert out == '{"document_type": "SAP"}'
    assert gen._client.messages.create.await_count == 1


@pytest.mark.asyncio
async def test_continues_until_completion_and_concatenates():
    gen = _make_generator()
    gen._client = MagicMock()
    # First response truncates; second completes. Concatenation must reconstruct
    # valid JSON.
    gen._client.messages.create = AsyncMock(
        side_effect=[
            _response('{"document_type": "SAP", "ti', "max_tokens"),
            _response('tle": "X"}', "end_turn"),
        ]
    )

    out = await gen._call_claude(
        system_prompt="sys", user_prompt="user", model_id="claude-sonnet-4-6"
    )

    assert out == '{"document_type": "SAP", "title": "X"}'
    assert gen._client.messages.create.await_count == 2


@pytest.mark.asyncio
async def test_continuation_replays_partial_and_ends_with_user_turn():
    gen = _make_generator()
    gen._client = MagicMock()
    gen._client.messages.create = AsyncMock(
        side_effect=[
            _response('{"a": 1, ', "max_tokens"),
            _response('"b": 2}', "end_turn"),
        ]
    )

    await gen._call_claude(system_prompt="sys", user_prompt="user prompt", model_id="m")

    # The second call resumes by replaying the accumulated (whitespace-trimmed)
    # text as an assistant turn, then a trailing user "continue" message — the
    # conversation must end with a user message (Claude rejects assistant prefill).
    second_call_messages = gen._client.messages.create.await_args_list[1].kwargs[
        "messages"
    ]
    assert second_call_messages[0] == {"role": "user", "content": "user prompt"}
    assert second_call_messages[1] == {"role": "assistant", "content": '{"a": 1,'}
    assert second_call_messages[2]["role"] == "user"
    assert second_call_messages[-1]["role"] == "user"


@pytest.mark.asyncio
async def test_raises_when_still_truncated_after_budget():
    gen = _make_generator()
    gen._client = MagicMock()
    # Always truncates — the loop must terminate and fail loudly.
    gen._client.messages.create = AsyncMock(
        return_value=_response("partial", "max_tokens")
    )

    with pytest.raises(ValueError, match="still truncated"):
        await gen._call_claude(system_prompt="sys", user_prompt="user", model_id="m")

    # One initial call plus MAX_CONTINUATION_ROUNDS continuations.
    assert (
        gen._client.messages.create.await_count
        == BaseGenerator.MAX_CONTINUATION_ROUNDS + 1
    )
