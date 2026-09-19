from __future__ import annotations

import psutil

from llm_analyzer.schemas.common import Confidence, Evidence, Status
from llm_analyzer.schemas.hardware import StorageInfo


def collect_storage() -> StorageInfo:
    usage = psutil.disk_usage("/")

    return StorageInfo(
        scope="/",
        total_bytes=usage.total,
        used_bytes=usage.used,
        free_bytes=usage.free,
        drive_type="unknown",
        evidence=Evidence(
            source="psutil",
            confidence=Confidence.HIGH,
            status=Status.AVAILABLE,
            note="",
        ),
    )