"""CLI-тесты: --help / --version / дефолты парсера (см. atomno-mcp-conventions)."""

from __future__ import annotations

import subprocess
import sys

import pytest


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "atomno_mcp_sudact.server", *args],
        capture_output=True,
        text=True,
        timeout=30,
    )


class TestHelp:
    def test_help_exits_zero(self) -> None:
        r = _run("--help")
        assert r.returncode == 0
        assert "atomno-mcp-sudact" in r.stdout


class TestVersion:
    def test_version_exits_zero(self) -> None:
        r = _run("--version")
        assert r.returncode == 0
        assert "atomno-mcp-sudact" in r.stdout


class TestTransportValidation:
    def test_bad_transport_rejected(self) -> None:
        r = _run("--transport", "carrier-pigeon")
        assert r.returncode != 0


class TestLogLevelValidation:
    def test_bad_log_level_rejected(self) -> None:
        r = _run("--log-level", "LOUD")
        assert r.returncode != 0


class TestParserDefaults:
    def test_settings_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("MCP_SUDACT_TOKEN", raising=False)
        monkeypatch.delenv("MCP_SUDACT_API_BASE", raising=False)
        from atomno_mcp_sudact.config import DEFAULT_API_BASE, Settings

        s = Settings.from_env()
        assert s.api_base == DEFAULT_API_BASE
        assert s.token is None
        assert s.has_token is False


class TestInvalidEnvBailsOutCleanly:
    def test_bad_timeout_falls_back(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MCP_SUDACT_TIMEOUT", "not-a-number")
        from atomno_mcp_sudact.config import DEFAULT_TIMEOUT, Settings

        assert Settings.from_env().timeout == DEFAULT_TIMEOUT
