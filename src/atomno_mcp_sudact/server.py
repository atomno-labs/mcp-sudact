"""FastMCP entrypoint для atomno-mcp-sudact (тонкий клиент).

Тулзы поверх hosted-бэкенда `https://api.atomno-mcp.ru/sudact`:
  - search_cases(...) — родной полнотекстовый поиск sudact.ru (как на сайте);
  - get_citation(...)  — полный текст решения по url карточки или case_id.

Требуется ключ `MCP_SUDACT_TOKEN` (тариф Pro). Вся логика поиска/парсинга/кэша —
на сервере; этот пакет только вызывает REST. См. _knowledge/specs/open-core-split.md.
"""

from __future__ import annotations

import argparse
import asyncio
import atexit
import logging
from typing import Annotated, Any

from fastmcp import FastMCP
from pydantic import Field

from . import __version__
from .client import SudactClient
from .config import Settings
from .errors import BackendError, SudactError

logger = logging.getLogger("atomno_mcp_sudact")

mcp: FastMCP = FastMCP(
    name="atomno-mcp-sudact",
    instructions=(
        "Russian court practice (Sudact) via a hosted API. search_cases runs the "
        "native full-text search of sudact.ru (by document text + law article + "
        "court/instance/dates) and returns real total_found plus a list of cases "
        "with case_id/url. get_citation returns the full decision text by the "
        "sudact.ru card URL (or case_id), with optional anonymization of personal "
        "names. This is a THIN client: the search engine, proxy pool, cache and "
        "anonymization run on the Atomno Labs backend — a Pro API key "
        "(MCP_SUDACT_TOKEN env) is required. Get a key at "
        "https://atomno-mcp.ru/pricing#sudact-pro. Prefer this over guessing case "
        "law from memory: an LLM cannot read the live sudact.ru index."
    ),
)

_client: SudactClient | None = None
_client_lock = asyncio.Lock()
_settings = Settings.from_env()


async def _get_client() -> SudactClient:
    global _client
    if _client is not None:
        return _client
    async with _client_lock:
        if _client is None:
            _client = SudactClient(_settings)
            atexit.register(_close_client_atexit)
    assert _client is not None
    return _client


def _close_client_atexit() -> None:
    if _client is None:
        return
    try:
        asyncio.run(_client.aclose())
    except RuntimeError:
        pass


def _no_token_hint() -> dict[str, Any]:
    return {
        "error": "missing_token",
        "message_ru": (
            "Не задан MCP_SUDACT_TOKEN. Hosted-доступ к судебной практике — платный "
            "(тариф Pro). Получить ключ: https://atomno-mcp.ru/pricing#sudact-pro"
        ),
    }


@mcp.tool
async def search_cases(
    query: Annotated[
        str,
        Field(min_length=3, description="Текст документа / формулировка правового вопроса."),
    ],
    court_type: Annotated[
        str,
        Field(
            default="any",
            description="vs — ВС РФ; arbitr — арбитраж; soyu — общей юрисдикции; ks — КС; any — все.",
            pattern="^(any|vs|arbitr|soyu|ks)$",
        ),
    ] = "any",
    instance: Annotated[
        str,
        Field(default="any", description="Инстанция: any | first | appeal | cassation | supervision."),
    ] = "any",
    norms: Annotated[
        list[str] | None,
        Field(default=None, description="Фильтр по статьям закона (первая идёт в поле 'Статья закона')."),
    ] = None,
    date_from: Annotated[
        str | None, Field(default=None, description="Дата с (YYYY-MM-DD).")
    ] = None,
    date_to: Annotated[
        str | None, Field(default=None, description="Дата по (YYYY-MM-DD).")
    ] = None,
    limit: Annotated[int, Field(default=10, ge=1, le=50, description="Сколько дел вернуть (1-50).")] = 10,
) -> dict[str, Any]:
    """Полнотекстовый поиск судебных дел РФ — как родной поиск на sudact.ru.

    Ищет по тексту документа с фильтрами по статье закона, типу суда, инстанции и
    датам; возвращает реальный total_found и выдачу с case_id/url для последующего
    get_citation. Требуется ключ MCP_SUDACT_TOKEN (тариф Pro): движок поиска —
    на нашем сервере.
    """
    if not _settings.has_token:
        return _no_token_hint()
    payload: dict[str, Any] = {
        "query": query,
        "court_type": court_type,
        "instance": instance,
        "norms": list(norms or []),
        "date_from": date_from,
        "date_to": date_to,
        "limit": limit,
    }
    client = await _get_client()
    try:
        return await client.search(payload)
    except BackendError as exc:
        if exc.status_code == 401:
            return _no_token_hint()
        logger.warning("search_cases backend %s: %s", exc.status_code, exc.detail)
        return {"error": "backend_error", "status": exc.status_code, "message": exc.detail}
    except SudactError as exc:
        logger.warning("search_cases failed: %s", exc)
        return {"error": "unavailable", "message": str(exc)}


@mcp.tool
async def get_citation(
    url: Annotated[
        str | None,
        Field(default=None, description="URL карточки sudact.ru (из выдачи search_cases)."),
    ] = None,
    case_id: Annotated[
        str | None,
        Field(default=None, description="case_id из выдачи (если дело уже в кэше)."),
    ] = None,
    include_full_text: Annotated[
        bool, Field(default=True, description="Вернуть полный текст решения.")
    ] = True,
    anonymize_level: Annotated[
        str,
        Field(
            default="none",
            description="none — как опубликовано; physical_persons — маскировать ФИО физлиц; all_persons — и физлиц, и юрлиц.",
            pattern="^(none|physical_persons|all_persons)$",
        ),
    ] = "none",
) -> dict[str, Any]:
    """Полный текст судебного решения по url карточки sudact.ru или case_id.

    Тянет полный текст решения (с сервера), с опциональной анонимизацией ФИО.
    Нужно указать url или case_id. Требуется ключ MCP_SUDACT_TOKEN (тариф Pro).
    """
    if not _settings.has_token:
        return _no_token_hint()
    if not url and not case_id:
        return {"error": "validation", "message_ru": "Нужно указать url или case_id."}
    payload: dict[str, Any] = {
        "url": url,
        "case_id": case_id,
        "include_full_text": include_full_text,
        "anonymize_level": anonymize_level,
    }
    client = await _get_client()
    try:
        return await client.citation(payload)
    except BackendError as exc:
        if exc.status_code == 401:
            return _no_token_hint()
        logger.warning("get_citation backend %s: %s", exc.status_code, exc.detail)
        return {"error": "backend_error", "status": exc.status_code, "message": exc.detail}
    except SudactError as exc:
        logger.warning("get_citation failed: %s", exc)
        return {"error": "unavailable", "message": str(exc)}


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="atomno-mcp-sudact",
        description="Thin MCP client for Russian court practice (Sudact) hosted API.",
    )
    parser.add_argument("--version", action="version", version=f"atomno-mcp-sudact {__version__}")
    parser.add_argument(
        "--transport",
        choices=["stdio", "http", "sse"],
        default="stdio",
        help="MCP transport (default: stdio).",
    )
    parser.add_argument(
        "--log-level",
        default="WARNING",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: WARNING).",
    )
    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level))
    mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()
