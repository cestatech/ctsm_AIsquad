"""Unit tests for trusted proxy header handling."""

from __future__ import annotations

from typing import Any

import pytest

from app.core.proxy_headers import TrustedProxyHeadersMiddleware


async def _receive() -> dict[str, Any]:
    return {"type": "http.request", "body": b"", "more_body": False}


async def _send(message: dict[str, Any]) -> None:
    return None


def _scope(
    *,
    peer: str,
    forwarded_for: str | None = None,
    forwarded_proto: str | None = None,
) -> dict[str, Any]:
    headers: list[tuple[bytes, bytes]] = []
    if forwarded_for:
        headers.append((b"x-forwarded-for", forwarded_for.encode()))
    if forwarded_proto:
        headers.append((b"x-forwarded-proto", forwarded_proto.encode()))
    return {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/",
        "raw_path": b"/",
        "query_string": b"",
        "root_path": "",
        "headers": headers,
        "client": (peer, 1234),
        "server": ("test", 80),
    }


@pytest.mark.asyncio
class TestTrustedProxyHeadersMiddleware:
    async def test_trusted_proxy_resolves_original_client(self):
        captured: dict[str, Any] = {}

        async def app(scope, receive, send):
            captured.update(scope)

        middleware = TrustedProxyHeadersMiddleware(
            app,
            trusted_proxies=["10.0.0.0/8"],
        )
        await middleware(
            _scope(
                peer="10.0.0.5",
                forwarded_for="198.51.100.42, 10.0.0.4",
                forwarded_proto="https",
            ),
            _receive,
            _send,
        )

        assert captured["client"] == ("198.51.100.42", 0)
        assert captured["scheme"] == "https"

    async def test_untrusted_peer_cannot_spoof_forwarded_headers(self):
        captured: dict[str, Any] = {}

        async def app(scope, receive, send):
            captured.update(scope)

        middleware = TrustedProxyHeadersMiddleware(
            app,
            trusted_proxies=["10.0.0.0/8"],
        )
        await middleware(
            _scope(
                peer="203.0.113.8",
                forwarded_for="198.51.100.42",
                forwarded_proto="https",
            ),
            _receive,
            _send,
        )

        assert captured["client"] == ("203.0.113.8", 1234)
        assert captured["scheme"] == "http"

    async def test_malformed_forwarded_chain_is_ignored(self):
        captured: dict[str, Any] = {}

        async def app(scope, receive, send):
            captured.update(scope)

        middleware = TrustedProxyHeadersMiddleware(
            app,
            trusted_proxies=["10.0.0.0/8"],
        )
        await middleware(
            _scope(peer="10.0.0.5", forwarded_for="not-an-ip"),
            _receive,
            _send,
        )

        assert captured["client"] == ("10.0.0.5", 1234)

    async def test_ipv6_proxy_network_is_supported(self):
        captured: dict[str, Any] = {}

        async def app(scope, receive, send):
            captured.update(scope)

        middleware = TrustedProxyHeadersMiddleware(
            app,
            trusted_proxies=["2001:db8:abcd::/48"],
        )
        await middleware(
            _scope(peer="2001:db8:abcd::2", forwarded_for="2001:db8::99"),
            _receive,
            _send,
        )

        assert captured["client"] == ("2001:db8::99", 0)
