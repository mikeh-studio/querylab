"""Local browser boundary: no remote mode or trusted forwarded headers."""

from __future__ import annotations

import ipaddress
import re
import secrets

from starlette.datastructures import Headers
from starlette.responses import JSONResponse, PlainTextResponse


def is_loopback_client(host: str | None) -> bool:
    if host in {"localhost", "testclient"}:
        return True
    try:
        address = ipaddress.ip_address(host or "")
        return address.is_loopback or bool(
            isinstance(address, ipaddress.IPv6Address)
            and address.ipv4_mapped
            and address.ipv4_mapped.is_loopback
        )
    except ValueError:
        return False


def local_authority(value: str) -> bool:
    # Match the raw authority, not a URL parser's normalized/decoded hostname.
    return bool(
        re.fullmatch(r"(?:localhost|127\.0\.0\.1|\[::1\])(?::[0-9]{1,5})?", value)
    ) and (
        ":" not in value.rsplit("]", 1)[-1]
        or 1 <= int(value.rsplit(":", 1)[1]) <= 65535
    )


class LocalOnlyMiddleware:
    """Reject hostile requests before reading bodies or entering handlers.

    The random token is scoped to this app process. It is only obtainable through
    a same-origin, non-cacheable bootstrap request and is never put in a URL.
    """

    def __init__(self, app):
        self.app = app
        self.token = secrets.token_urlsafe(32)

    async def __call__(self, scope, receive, send):
        if scope["type"] not in {"http", "websocket"}:
            return await self.app(scope, receive, send)
        headers = Headers(scope=scope)
        host = headers.get("host", "")
        client = scope.get("client")
        server = scope.get("server")
        suffix = host.rsplit("]", 1)[-1] if host.startswith("[") else host
        valid_authority = local_authority(host)
        port = None
        if valid_authority:
            port = (
                int(suffix.rsplit(":", 1)[1])
                if ":" in suffix and suffix.rsplit(":", 1)[1].isdigit()
                else (443 if scope.get("scheme") in {"https", "wss"} else 80)
            )
        allowed = (
            is_loopback_client(client[0] if client else None)
            and len(headers.getlist("host")) == 1
            and valid_authority
            and (not server or server[1] == port)
            and not any(
                key == "forwarded"
                or key == "x-real-ip"
                or key.startswith("x-forwarded-")
                for key in headers
            )
            and all(
                len(headers.getlist(key)) <= 1
                for key in ("origin", "sec-fetch-site", "x-local-session")
            )
            and headers.get("sec-fetch-site", "same-origin") in {"same-origin", "none"}
        )
        origin = headers.get("origin")
        if origin is not None:
            scheme = "https" if scope.get("scheme") in {"https", "wss"} else "http"
            allowed = allowed and origin == f"{scheme}://{host}"
        websocket = scope["type"] == "websocket"
        mutation = not websocket and scope["method"] not in {"GET", "HEAD", "OPTIONS"}
        if websocket:
            protocol = "local-session." + self.token
            allowed = (
                allowed
                and origin is not None
                and any(
                    secrets.compare_digest(p.encode(), protocol.encode())
                    for p in scope.get("subprotocols", [])
                )
            )
            if allowed:
                scope["local_session_protocol"] = protocol
        elif mutation:
            supplied = headers.get("x-local-session", "")
            allowed = allowed and secrets.compare_digest(
                supplied.encode(), self.token.encode()
            )
        if not allowed:
            if websocket:
                return await send({"type": "websocket.close", "code": 1008})
            return await PlainTextResponse(
                "Local browser request denied", status_code=403
            )(scope, receive, send)
        if (
            not websocket
            and scope["path"] == "/api/local-session"
            and scope["method"] == "GET"
        ):
            return await JSONResponse(
                {"token": self.token},
                headers={"Cache-Control": "no-store", "Vary": "Origin, Sec-Fetch-Site"},
            )(scope, receive, send)
        await self.app(scope, receive, send)
