from pydantic import Field, model_validator

from llm_analyzer.schemas.common import Bytes, Envelope, Evidence, Status, StrictModel


class PlatformInfo(StrictModel):
    os: str = "unknown"
    version: str | None = None
    build: str | None = None
    edition: str | None = None
    architecture: str = "unknown"
    machine_architecture: str = "unknown"
    manufacturer: str | None = None
    model: str | None = None


class CPUInfo(StrictModel):
    vendor: str | None = None
    brand: str | None = None
    architecture: str = "unknown"
    physical_cores: int | None = Field(default=None, gt=0)
    logical_cores: int | None = Field(default=None, gt=0)
    flags: list[str] = Field(default_factory=list)
    flags_known: bool = False
    frequency_mhz: float | None = Field(default=None, gt=0)
    evidence: dict[str, Evidence] = Field(default_factory=dict)


class MemoryInfo(StrictModel):
    total_bytes: Bytes | None = None
    available_bytes: Bytes | None = None
    used_bytes: Bytes | None = None
    utilization_percent: float | None = Field(default=None, ge=0, le=100)
    swap_total_bytes: Bytes | None = None
    swap_free_bytes: Bytes | None = None
    evidence: Evidence = Field(default_factory=lambda: Evidence(source="unknown"))

    @model_validator(mode="after")
    def consistent(self) -> "MemoryInfo":
        if self.total_bytes is not None:
            for value in (self.available_bytes, self.used_bytes):
                if value is not None and value > self.total_bytes:
                    raise ValueError("Memory counters cannot exceed installed memory")
        return self


class GPUInfo(StrictModel):
    index: int = Field(ge=0)
    vendor: str
    name: str
    dedicated_vram_bytes: Bytes | None = None
    free_vram_bytes: Bytes | None = None
    used_vram_bytes: Bytes | None = None
    shared_memory_bytes: Bytes | None = None
    driver_version: str | None = None
    compute_capability: float | None = Field(default=None, ge=0)
    gpu_type: str = "unknown"
    evidence: dict[str, Evidence] = Field(default_factory=dict)

    @model_validator(mode="after")
    def consistent(self) -> "GPUInfo":
        if self.dedicated_vram_bytes is not None:
            for value in (self.free_vram_bytes, self.used_vram_bytes):
                if value is not None and value > self.dedicated_vram_bytes:
                    raise ValueError("VRAM counters cannot exceed dedicated VRAM")
        return self


class StorageInfo(StrictModel):
    scope: str = "system drive"
    total_bytes: Bytes | None = None
    used_bytes: Bytes | None = None
    free_bytes: Bytes | None = None
    drive_type: str = "unknown"
    evidence: Evidence = Field(default_factory=lambda: Evidence(source="unknown"))

    @model_validator(mode="after")
    def consistent(self) -> "StorageInfo":
        if self.total_bytes is not None:
            for value in (self.free_bytes, self.used_bytes):
                if value is not None and value > self.total_bytes:
                    raise ValueError("Disk counters cannot exceed total storage")
        return self


class BackendInfo(StrictModel):
    status: Status = Status.UNKNOWN
    version: str | None = None
    source: str = "not probed"
    confidence: str = "unknown"
    note: str = ""


class RuntimeInfo(StrictModel):
    name: str
    installed: bool = False
    version: str | None = None
    status: Status = Status.NOT_AVAILABLE
    backends: list[str] = Field(default_factory=list)
    source: str = "executable discovery"
    note: str = ""


class HardwareScanResult(Envelope):
    platform: PlatformInfo
    cpu: CPUInfo
    memory: MemoryInfo
    gpus: list[GPUInfo] = Field(default_factory=list)
    storage: StorageInfo
    backends: dict[str, BackendInfo] = Field(default_factory=dict)
    runtimes: list[RuntimeInfo] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    probes: dict[str, Evidence] = Field(default_factory=dict)
