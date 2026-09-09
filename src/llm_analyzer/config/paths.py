from pathlib import Path

from platformdirs import PlatformDirs, user_documents_path

APP_DIRS = PlatformDirs("LocalLLMAnalyzer", appauthor=False)


def config_path() -> Path:
    return APP_DIRS.user_config_path / "config.toml"


def log_path() -> Path:
    return APP_DIRS.user_log_path / "llm-analyzer.log"


def report_directory() -> Path:
    # platformdirs uses the Windows known-folder API, including redirected Documents.
    return user_documents_path() / "Local LLM Analyzer" / "Reports"
