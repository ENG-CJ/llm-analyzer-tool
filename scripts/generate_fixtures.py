"""Generate synthetic, non-sensitive hardware fixtures; never inspects the host."""

from pathlib import Path

from llm_analyzer.schemas.common import Confidence, Evidence, Status
from llm_analyzer.schemas.hardware import (
    BackendInfo,
    CPUInfo,
    GPUInfo,
    HardwareScanResult,
    MemoryInfo,
    PlatformInfo,
    RuntimeInfo,
    StorageInfo,
)

GIB = 1024**3


def profile(ram: int, vram: int | None = None) -> HardwareScanResult:
    evidence = Evidence(
        source="synthetic fixture", confidence=Confidence.HIGH, status=Status.AVAILABLE
    )
    result = HardwareScanResult(
        generated_at="2026-09-09T00:00:00Z",
        platform=PlatformInfo(
            os="Windows",
            edition="Windows 11 (synthetic)",
            version="10.0",
            build="26100",
            architecture="x86_64",
            machine_architecture="AMD64",
        ),
        cpu=CPUInfo(
            brand="Synthetic x64 CPU",
            vendor="Fixture",
            architecture="x86_64",
            physical_cores=8,
            logical_cores=16,
            flags=["avx", "avx2", "fma", "sse2"],
            flags_known=True,
            evidence={"flags": evidence},
        ),
        memory=MemoryInfo(
            total_bytes=ram * GIB,
            available_bytes=int(ram * 0.75 * GIB),
            used_bytes=int(ram * 0.25 * GIB),
            utilization_percent=25,
            evidence=evidence,
        ),
        storage=StorageInfo(
            total_bytes=512 * GIB, used_bytes=256 * GIB, free_bytes=256 * GIB, evidence=evidence
        ),
        runtimes=[
            RuntimeInfo(name="ollama", installed=True, version="1.0.0", status=Status.AVAILABLE),
            RuntimeInfo(name="llama.cpp"),
        ],
        backends={
            "cuda_driver": BackendInfo(status=Status.NOT_AVAILABLE),
            "cuda_toolkit": BackendInfo(status=Status.NOT_AVAILABLE),
            "vulkan": BackendInfo(),
            "hip": BackendInfo(),
            "directml": BackendInfo(),
        },
    )
    if vram is not None:
        result.gpus = [
            GPUInfo(
                index=0,
                name=f"Synthetic NVIDIA {vram} GiB",
                vendor="NVIDIA",
                dedicated_vram_bytes=vram * GIB,
                free_vram_bytes=int(vram * 0.9 * GIB),
                used_vram_bytes=int(vram * 0.1 * GIB),
                driver_version="580.88",
                compute_capability=8.6,
                gpu_type="discrete",
                evidence={"dedicated_vram_bytes": evidence, "free_vram_bytes": evidence},
            )
        ]
        result.backends["cuda_driver"] = BackendInfo(
            status=Status.AVAILABLE,
            version="12.0",
            source="synthetic driver API",
            confidence="high",
        )
    return result


def main() -> None:
    fixtures = {
        "windows_cpu_only_8gb": profile(8),
        "windows_nvidia_4gb_16gb": profile(16, 4),
        "windows_nvidia_8gb_32gb": profile(32, 8),
        "windows_nvidia_16gb_64gb": profile(64, 16),
        "windows_nvidia_24gb_64gb": profile(64, 24),
    }
    amd = profile(32)
    amd.gpus = [
        GPUInfo(index=0, name="Synthetic AMD adapter", vendor="AMD", dedicated_vram_bytes=8 * GIB)
    ]
    fixtures["windows_amd"] = amd
    intel = profile(16)
    intel.gpus = [
        GPUInfo(
            index=0,
            name="Synthetic Intel integrated graphics",
            vendor="Intel",
            dedicated_vram_bytes=128 * 1024**2,
            shared_memory_bytes=8 * GIB,
            gpu_type="integrated",
        )
    ]
    fixtures["windows_intel_integrated"] = intel
    unknown = profile(32, 8)
    unknown.gpus[0] = GPUInfo(
        index=0,
        name="Synthetic NVIDIA unknown memory",
        vendor="NVIDIA",
        driver_version="580.88",
        compute_capability=8.6,
    )
    fixtures["windows_unknown_vram"] = unknown
    multi = profile(32, 4)
    multi.gpus.append(multi.gpus[0].model_copy(update={"index": 1}, deep=True))
    fixtures["windows_multiple_gpus"] = multi
    fixtures["windows_nvidia_no_toolkit"] = profile(32, 8)
    missing = profile(16)
    missing.runtimes = [RuntimeInfo(name="ollama"), RuntimeInfo(name="llama.cpp")]
    fixtures["windows_no_ollama"] = missing
    fixtures["windows_ollama_installed"] = profile(16, 4)
    low_disk = profile(32, 8)
    low_disk.storage = StorageInfo(total_bytes=512 * GIB, free_bytes=10 * 1024**2)
    fixtures["windows_low_disk"] = low_disk
    low_ram = profile(64, 24)
    low_ram.memory = MemoryInfo(total_bytes=64 * GIB, available_bytes=512 * 1024**2)
    fixtures["windows_low_available_ram"] = low_ram
    target = Path(__file__).resolve().parents[1] / "tests/fixtures"
    target.mkdir(parents=True, exist_ok=True)
    for name, fixture in fixtures.items():
        (target / f"{name}.json").write_text(
            fixture.model_dump_json(indent=2) + "\n", encoding="utf-8"
        )


if __name__ == "__main__":
    main()
