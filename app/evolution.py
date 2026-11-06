"""Minimal Evolution API v2 client: list groups, fetch media as base64, send a quoted text."""
from __future__ import annotations

import logging
from typing import Any

import httpx

from .config import Settings

log = logging.getLogger("laschuk_resume.evolution")


class EvolutionError(RuntimeError):
    pass


class EvolutionClient:
    def __init__(self, settings: Settings, client: httpx.AsyncClient):
        self.s = settings
        self.http = client

    @property
    def _headers(self) -> dict[str, str]:
        return {"apikey": self.s.evolution_api_key, "Content-Type": "application/json"}

    def _url(self, path: str) -> str:
        return f"{self.s.evolution_base}/{path.strip('/')}/{self.s.evolution_instance}"

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        url = self._url(path)
        try:
            resp = await self.http.request(method, url, headers=self._headers, **kwargs)
        except httpx.HTTPError as exc:
            raise EvolutionError(f"{method} {path}: {exc.__class__.__name__}: {exc}") from exc
        if resp.status_code >= 400:
            raise EvolutionError(f"{method} {path}: HTTP {resp.status_code}: {resp.text[:300]}")
        try:
            return resp.json()
        except ValueError as exc:
            raise EvolutionError(f"{method} {path}: non-JSON response") from exc

    async def fetch_groups(self) -> list[dict[str, Any]]:
        data = await self._request("GET", "group/fetchAllGroups", params={"getParticipants": "false"})
        if isinstance(data, dict):
            data = data.get("groups") or data.get("data") or []
        return data if isinstance(data, list) else []

    async def get_media_base64(self, key: dict[str, Any]) -> tuple[str, str]:
        """Return (base64, mimetype) for a media message via /chat/getBase64FromMediaMessage."""
        data = await self._request(
            "POST",
            "chat/getBase64FromMediaMessage",
            json={"message": {"key": key}, "convertToMp4": False},
        )
        b64 = (data or {}).get("base64") if isinstance(data, dict) else None
        if not b64:
            raise EvolutionError("getBase64FromMediaMessage returned no base64")
        return b64, str(data.get("mimetype") or "")

    async def send_text_reply(
        self, jid: str, text: str, quoted_key: dict[str, Any], quoted_message: dict[str, Any]
    ) -> dict[str, Any]:
        # Strip inline media from the quote: Evolution only needs key + message shape.
        message = {k: v for k, v in (quoted_message or {}).items() if k != "base64"}
        return await self._request(
            "POST",
            "message/sendText",
            json={"number": jid, "text": text, "quoted": {"key": quoted_key, "message": message}},
        )
