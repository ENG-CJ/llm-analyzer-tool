from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from llm_analyzer import __version__

Bytes = Annotated[int, Field(ge=0, le=2**63 - 1)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, validate_assignment=True)


class Confidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


class Status(StrEnum):
    AVAILABLE = "available"
    NOT_AVAILABLE = "not_available"
    UNSUPPORTED = "unsupported"
    UNKNOWN = "unknown"


class Evidence(StrictModel):
    source: str
    confidence: Confidence = Confidence.UNKNOWN
    status: Status = Status.UNKNOWN
    note: str = ""


class Envelope(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    application_version: str = __version__
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
