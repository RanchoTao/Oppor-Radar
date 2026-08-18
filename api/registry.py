from __future__ import annotations

import hmac
import json
import os
from http.server import BaseHTTPRequestHandler

from src.registry.github_store import GithubRegistryStore
from src.registry.validation import (
    RegistryValidationError,
    validate_groups,
    validate_profile,
    validate_sources,
)


def _allowed_origins() -> set[str]:
    raw = os.getenv(
        "OPPOR_ALLOWED_ORIGINS",
        "https://ranchotao.github.io,http://localhost:8000,http://127.0.0.1:8000",
    )
    return {value.strip().rstrip("/") for value in raw.split(",") if value.strip()}


def _authorized(header: str | None) -> bool:
    expected = os.getenv("OPPOR_ADMIN_TOKEN", "")
    if not expected or not header or not header.startswith("Bearer "):
        return False
    supplied = header.removeprefix("Bearer ").strip()
    return hmac.compare_digest(supplied, expected)


def prepare_payload(body: dict, current: dict) -> dict:
    if not isinstance(body, dict):
        raise RegistryValidationError("body must be an object")

    groups = validate_groups(body["groups"]) if "groups" in body else current["groups"]
    result = {}
    if "groups" in body:
        result["groups"] = groups
    if "sources" in body:
        result["sources"] = validate_sources(body["sources"], groups)
    if "profile" in body:
        result["profile"] = validate_profile(body["profile"])
    if not result:
        raise RegistryValidationError("nothing to update")
    return result


class handler(BaseHTTPRequestHandler):
    server_version = "OpporRadarRegistry/1.0"

    def _origin(self) -> str | None:
        origin = (self.headers.get("Origin") or "").rstrip("/")
        return origin if origin in _allowed_origins() else None

    def _headers(self, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        origin = self._origin()
        if origin:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
            self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
            self.send_header("Access-Control-Allow-Methods", "GET, PUT, OPTIONS")
        self.end_headers()

    def _json(self, value, status: int = 200) -> None:
        self._headers(status)
        self.wfile.write(json.dumps(value, ensure_ascii=False).encode("utf-8"))

    def _require_auth(self) -> bool:
        if not _authorized(self.headers.get("Authorization")):
            self._json({"error": "unauthorized"}, 401)
            return False
        return True

    def do_OPTIONS(self):
        if self.headers.get("Origin") and not self._origin():
            self._json({"error": "origin_not_allowed"}, 403)
            return
        self._headers(204)

    def do_GET(self):
        if not self._require_auth():
            return
        try:
            registry = GithubRegistryStore().read_registry()
            self._json({"ok": True, **registry})
        except Exception as exc:
            self._json({"error": "registry_read_failed", "detail": str(exc)[:300]}, 502)

    def do_PUT(self):
        if not self._require_auth():
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
            if length <= 0 or length > 2_000_000:
                raise RegistryValidationError("invalid body size")
            body = json.loads(self.rfile.read(length).decode("utf-8"))
            store = GithubRegistryStore()
            current = store.read_registry()
            payload = prepare_payload(body, current)
            message = str(body.get("message") or "chore: update Oppor Radar registry")[:120]
            result = store.write_registry(payload, message=message)
            self._json({"ok": True, **result})
        except RegistryValidationError as exc:
            self._json({"error": "validation_error", "detail": str(exc)}, 400)
        except json.JSONDecodeError:
            self._json({"error": "invalid_json"}, 400)
        except Exception as exc:
            self._json({"error": "registry_write_failed", "detail": str(exc)[:300]}, 502)
