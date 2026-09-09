import json
import os
import platform
from pathlib import Path
from typing import Any

from llm_analyzer.schemas.hardware import PlatformInfo
from llm_analyzer.utils.process import run_command

# Only selected non-sensitive fields are queried. No network, serials or user identifiers.
CIM_SCRIPT = """
$ErrorActionPreference='Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$result = @{}
$errors = @()
try { $result.system = Get-CimInstance Win32_ComputerSystem | Select-Object Manufacturer,Model,SystemType } catch { $errors += 'system CIM unavailable' }
try { $result.os = Get-CimInstance Win32_OperatingSystem | Select-Object Caption,Version,BuildNumber } catch { $errors += 'OS CIM unavailable' }
try { $result.cpu = @(Get-CimInstance Win32_Processor | Select-Object Name,Manufacturer) } catch { $errors += 'CPU CIM unavailable' }
try { $result.gpus = @(Get-CimInstance Win32_VideoController | Select-Object Name,AdapterCompatibility,DriverVersion) } catch { $errors += 'GPU CIM unavailable' }
$result.errors = $errors
$result | ConvertTo-Json -Depth 4 -Compress
"""


def query_cim() -> dict[str, Any]:
    executable = (
        Path(os.environ.get("SystemRoot", r"C:\Windows"))
        / "System32/WindowsPowerShell/v1.0/powershell.exe"
    )
    result = run_command(
        [str(executable), "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", CIM_SCRIPT],
        timeout=15,
    )
    if not result.ok:
        raise OSError("Windows CIM query unavailable or timed out")
    parsed = json.loads(result.stdout)
    if not isinstance(parsed, dict):
        raise ValueError("Unexpected CIM result")
    return parsed


def system_info(cim: dict[str, Any]) -> PlatformInfo:
    system, os_info = cim.get("system") or {}, cim.get("os") or {}
    native = (
        os.environ.get("PROCESSOR_ARCHITEW6432")
        or os.environ.get("PROCESSOR_ARCHITECTURE")
        or platform.machine()
    )
    return PlatformInfo(
        os="Windows",
        version=os_info.get("Version") or platform.version(),
        build=os_info.get("BuildNumber"),
        edition=os_info.get("Caption"),
        architecture="x86_64"
        if platform.machine().lower() in {"amd64", "x86_64"}
        else platform.machine(),
        machine_architecture=native,
        manufacturer=system.get("Manufacturer"),
        model=system.get("Model"),
    )
