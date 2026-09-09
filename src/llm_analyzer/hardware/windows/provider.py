import logging
from collections.abc import Callable
from typing import Any, TypeVar

from llm_analyzer.hardware.base import ProgressCallback
from llm_analyzer.hardware.windows.backends import backend_info
from llm_analyzer.hardware.windows.cpu import cpu_info
from llm_analyzer.hardware.windows.gpu import gpu_info
from llm_analyzer.hardware.windows.memory import memory_info
from llm_analyzer.hardware.windows.storage import storage_info
from llm_analyzer.hardware.windows.system import query_cim, system_info
from llm_analyzer.runtimes.detector import detect_runtimes
from llm_analyzer.schemas.common import Confidence, Evidence, Status
from llm_analyzer.schemas.hardware import (
    BackendInfo,
    CPUInfo,
    GPUInfo,
    HardwareScanResult,
    MemoryInfo,
    RuntimeInfo,
    StorageInfo,
)
from llm_analyzer.utils.errors import AnalyzerError

logger = logging.getLogger(__name__)
T = TypeVar("T")


class WindowsHardwareProvider:
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
                # Third-party/native probe failures must not erase the rest of a scan.
                logger.warning("Probe %s failed (%s)", name, type(exc).__name__)
                probes[name] = Evidence(source=name, note=f"Probe failed: {type(exc).__name__}")
                warnings.append(f"{name} detection failed; unavailable fields remain unknown.")
                return fallback
            finally:
                if progress:
                    progress(name)

        cim: dict[str, Any] = probe("Windows CIM", query_cim, {})
        warnings.extend(cim.get("errors") or [])
        system = system_info(cim)
        cpu = probe("CPU", lambda: cpu_info(cim), CPUInfo(architecture="x86_64"))
        memory = probe("Memory", memory_info, MemoryInfo())
        gpus: list[GPUInfo] = probe("GPU", lambda: gpu_info(cim, warnings), [])
        storage = probe("Storage", storage_info, StorageInfo())
        backends: dict[str, BackendInfo] = probe("Backends", backend_info, {})
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
