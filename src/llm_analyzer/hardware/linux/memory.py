from __future__ import annotations

import psutil

from llm_analyzer.schemas.common import Confidence, Evidence, Status
from llm_analyzer.schemas.hardware import MemoryInfo


def collect_memory() -> MemoryInfo:
    memory = psutil.virtual_memory()
    swap = psutil.swap_memory()

    return MemoryInfo(
        total_bytes=memory.total,
        available_bytes=memory.available,
        used_bytes=memory.used,
        utilization_percent=memory.percent,
        swap_total_bytes=swap.total,
        swap_free_bytes=swap.free,
        evidence=Evidence(
            source="psutil",
            confidence=Confidence.HIGH,
            status=Status.AVAILABLE,
            note="",
        ),
    )