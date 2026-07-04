"""atomno-mcp-sudact — тонкий MCP-клиент судебной практики РФ (Sudact).

Клиент НЕ содержит движка: только httpx-вызовы на hosted-бэкенд Atomno Labs
(`api.atomno-labs.ru/sudact`) и форматирование ответа. Полнотекстовый поиск
sudact.ru, парсеры, кэш и анонимизация — приватные, на сервере (тариф Pro).
См. _knowledge/specs/open-core-split.md.
"""

__version__ = "0.1.1"

__all__ = ["__version__"]
