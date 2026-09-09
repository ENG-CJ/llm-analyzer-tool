import os

import psutil

from llm_analyzer.schemas.common import Confidence, Evidence, Status
from llm_analyzer.schemas.hardware import StorageInfo


def storage_info() -> StorageInfo:
    drive = os.environ.get("SystemDrive", "C:") + "\\"
    usage = psutil.disk_usage(drive)
    return StorageInfo(
        total_bytes=usage.total,
        used_bytes=usage.used,
        free_bytes=usage.free,
        evidence=Evidence(
            source="psutil system drive", confidence=Confidence.HIGH, status=Status.AVAILABLE
        ),
    )
