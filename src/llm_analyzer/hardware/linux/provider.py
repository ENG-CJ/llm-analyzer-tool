from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TypeVar

from llm_analyzer.hardware.base import ProgressCallback
from llm_analyzer.hardware.linux.backends import detect_backends
from llm_analyzer.hardware.linux.cpu import collect_cpu
from llm_analyzer.hardware.linux.gpu import collect_gpus
from llm_analyzer.hardware.linux.memory import collect_memory
from llm_analyzer.hardware.linux.storage import collect_storage
from llm_analyzer.hardware.linux.system import collect_platform
from llm_analyzer.runtimes.detector import detect_runtimes
from llm_analyzer.schemas.common import Confidence, Evidence, Status
from llm_analyzer.schemas.hardware import (
    BackendInfo,
    CPUInfo,
    GPUInfo,
    HardwareScanResult,
    MemoryInfo,
    PlatformInfo,
    RuntimeInfo,
    StorageInfo,
)
from llm_analyzer.utils.errors import AnalyzerError

logger = logging.getLogger(__name__)
T = TypeVar("T")


class LinuxHardwareProvider:
    def scan(self, progress: ProgressCallback | None = None) -> HardwareScanResult:
        warnings: list[str] = []
        probes: dict[str, Evidence] = {}

        def probe(name: str, action: Callable[[], T], fallback: T) -> T:
            try:
                value = action()
                probes[name] = Evidence(
                    source=name, confidence=Confidence.HIGH, status=Status.AVAILABLE
                )
                logger.info("Probe completed: %s", name)
                return value
            except Exception as exc:
                logger.warning("Probe %s failed (%s)", name, type(exc).__name__)
                probes[name] = Evidence(source=name, note=f"Probe failed: {type(exc).__name__}")
                warnings.append(f"{name} detection failed; unavailable fields remain unknown.")
                return fallback
            finally:
                if progress:
                    progress(name)

        system: PlatformInfo = probe("Linux Platform", collect_platform, PlatformInfo(os="Linux"))
        cpu: CPUInfo = probe("CPU", collect_cpu, CPUInfo(architecture="x86_64"))
        memory: MemoryInfo = probe("Memory", collect_memory, MemoryInfo())
        gpus: list[GPUInfo] = probe("GPU", collect_gpus, [])
        storage: StorageInfo = probe("Storage", collect_storage, StorageInfo())
        backends: dict[str, BackendInfo] = probe("Backends", detect_backends, {})
        runtimes: list[RuntimeInfo] = probe("Runtimes", detect_runtimes, [])

        if memory.total_bytes is None:
            raise AnalyzerError("Physical memory query failed; run doctor for diagnostics", 4)
        if memory.available_bytes is not None and memory.available_bytes < memory.total_bytes * 0.3:
            warnings.append(
                "Available RAM is much lower than installed RAM. Close memory-heavy applications and rescan."
            )
        if not cpu.flags_known:
            warnings.append("CPU instruction capabilities could not be verified.")

        return HardwareScanResult(
            platform=system,
            cpu=cpu,
            memory=memory,
            gpus=gpus,
            storage=storage,
            backends=backends,
            runtimes=runtimes,
            warnings=warnings,
            probes=probes,
        )