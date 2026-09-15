from __future__ import annotations

import platform

import cpuinfo

from llm_analyzer.schemas.common import Confidence, Evidence, Status
from llm_analyzer.schemas.hardware import CPUInfo


def _cpu_flags() -> tuple[list[str], bool]:
    try:
        info = cpuinfo.get_cpu_info()
    except Exception:
        return [], False

    flags = info.get("flags")

    if not isinstance(flags, list):
        return [], False

    return sorted(str(flag) for flag in flags), True


def collect_cpu() -> CPUInfo:
    try:
        info = cpuinfo.get_cpu_info()
    except Exception:
        info = {}

    flags, flags_known = _cpu_flags()

    physical_cores = info.get("count")
    logical_cores = info.get("count")

    try:
        import psutil

        physical_cores = psutil.cpu_count(logical=True) or logical_cores
        physical = psutil.cpu_count(logical=False)
        if physical is not None:
            physical_cores = physical
        logical_cores = psutil.cpu_count(logical=True) or logical_cores
    except Exception:
        pass

    return CPUInfo(
        vendor=info.get("vendor_id"),
        brand=info.get("brand_raw"),
        architecture=platform.machine(),
        physical_cores=physical_cores,
        logical_cores=logical_cores,
        flags=flags,
        flags_known=flags_known,
        frequency_mhz=None,
        evidence={
            "cpuinfo": Evidence(
                source="py-cpuinfo",
                confidence=Confidence.HIGH if info else Confidence.UNKNOWN,
                status=Status.AVAILABLE if info else Status.UNKNOWN,
                note="",
            )
        },
    )