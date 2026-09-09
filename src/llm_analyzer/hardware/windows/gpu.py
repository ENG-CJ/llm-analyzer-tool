import csv
import io
import logging
import os
import shutil
from pathlib import Path
from typing import Any

from llm_analyzer.hardware.windows.dxgi import enumerate_dxgi
from llm_analyzer.schemas.common import Confidence, Evidence, Status
from llm_analyzer.schemas.hardware import GPUInfo
from llm_analyzer.utils.process import run_command

logger = logging.getLogger(__name__)
MIB = 1024**2


def optional_number(value: str) -> float | None:
    try:
        result = float(value.strip())
        return result if result >= 0 else None
    except ValueError:
        return None


def parse_nvidia_csv(text: str) -> list[GPUInfo]:
    gpus: list[GPUInfo] = []
    for row in csv.reader(io.StringIO(text), skipinitialspace=True):
        if not row:
            continue
        if len(row) not in {6, 7}:
            raise ValueError("Unexpected nvidia-smi CSV columns")
        index, name, total, free, used, driver = [item.strip() for item in row[:6]]
        values = [optional_number(item) for item in (total, free, used)]
        evidence = {
            key: Evidence(
                source="nvidia-smi",
                confidence=Confidence.HIGH if value is not None else Confidence.UNKNOWN,
                status=Status.AVAILABLE if value is not None else Status.UNKNOWN,
            )
            for key, value in zip(
                ("dedicated_vram_bytes", "free_vram_bytes", "used_vram_bytes"), values, strict=True
            )
        }
        evidence["identity"] = Evidence(
            source="nvidia-smi", confidence=Confidence.HIGH, status=Status.AVAILABLE
        )
        gpus.append(
            GPUInfo(
                index=int(index),
                vendor="NVIDIA",
                name=name,
                dedicated_vram_bytes=int(values[0] * MIB) if values[0] is not None else None,
                free_vram_bytes=int(values[1] * MIB) if values[1] is not None else None,
                used_vram_bytes=int(values[2] * MIB) if values[2] is not None else None,
                driver_version=driver if optional_number(driver) is not None else None,
                compute_capability=optional_number(row[6]) if len(row) == 7 else None,
                evidence=evidence,
            )
        )
    return gpus


def find_nvidia_smi() -> str | None:
    found = shutil.which("nvidia-smi")
    if found:
        return found
    for path in (
        Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32/nvidia-smi.exe",
        Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
        / "NVIDIA Corporation/NVSMI/nvidia-smi.exe",
    ):
        if path.is_file():
            return str(path)
    return None


def query_nvidia() -> list[GPUInfo]:
    executable = find_nvidia_smi()
    if not executable:
        return []
    fields = "index,name,memory.total,memory.free,memory.used,driver_version"
    result = run_command(
        [executable, f"--query-gpu={fields},compute_cap", "--format=csv,noheader,nounits"]
    )
    if not result.ok and result.error != "timed out":
        result = run_command([executable, f"--query-gpu={fields}", "--format=csv,noheader,nounits"])
    if not result.ok:
        raise OSError("nvidia-smi failed or timed out")
    return parse_nvidia_csv(result.stdout)


def cim_gpus(cim: dict[str, Any]) -> list[GPUInfo]:
    result: list[GPUInfo] = []
    for index, row in enumerate(cim.get("gpus") or []):
        name = row.get("Name") or "Unknown adapter"
        vendor_text = str(row.get("AdapterCompatibility") or name).lower()
        vendor = next(
            (v for v in ("NVIDIA", "AMD", "Intel", "Microsoft") if v.lower() in vendor_text),
            "other",
        )
        result.append(
            GPUInfo(
                index=index,
                name=name,
                vendor=vendor,
                driver_version=row.get("DriverVersion"),
                evidence={
                    "identity": Evidence(
                        source="Windows CIM", confidence=Confidence.HIGH, status=Status.AVAILABLE
                    ),
                    "dedicated_vram_bytes": Evidence(
                        source="CIM fallback",
                        note="AdapterRAM is a 32-bit field and is deliberately ignored",
                    ),
                },
            )
        )
    return result


def gpu_info(cim: dict[str, Any], warnings: list[str]) -> list[GPUInfo]:
    try:
        base = enumerate_dxgi()
    except (OSError, ValueError, AttributeError) as exc:
        logger.warning("DXGI probe failed: %s", type(exc).__name__)
        warnings.append("DXGI unavailable; using CIM adapter enumeration with unknown VRAM.")
        base = cim_gpus(cim)
    try:
        nvidia = query_nvidia()
    except (OSError, ValueError) as exc:
        logger.warning("NVIDIA probe failed: %s", type(exc).__name__)
        warnings.append("NVIDIA memory/driver query failed; dedicated/free VRAM may be unknown.")
        nvidia = []
    # Keep NVIDIA's device index domain intact. Never sum memory from separate adapters.
    remaining = list(base)
    for gpu in nvidia:
        match = next(
            (item for item in remaining if item.name.casefold() == gpu.name.casefold()), None
        )
        if match:
            gpu.shared_memory_bytes = match.shared_memory_bytes
            if "shared_memory_bytes" in match.evidence:
                gpu.evidence["shared_memory_bytes"] = match.evidence["shared_memory_bytes"]
            remaining.remove(match)
    merged = nvidia + remaining
    # DXGI supplies memory, while CIM can independently provide a Windows driver version.
    cim_adapters = cim_gpus(cim)
    for adapter in merged:
        matches = [
            entry for entry in cim_adapters if entry.name.casefold() == adapter.name.casefold()
        ]
        if len(matches) == 1 and adapter.driver_version is None:
            adapter.driver_version = matches[0].driver_version
            if adapter.driver_version:
                adapter.evidence["driver_version"] = Evidence(
                    source="Windows CIM", confidence=Confidence.HIGH, status=Status.AVAILABLE
                )
    for gpu in merged:
        if gpu.dedicated_vram_bytes is None:
            warnings.append(f"Dedicated VRAM could not be verified for {gpu.name}.")
    return merged
