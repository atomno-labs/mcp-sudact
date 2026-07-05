"""HTTP-клиент к hosted-бэкенду Sudact (api.atomno-mcp.ru/sudact).

Тонкая обёртка над httpx: один общий AsyncClient, заголовок X-API-Key,
маппинг ошибок в SudactError. Никакой логики поиска/парсинга — только транспорт.
"""

from __future__ import annotations

from typing import Any

import httpx

from . import __version__
from .config import Settings
from .errors import BackendError, BackendUnavailable

_USER_AGENT = f"atomno-mcp-sudact/{__version__}"


class SudactClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        headers = {"User-Agent": _USER_AGENT, "Accept": "application/json"}
        if settings.token:
            headers["X-API-Key"] = settings.token
        self._client = httpx.AsyncClient(
            base_url=settings.api_base,
            timeout=settings.timeout,
            headers=headers,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            resp = await self._client.post(path, json=payload)
        except httpx.TimeoutException as exc:
            raise BackendUnavailable(f"timeout calling {path}") from exc
        except httpx.HTTPError as exc:
            raise BackendUnavailable(f"network error calling {path}: {exc}") from exc
        return self._parse(resp, path)

    @staticmethod
    def _parse(resp: httpx.Response, path: str) -> dict[str, Any]:
        if resp.status_code >= 400:
            raise BackendError(resp.status_code, _extract_detail(resp))
        try:
            return resp.json()
        except ValueError as exc:
            raise BackendError(resp.status_code, "invalid JSON in response") from exc

    async def search(self, payload: dict[str, Any]) -> dict[str, Any]:
        """POST /v1/search — родной полнотекстовый поиск sudact.ru."""
        return await self._post("/v1/search", payload)

    async def citation(self, payload: dict[str, Any]) -> dict[str, Any]:
        """POST /v1/citation — полный текст решения по url карточки / case_id."""
        return await self._post("/v1/citation", payload)


def _extract_detail(resp: httpx.Response) -> str:
    try:
        body = resp.json()
    except ValueError:
        return resp.text[:300] or resp.reason_phrase
    if isinstance(body, dict):
        for key in ("message_ru", "detail", "message", "error"):
            if body.get(key):
                return str(body[key])
    return str(body)[:300]
