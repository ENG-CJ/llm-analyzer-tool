import ctypes as ct
import re
import shutil

from llm_analyzer.schemas.common import Status
from llm_analyzer.schemas.hardware import BackendInfo
from llm_analyzer.utils.process import run_command


def backend_info() -> dict[str, BackendInfo]:
    result = {
        name: BackendInfo(note="Usability requires runtime-specific device validation")
        for name in ("cuda_driver", "cuda_toolkit", "vulkan", "directml", "hip")
    }
    try:
        driver = ct.WinDLL("nvcuda.dll", winmode=0x800)
        driver.cuInit.argtypes = [ct.c_uint]
        driver.cuInit.restype = ct.c_int
        driver.cuDriverGetVersion.argtypes = [ct.POINTER(ct.c_int)]
        driver.cuDriverGetVersion.restype = ct.c_int
        version = ct.c_int()
        usable = driver.cuInit(0) == 0 and driver.cuDriverGetVersion(ct.byref(version)) == 0
        result["cuda_driver"] = BackendInfo(
            status=Status.AVAILABLE if usable else Status.UNKNOWN,
            version=f"{version.value // 1000}.{version.value % 1000 // 10}" if usable else None,
            source="CUDA driver API cuInit/cuDriverGetVersion",
            confidence="high" if usable else "unknown",
            note="Driver API capability, not a CUDA Toolkit installation",
        )
    except OSError:
        result["cuda_driver"] = BackendInfo(
            status=Status.NOT_AVAILABLE,
            source="Windows system DLL lookup",
            note="CUDA driver DLL not found",
        )
    nvcc = shutil.which("nvcc")
    if nvcc:
        probe = run_command([nvcc, "--version"])
        match = re.search(r"release\s+(\d+\.\d+)", probe.stdout) if probe.ok else None
        result["cuda_toolkit"] = BackendInfo(
            status=Status.AVAILABLE if match else Status.UNKNOWN,
            version=match.group(1) if match else None,
            source="nvcc --version",
            confidence="high" if match else "unknown",
        )
    else:
        result["cuda_toolkit"] = BackendInfo(
            status=Status.NOT_AVAILABLE,
            source="PATH discovery",
            note="nvcc not found on PATH; Toolkit may exist elsewhere. Prebuilt runtimes may not require it.",
        )
    vulkan = shutil.which("vulkaninfo")
    if vulkan:
        probe = run_command([vulkan, "--summary"])
        verified = probe.ok and "deviceName" in probe.stdout
        result["vulkan"] = BackendInfo(
            status=Status.AVAILABLE if verified else Status.UNKNOWN,
            source="vulkaninfo --summary",
            confidence="medium" if verified else "unknown",
            note="Device enumeration only; runtime feature support and adapter mapping remain unverified",
        )
    return result
