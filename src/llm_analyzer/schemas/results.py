from enum import StrEnum
from typing import Literal

from pydantic import Field

from llm_analyzer.config.settings import Priority, Settings, UseCase
from llm_analyzer.schemas.common import Bytes, Confidence, Envelope, StrictModel
from llm_analyzer.schemas.hardware import HardwareScanResult


class Fit(StrEnum):
    EXCELLENT = "EXCELLENT"
    GOOD = "GOOD"
    BORDERLINE = "BORDERLINE"
    NOT_RECOMMENDED = "NOT_RECOMMENDED"
    UNKNOWN = "UNKNOWN"


class Execution(StrEnum):
    GPU = "full_gpu"
    HYBRID = "hybrid"
    CPU = "cpu"
    NONE = "undetermined"


class RecommendationReason(StrictModel):
    code: str
    level: Literal["pass", "warning", "fail", "unknown", "info"]
    message: str


class MemoryEstimate(StrictModel):
    weights_bytes: Bytes
    kv_cache_bytes: Bytes
    runtime_overhead_bytes: Bytes
    working_buffers_bytes: Bytes
    total_bytes: Bytes
    storage_required_bytes: Bytes
    confidence: Confidence
    assumptions: list[str]


class AnalysisRequest(StrictModel):
    use_case: UseCase = UseCase.CHAT
    priority: Priority = Priority.BALANCED
    context: int = Field(default=4096, ge=128, le=1048576)
    top: int = Field(default=5, ge=1, le=100)
    runtime: str = "auto"
    model_id: str | None = None
    quant: str | None = None


class ModelRecommendation(StrictModel):
    model_id: str
    display_name: str
    parameters: int
    quantization: str
    bits_estimate: float
    generic: bool = False
    context: int
    runtime: str
    runtime_installed: bool
    runtime_compatibility: Literal["conditional", "unsupported", "unknown"] = "conditional"
    fit: Fit
    execution: Execution
    gpu_index: int | None = None
    gpu_name: str | None = None
    backend: str = "cpu"
    memory: MemoryEstimate
    safe_ram_bytes: Bytes | None
    safe_vram_bytes: Bytes | None = None
    estimated_host_bytes: Bytes
    estimated_device_bytes: Bytes = 0
    confidence: Confidence
    performance_class: Literal["fast", "moderate", "slow", "very_slow", "unknown"] = "unknown"
    performance_confidence: Confidence = Confidence.LOW
    reasons: list[RecommendationReason]


class RecommendationResult(Envelope):
    request: AnalysisRequest
    catalog_version: str
    catalog_sha256: str
    rules_version: str
    rules_sha256: str
    recommendations: list[ModelRecommendation]
    rejected: list[ModelRecommendation]
    unknown: list[ModelRecommendation]
    generic_capacity: list[ModelRecommendation]
    evaluated_configurations: list[ModelRecommendation]
    capability_summary: str
    capability_reason: str
    warnings: list[str]


class AnalysisResult(Envelope):
    hardware: HardwareScanResult
    result: RecommendationResult
    settings: Settings
    methodology: str


class BenchmarkResult(Envelope):
    mode: Literal["system"] = "system"
    operation: str = "SHA-256, fixed 1 MiB buffer, single worker"
    elapsed_seconds: float
    processed_bytes: Bytes
    throughput_mib_per_second: float
    ram_peak_bytes: Bytes | None = None
    inference_tokens_per_second: None = None
    note: str = "Measured CPU hashing throughput; cannot predict LLM inference speed"
