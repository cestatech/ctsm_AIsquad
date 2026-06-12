"""Trusted proxy handling for client IP and request scheme resolution."""

from __future__ import annotations

from ipaddress import ip_address, ip_network
from typing import cast

from starlette.types import ASGIApp, Receive, Scope, Send


class TrustedProxyHeadersMiddleware:
    """Apply forwarded headers only when the immediate peer is trusted."""

    def __init__(self, app: ASGIApp, trusted_proxies: list[str]) -> None:
        self.app = app
        self._trusted_networks = [
            ip_network(proxy, strict=False) for proxy in trusted_proxies
        ]

    def _is_trusted(self, host: str) -> bool:
        try:
            address = ip_address(host)
        except ValueError:
            return False
        return any(address in network for network in self._trusted_networks)

    def _resolve_forwarded_client(self, forwarded_for: str) -> str | None:
        hosts = [host.strip() for host in forwarded_for.split(",")]
        if not hosts or any(not host for host in hosts):
            return None

        try:
            normalized = [str(ip_address(host)) for host in hosts]
        except ValueError:
            return None

        for host in reversed(normalized):
            if not self._is_trusted(host):
                return host
        return normalized[0]

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in {"http", "websocket"}:
            await self.app(scope, receive, send)
            return

        client = scope.get("client")
        peer_host = client[0] if client else None
        if not peer_host or not self._is_trusted(peer_host):
            await self.app(scope, receive, send)
            return

        headers = dict(scope["headers"])
        forwarded_for = headers.get(b"x-forwarded-for")
        forwarded_proto = headers.get(b"x-forwarded-proto")
        updated_scope = dict(scope)

        if forwarded_for:
            resolved = self._resolve_forwarded_client(forwarded_for.decode("latin1"))
            if resolved:
                updated_scope["client"] = (resolved, 0)

        if forwarded_proto:
            proto = forwarded_proto.decode("latin1").strip().lower()
            if proto in {"http", "https"}:
                updated_scope["scheme"] = (
                    proto.replace("http", "ws")
                    if scope["type"] == "websocket"
                    else proto
                )

        await self.app(cast(Scope, updated_scope), receive, send)
