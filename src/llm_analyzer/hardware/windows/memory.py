import psutil

from llm_analyzer.schemas.common import Confidence, Evidence, Status
from llm_analyzer.schemas.hardware import MemoryInfo


def memory_info() -> MemoryInfo:
    ram, swap = psutil.virtual_memory(), psutil.swap_memory()
    return MemoryInfo(
        total_bytes=ram.total,
        available_bytes=ram.available,
        used_bytes=ram.used,
        utilization_percent=ram.percent,
        swap_total_bytes=swap.total,
        swap_free_bytes=swap.free,
        evidence=Evidence(
            source="psutil Windows memory APIs", confidence=Confidence.HIGH, status=Status.AVAILABLE
        ),
    )
