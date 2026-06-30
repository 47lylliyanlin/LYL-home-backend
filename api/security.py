"""
Lightweight security helpers for cloud test deployments.

Public chat endpoints stay open for the app frontend. Dashboard, debug, profile,
maintenance, and memory inspection endpoints can be protected with a shared admin
token by setting KIRO_ADMIN_TOKEN.
"""

import os
from typing import Iterable

from fastapi import Request
from fastapi.responses import JSONResponse


ADMIN_PREFIXES = (
    "/dashboard",
    "/api/gateway",
    "/api/profile",
    "/api/memory",
    "/api/darkroom",
    "/api/dream",
    "/api/maintenance",
    "/api/pulse",
    "/api/introspection",
    "/api/ai/config",
)


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def admin_token() -> str:
    return _env("KIRO_ADMIN_TOKEN")


def admin_auth_enabled() -> bool:
    return bool(admin_token())


def cors_origins() -> list[str]:
    raw = _env("KIRO_CORS_ORIGINS", "*")
    if raw == "*":
        return ["*"]
    values = [item.strip() for item in raw.split(",") if item.strip()]
    return values or ["*"]


def is_admin_path(path: str, prefixes: Iterable[str] = ADMIN_PREFIXES) -> bool:
    return any(path == prefix or path.startswith(prefix + "/") for prefix in prefixes)


def request_token(request: Request) -> str:
    return (
        request.headers.get("X-Kiro-Admin-Token")
        or request.query_params.get("admin_token")
        or ""
    ).strip()


async def admin_auth_middleware(request: Request, call_next):
    if not is_admin_path(request.url.path):
        return await call_next(request)

    expected = admin_token()
    if not expected:
        return await call_next(request)

    if request_token(request) != expected:
        return JSONResponse(
            status_code=401,
            content={"error": "admin authorization required"},
            headers={"WWW-Authenticate": "KiroAdmin"},
        )

    return await call_next(request)
