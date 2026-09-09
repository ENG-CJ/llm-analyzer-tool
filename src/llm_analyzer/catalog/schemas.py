from datetime import date
from typing import Literal

from pydantic import Field, HttpUrl, model_validator

from llm_analyzer.config.settings import UseCase
from llm_analyzer.schemas.common import Bytes, Confidence, StrictModel

QUANT_BITS = {
    "Q2_K": 2.625,
    "Q3_K_M": 3.5,
    "Q4_0": 4.5,
    "Q4_K_M": 4.85,
    "Q5_K_M": 5.7,
    "Q6_K": 6.56,
    "Q8_0": 8.5,
    "FP16": 16,
    "BF16": 16,
}


class QuantizationDefinition(StrictModel):
    name: str
    bits_estimate: float = Field(gt=0, le=32)
    file_size_bytes: Bytes | None = None
    source: HttpUrl | None = None

    @model_validator(mode="after")
    def valid_quant(self) -> "QuantizationDefinition":
        if self.name not in QUANT_BITS:
            raise ValueError("Unknown quantization class")
        if abs(self.bits_estimate - QUANT_BITS[self.name]) > 0.01:
            raise ValueError("Quantization bit estimate must match documented class")
        if self.file_size_bytes == 0:
            raise ValueError("Quantization file size must be positive")
        if self.file_size_bytes is not None and self.source is None:
            raise ValueError("Measured file size requires a source")
        return self


class ModelDefinition(StrictModel):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]*$", max_length=100)
    display_name: str
    family: str
    publisher: str
    parameters: int = Field(gt=0, le=10**13)
    architecture: str
    modalities: list[Literal["text", "image"]] = Field(min_length=1)
    capabilities: list[UseCase] = Field(min_length=1)
    context_maximum: int = Field(ge=128, le=1048576)
    layers: int | None = Field(default=None, gt=0, le=1000)
    kv_heads: int | None = Field(default=None, gt=0, le=1024)
    head_dim: int | None = Field(default=None, gt=0, le=4096)
    embedding: bool = False
    generic: bool = False
    format: Literal["gguf"] = "gguf"
    quantizations: list[QuantizationDefinition] = Field(min_length=1)
    runtime_support: list[str] = Field(min_length=1)
    runtime_minimum_versions: dict[str, str] = Field(default_factory=dict)
    sources: list[HttpUrl] = Field(min_length=1)
    source_revision: str | None = None
    last_verified_at: date
    metadata_confidence: Confidence = Confidence.MEDIUM
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def valid_model(self) -> "ModelDefinition":
        names = [q.name for q in self.quantizations]
        if len(names) != len(set(names)):
            raise ValueError("Duplicate quantization names")
        if UseCase.MULTIMODAL in self.capabilities and "image" not in self.modalities:
            raise ValueError("Multimodal capability requires image modality")
        if self.embedding != (UseCase.EMBEDDINGS in self.capabilities):
            raise ValueError("Embedding architecture and capabilities disagree")
        return self


class Catalog(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    catalog_version: str
    models: list[ModelDefinition] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_ids(self) -> "Catalog":
        ids = [model.id for model in self.models]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate model IDs")
        return self


class CudaRule(StrictModel):
    minimum_compute_capability: float = Field(ge=0)
    minimum_driver_major: int = Field(ge=0)
    legacy_compute_below: float | None = None
    legacy_minimum_driver_major: int | None = None


class RuntimeRule(StrictModel):
    name: str
    platforms: list[str] = Field(min_length=1)
    architectures: list[str] = Field(min_length=1)
    model_architectures: list[str] = Field(min_length=1)
    formats: list[str] = Field(min_length=1)
    quantizations: list[str] = Field(min_length=1)
    backends: list[Literal["cpu", "cuda", "vulkan", "hip", "directml"]]
    partial_offload: bool
    required_cpu_flags: list[str] = Field(default_factory=list)
    minimum_version: str | None = None
    cuda: CudaRule | None = None
    source: HttpUrl
    last_verified_at: date
    note: str


class RuntimeRules(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    rules_version: str
    runtimes: list[RuntimeRule] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_rules(self) -> "RuntimeRules":
        names = [rule.name for rule in self.runtimes]
        if len(names) != len(set(names)):
            raise ValueError("Duplicate runtime rules")
        for rule in self.runtimes:
            if any(q not in QUANT_BITS for q in rule.quantizations):
                raise ValueError("Unknown quantization in runtime rule")
        return self
