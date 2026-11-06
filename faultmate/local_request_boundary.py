"""Loopback-only browser request boundary for existing FaultMate AI.

A web page on another origin must never be allowed to trigger the local paid
agent API even if it can guess public case IDs, the canonical preview SHA or
the user's locally configured provider key. This is defense-in-depth against
cross-site and DNS-rebinding browser requests, not authentication against
a malicious process already running on the same computer.

The normal UI continues to work at http://127.0.0.1:8787 or localhost.
'http://testserver' is used ONLY by the existing FastAPI TestClient suite.
"""
from __future__ import annotations

from urllib.parse import urlsplit

from starlette.requests import Request

LOCAL_HOSTS = frozenset({"127.0.0.1", "localhost", "testserver"})
REJECTION = "local_same_origin_required"


def verified_local_host(raw: str | None) -> bool:
    """Require a literal loopback hostname, not arbitrary DNS or userinfo."""
    if not raw or not isinstance(raw, str) or raw.strip() != raw:
        return False
    if any(c.isspace() or ord(c) < 32 for c in raw):
        return False
    try:
        parsed = urlsplit("http://" + raw)
        return (
            parsed.scheme == "http"
            and parsed.hostname in LOCAL_HOSTS
            and parsed.netloc == raw
            and parsed.path == ""
            and parsed.query == ""
            and parsed.fragment == ""
            and parsed.username is None
            and parsed.password is None
            and (parsed.port is None or 1 <= parsed.port <= 65535)
        )
    except ValueError:
        return False


def verified_same_origin(raw_origin: str | None,
                         raw_host: str | None, scheme: str) -> bool:
    """Missing Origin supports native localhost tools; *present* must match."""
    if raw_origin is None:
        return True
    if not isinstance(raw_origin, str) or not raw_origin:
        return False
    if raw_origin == "null" or any(c.isspace() or ord(c) < 32 for c in raw_origin):
        return False
    if not verified_local_host(raw_host):
        return False
    try:
        origin = urlsplit(raw_origin)
        if origin.scheme.lower() != scheme.lower() or origin.scheme not in ("http", "https"):
            return False
        if origin.username is not None or origin.password is not None:
            return False
        if origin.path or origin.query or origin.fragment:
            return False
        if origin.netloc.lower() != raw_host.lower():
            return False
        # Both must actually be a valid host with a valid explicit port.
        if origin.hostname not in LOCAL_HOSTS:
            return False
        _ = origin.port
    except ValueError:
        return False
    return True


def browser_request_allowed(request: Request) -> bool:
    """Read-only check performed BEFORE any app route or paid agent function."""
    hosts = request.headers.getlist("host")
    if len(hosts) != 1 or not verified_local_host(hosts[0]):
        return False
    if request.method not in ("GET", "HEAD", "OPTIONS") and request.url.path.startswith("/api/"):
        if request.headers.get("sec-fetch-site", "").lower() == "cross-site":
            return False
        origins = request.headers.getlist("origin")
        if len(origins) > 1:
            return False
        if origins and not verified_same_origin(origins[0], hosts[0], request.url.scheme):
            return False
    return True
