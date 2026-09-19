from __future__ import annotations

import re
import subprocess
from pathlib import Path

from llm_analyzer.schemas.common import Confidence, Evidence, Status
from llm_analyzer.schemas.hardware import GPUInfo


def _run_lspci() -> str | None:
    try:
        result = subprocess.run(
            ["lspci", "-nnk"],
            capture_output=True,
            text=True,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None

    if result.returncode != 0:
        return None

    return result.stdout


def _vendor_from_name(name: str) -> str:
    lowered = name.lower()

    if "intel" in lowered:
        return "Intel"
    if "nvidia" in lowered:
        return "NVIDIA"
    if "amd" in lowered or "advanced micro devices" in lowered:
        return "AMD"

    return "Unknown"


def _gpu_type(vendor: str, name: str) -> str:
    lowered = name.lower()

    if vendor == "Intel":
        return "integrated"

    if "integrated" in lowered:
        return "integrated"

    return "discrete"


def _read_sysfs_memory(
    pci_address: str | None,
) -> tuple[int | None, int | None]:
    if not pci_address:
        return None, None

    device_path = Path("/sys/bus/pci/devices") / pci_address

    total_file = device_path / "mem_info_vram_total"
    used_file = device_path / "mem_info_vram_used"

    total: int | None = None
    used: int | None = None

    try:
        if total_file.exists():
            total = int(total_file.read_text().strip())
    except (OSError, ValueError):
        total = None

    try:
        if used_file.exists():
            used = int(used_file.read_text().strip())
    except (OSError, ValueError):
        used = None

    return total, used


def _parse_gpus(output: str) -> list[GPUInfo]:
    gpus: list[GPUInfo] = []

    current: dict[str, str | None] | None = None

    def finish() -> None:
        if current is None:
            return

        address = current.get("address")
        name = current.get("name") or "Unknown GPU"
        vendor = _vendor_from_name(name)

        dedicated_vram, used_vram = _read_sysfs_memory(address)

        evidence: dict[str, Evidence] = {
            "lspci": Evidence(
                source="lspci",
                confidence=Confidence.HIGH,
                status=Status.AVAILABLE,
                note="",
            )
        }

        driver = current.get("driver")

        if driver:
            evidence["kernel-driver"] = Evidence(
                source="lspci",
                confidence=Confidence.HIGH,
                status=Status.AVAILABLE,
                note=f"Kernel driver: {driver}",
            )

        if dedicated_vram is None and _gpu_type(vendor, name) == "integrated":
            evidence["memory"] = Evidence(
                source="Linux GPU sysfs",
                confidence=Confidence.MEDIUM,
                status=Status.AVAILABLE,
                note=(
                    "Integrated GPU uses shared system memory; "
                    "no fixed dedicated VRAM amount was reported."
                ),
            )

        gpus.append(
            GPUInfo(
                index=len(gpus),
                vendor=vendor,
                name=name,
                dedicated_vram_bytes=dedicated_vram,
                free_vram_bytes=(
                    max(dedicated_vram - used_vram, 0)
                    if dedicated_vram is not None and used_vram is not None
                    else None
                ),
                used_vram_bytes=used_vram,
                shared_memory_bytes=None,
                driver_version=driver,
                compute_capability=None,
                gpu_type=_gpu_type(vendor, name),
                evidence=evidence,
            )
        )

    for line in output.splitlines():
        pci_match = re.match(r"^([0-9a-fA-F:.]+)\s+(.+)$", line)

        if pci_match:
            finish()

            controller = re.match(
                r"^([0-9a-fA-F:.]+)\s+"
                r"(?:VGA compatible controller|3D controller|Display controller)"
                r"\s*(?:\[[^\]]+\])?:\s*(.+)$",
                line,
            )

            if controller:
                current = {
                    "address": controller.group(1),
                    "name": controller.group(2),
                    "driver": None,
                }
            else:
                current = None

            continue

        if current is not None:
            driver_match = re.search(
                r"Kernel driver in use:\s*(.+)$",
                line,
            )

            if driver_match:
                current["driver"] = driver_match.group(1).strip()

    finish()

    return gpus


def collect_gpus() -> list[GPUInfo]:
    output = _run_lspci()

    if not output:
        return []

    return _parse_gpus(output)