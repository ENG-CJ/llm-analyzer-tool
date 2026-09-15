from __future__ import annotations

import re
import shutil
import subprocess

from llm_analyzer.schemas.common import Status
from llm_analyzer.schemas.hardware import BackendInfo


def _run_command(command: list[str]) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None


def _not_available(source: str, note: str) -> BackendInfo:
    return BackendInfo(
        status=Status.NOT_AVAILABLE,
        version=None,
        source=source,
        confidence="unknown",
        note=note,
    )


def detect_backends() -> dict[str, BackendInfo]:
    backends: dict[str, BackendInfo] = {}

    # CUDA driver
    if shutil.which("nvidia-smi"):
        result = _run_command(
            [
                "nvidia-smi",
                "--query-gpu=driver_version",
                "--format=csv,noheader",
            ]
        )

        version = None
        if result and result.returncode == 0:
            version = result.stdout.strip().splitlines()[0] or None

        backends["cuda_driver"] = BackendInfo(
            status=Status.AVAILABLE if version else Status.UNKNOWN,
            version=version,
            source="nvidia-smi",
            confidence="high" if version else "unknown",
            note="",
        )
    else:
        backends["cuda_driver"] = _not_available(
            "PATH discovery",
            "nvidia-smi not found on PATH",
        )

    # CUDA toolkit
    if shutil.which("nvcc"):
        result = _run_command(["nvcc", "--version"])

        version = None

        if result and result.returncode == 0:
            match = re.search(
                r"release\s+([0-9.]+)",
                result.stdout,
            )
            if match:
                version = match.group(1)

        backends["cuda_toolkit"] = BackendInfo(
            status=Status.AVAILABLE if version else Status.UNKNOWN,
            version=version,
            source="nvcc",
            confidence="high" if version else "unknown",
            note="",
        )
    else:
        backends["cuda_toolkit"] = _not_available(
            "PATH discovery",
            "nvcc not found on PATH; Toolkit may exist elsewhere.",
        )

    # Vulkan
    if shutil.which("vulkaninfo"):
        result = _run_command(["vulkaninfo", "--summary"])

        if result and result.returncode == 0:
            output = result.stdout

            has_gpu = bool(
                re.search(
                    r"PHYSICAL_DEVICE_TYPE_(?:DISCRETE|INTEGRATED)_GPU",
                    output,
                )
            )

            backends["vulkan"] = BackendInfo(
                status=Status.AVAILABLE if has_gpu else Status.UNKNOWN,
                version=None,
                source="vulkaninfo",
                confidence="high" if has_gpu else "unknown",
                note="",
            )
        else:
            backends["vulkan"] = _not_available(
                "vulkaninfo",
                "vulkaninfo failed",
            )
    else:
        backends["vulkan"] = _not_available(
            "PATH discovery",
            "vulkaninfo not found on PATH",
        )

    # DirectML is Windows-only.
    backends["directml"] = BackendInfo(
        status=Status.NOT_AVAILABLE,
        version=None,
        source="platform",
        confidence="high",
        note="DirectML is not available on Linux.",
    )

    # ROCm / HIP
    if shutil.which("rocminfo"):
        result = _run_command(["rocminfo"])

        available = bool(
            result
            and result.returncode == 0
            and result.stdout.strip()
        )

        backends["hip"] = BackendInfo(
            status=Status.AVAILABLE if available else Status.UNKNOWN,
            version=None,
            source="rocminfo",
            confidence="high" if available else "unknown",
            note="",
        )
    else:
        backends["hip"] = _not_available(
            "PATH discovery",
            "rocminfo not found on PATH",
        )

    return backends