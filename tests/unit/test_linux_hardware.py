from types import SimpleNamespace

from llm_analyzer.hardware.linux.backends import detect_backends
from llm_analyzer.hardware.linux.cpu import collect_cpu
from llm_analyzer.hardware.linux.gpu import collect_gpus
from llm_analyzer.hardware.linux.memory import collect_memory
from llm_analyzer.hardware.linux.provider import LinuxHardwareProvider
from llm_analyzer.hardware.linux.storage import collect_storage


def test_linux_provider_detects_cpu_and_memory():
    result = LinuxHardwareProvider().scan()

    assert result.cpu.logical_cores >= 1
    assert result.cpu.physical_cores >= 1
    assert result.memory.total_bytes > 0


def test_linux_cpu_module():
    cpu = collect_cpu()

    assert cpu.architecture
    assert cpu.logical_cores >= 1


def test_linux_memory_module():
    memory = collect_memory()

    assert memory.total_bytes > 0
    assert memory.available_bytes >= 0


def test_linux_storage_module():
    storage = collect_storage()

    assert storage.total_bytes > 0
    assert storage.free_bytes >= 0


def test_linux_gpu_module():
    gpus = collect_gpus()

    assert isinstance(gpus, list)


def test_linux_provider_detects_intel_gpu():
    result = LinuxHardwareProvider().scan()

    intel_gpus = [
        gpu for gpu in result.gpus
        if gpu.vendor == "Intel"
    ]

    assert intel_gpus

    gpu = intel_gpus[0]

    assert gpu.gpu_type == "integrated"
    assert gpu.driver_version == "i915"


def test_linux_provider_handles_missing_lspci(monkeypatch):
    monkeypatch.setattr(
        "llm_analyzer.hardware.linux.gpu.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=1,
            stdout="",
            stderr="",
        ),
    )

    assert collect_gpus() == []


def test_linux_provider_detects_backends(monkeypatch):
    def fake_which(command):
        return {
            "vulkaninfo": "/usr/bin/vulkaninfo",
            "nvidia-smi": None,
            "nvcc": None,
            "rocminfo": None,
        }.get(command)

    vulkan_output = """
GPU0:
    deviceType = PHYSICAL_DEVICE_TYPE_INTEGRATED_GPU
    deviceName = Intel(R) UHD Graphics 620 (WHL GT2)

GPU1:
    deviceType = PHYSICAL_DEVICE_TYPE_CPU
    deviceName = llvmpipe (LLVM 19.1.7, 256 bits)
"""

    monkeypatch.setattr(
        "llm_analyzer.hardware.linux.backends.shutil.which",
        fake_which,
    )

    monkeypatch.setattr(
        "llm_analyzer.hardware.linux.backends.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout=vulkan_output,
            stderr="",
        ),
    )

    backends = detect_backends()

    assert backends["vulkan"].status == "available"
    assert backends["cuda_driver"].status == "not_available"
    assert backends["cuda_toolkit"].status == "not_available"
    assert backends["directml"].status == "not_available"
    assert backends["hip"].status == "not_available"