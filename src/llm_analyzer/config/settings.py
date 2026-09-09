import tomllib
from enum import StrEnum
from pathlib import Path

from pydantic import Field, ValidationError

from llm_analyzer.config.paths import config_path
from llm_analyzer.schemas.common import StrictModel
from llm_analyzer.utils.errors import AnalyzerError


class UseCase(StrEnum):
    CHAT = "chat"
    RAG = "rag"
    CODING = "coding"
    AGENTS = "agents"
    REASONING = "reasoning"
    EMBEDDINGS = "embeddings"
    MULTIMODAL = "multimodal"


class Priority(StrEnum):
    BALANCED = "balanced"
    QUALITY = "quality"
    LOW_MEMORY = "low-memory"
    SPEED = "speed"


class ReportFormat(StrEnum):
    MARKDOWN = "markdown"
    JSON = "json"
    TEXT = "text"
    HTML = "html"


class Settings(StrictModel):
    color: bool = True
    progress: bool = True
    default_report_format: ReportFormat = ReportFormat.MARKDOWN
    default_use_case: UseCase = UseCase.CHAT
    default_priority: Priority = Priority.BALANCED
    default_context: int = Field(default=4096, ge=128, le=1048576)
    top_recommendations: int = Field(default=5, ge=1, le=100)
    ram_headroom_fraction: float = Field(default=0.15, ge=0.05, le=0.8)
    vram_headroom_fraction: float = Field(default=0.10, ge=0.05, le=0.8)
    minimum_ram_reserve_gib: float = Field(default=1.0, ge=0.25, le=64)
    runtime_overhead_gib: float = Field(default=0.5, ge=0.1, le=32)
    working_buffer_fraction: float = Field(default=0.10, ge=0.05, le=1)
    storage_multiplier: float = Field(default=1.2, ge=1, le=4)


def load_settings(path: Path | None = None) -> Settings:
    selected = path or config_path()
    try:
        if not selected.exists():
            if path:
                raise AnalyzerError("Requested config file does not exist", 2)
            return Settings()
        with selected.open("rb") as stream:
            return Settings.model_validate(tomllib.load(stream))
    except (OSError, ValueError, ValidationError) as exc:
        raise AnalyzerError("Invalid or unreadable configuration; check config.toml", 2) from exc
