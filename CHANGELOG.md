# Changelog

Формат — [Keep a Changelog](https://keepachangelog.com/ru/1.0.0/),
версии — [SemVer](https://semver.org/lang/ru/).

## [0.1.2] — 2026-07-05

### Changed

- GitHub-организация переименована `atomno-labs` → `atomno-mcp`; обновлены ссылки на репозиторий и MCP-реестр (`pyproject.toml`, `server.json`, `README`, workflow публикации).

## [0.1.0] — 2026-07-03

### Added

- Первый публичный релиз тонкого MCP-клиента `atomno-mcp-sudact`.
- Тул `search_cases` — полнотекстовый поиск судебной практики РФ (по тексту
  документа, статье закона, суду, инстанции, датам).
- Тул `get_citation` — полный текст судебного решения по URL карточки/`case_id`
  с опциональной анонимизацией.
- CLI (`atomno-mcp-sudact`) с `--help`, `--version`, `--transport`, `--log-level`.

Движок поиска, пул прокси, кэш и анонимизация — на hosted-бэкенде Atomno Labs
(тариф Pro); клиент лишь общается с ним по HTTP.
