import os
import platform
import struct
from pathlib import Path

from pydantic import ValidationError

from llm_analyzer.hardware.base import HardwareProvider, ProgressCallback
from llm_analyzer.schemas.hardware import HardwareScanResult
from llm_analyzer.utils.errors import AnalyzerError
from llm_analyzer.utils.files import read_json


def read_scan(path: Path) -> HardwareScanResult:
    try:
        return HardwareScanResult.model_validate(read_json(path))
    except (OSError, ValueError, ValidationError) as exc:
        raise AnalyzerError("Invalid saved hardware scan; expected schema version 1.0", 2) from exc


def scan_hardware(
    provider: HardwareProvider | None = None, progress: ProgressCallback | None = None
) -> HardwareScanResult:
    if provider is None:
        if (
            platform.system() != "Windows"
            or platform.release() not in {"10", "11"}
            or platform.machine().lower() not in {"amd64", "x86_64"}
            or os.environ.get("PROCESSOR_ARCHITEW6432", "").lower() == "arm64"
            or struct.calcsize("P") != 8
        ):
            raise AnalyzerError(
                "Live scanning requires Windows 10/11 x64; use --scan-file for offline analysis", 3
            )
        from llm_analyzer.hardware.windows.provider import WindowsHardwareProvider

        provider = WindowsHardwareProvider()
    return provider.scan(progress)
