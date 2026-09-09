from pathlib import Path

import pytest

from llm_analyzer.catalog.loader import load_catalog, load_rules
from llm_analyzer.config.settings import Settings
from llm_analyzer.hardware.scanner import read_scan

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def hardware():
    return read_scan(FIXTURES / "windows_nvidia_8gb_32gb.json")


@pytest.fixture
def catalog():
    return load_catalog()


@pytest.fixture
def rules():
    return load_rules()


@pytest.fixture
def settings():
    return Settings()


@pytest.fixture(autouse=True)
def isolated_cli(monkeypatch, tmp_path):
    from llm_analyzer.cli import app as cli_module

    monkeypatch.setattr(cli_module, "configure_logging", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        cli_module,
        "load_settings",
        lambda path=None: (
            Settings()
            if path is None
            else __import__(
                "llm_analyzer.config.settings", fromlist=["load_settings"]
            ).load_settings(path)
        ),
    )
    monkeypatch.setattr(
        "llm_analyzer.reports.generator.report_directory",
        lambda: tmp_path / "Documents" / "Reports",
    )
