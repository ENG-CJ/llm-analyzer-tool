import json
import sys
from typing import Any

import psutil

from llm_analyzer.schemas.common import Confidence, Evidence, Status
from llm_analyzer.schemas.hardware import CPUInfo
from llm_analyzer.utils.process import run_command


def cpu_info(cim: dict[str, Any]) -> CPUInfo:
    command = [sys.executable]
    if not getattr(sys, "frozen", False):
        command += ["-m", "llm_analyzer"]
    result = run_command(command + ["--internal-cpu-probe"], timeout=12)
    data: dict[str, Any] = {}
    if result.ok:
        data = json.loads(result.stdout)
    records = cim.get("cpu") or []
    fallback = records[0] if records else {}
    relevant = {
        "avx",
        "avx2",
        "avx512f",
        "avx512bw",
        "avx512vl",
        "avx512dq",
        "avx512_vnni",
        "fma",
        "sse",
        "sse2",
        "sse3",
        "ssse3",
        "sse4_1",
        "sse4_2",
    }
    flags = sorted(
        {str(flag).lower().replace(".", "_") for flag in data.get("flags", [])} & relevant
    )
    return CPUInfo(
        vendor=data.get("vendor_id_raw") or fallback.get("Manufacturer"),
        brand=data.get("brand_raw") or fallback.get("Name"),
        architecture="x86_64",
        physical_cores=psutil.cpu_count(logical=False),
        logical_cores=psutil.cpu_count(),
        flags=flags,
        flags_known=bool(flags),
        evidence={
            "identity": Evidence(
                source="py-cpuinfo / CIM",
                confidence=Confidence.HIGH if data or fallback else Confidence.UNKNOWN,
                status=Status.AVAILABLE if data or fallback else Status.UNKNOWN,
            ),
            "flags": Evidence(
                source="py-cpuinfo CPUID",
                confidence=Confidence.HIGH if flags else Confidence.UNKNOWN,
                status=Status.AVAILABLE if flags else Status.UNKNOWN,
                note="Instruction flags are measured, never inferred from the CPU name",
            ),
            "cores": Evidence(source="psutil", confidence=Confidence.HIGH, status=Status.AVAILABLE),
        },
    )
