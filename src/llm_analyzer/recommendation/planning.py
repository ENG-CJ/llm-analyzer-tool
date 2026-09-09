from dataclasses import dataclass

from llm_analyzer.catalog.schemas import RuntimeRule
from llm_analyzer.config.settings import Settings
from llm_analyzer.recommendation.compatibility import cuda_eligible
from llm_analyzer.schemas.hardware import GPUInfo, HardwareScanResult
from llm_analyzer.schemas.results import Execution, MemoryEstimate


@dataclass(frozen=True)
class ExecutionPlan:
    execution: Execution
    host_bytes: int
    device_bytes: int = 0
    safe_vram: int | None = None
    gpu: GPUInfo | None = None
    unverified_free_vram: bool = False


def choose_plan(
    hardware: HardwareScanResult,
    rule: RuntimeRule,
    memory: MemoryEstimate,
    ram_budget: int | None,
    settings: Settings,
) -> ExecutionPlan:
    cpu_plan = ExecutionPlan(Execution.CPU, memory.total_bytes)
    if ram_budget is None:
        return cpu_plan
    candidates: list[ExecutionPlan] = []
    for gpu in hardware.gpus:
        if not cuda_eligible(gpu, rule, hardware):
            continue
        # Without a free-memory measurement, total VRAM does not establish present fit.
        if gpu.free_vram_bytes is None or gpu.dedicated_vram_bytes is None:
            continue
        vram = int(
            min(gpu.free_vram_bytes, gpu.dedicated_vram_bytes)
            * (1 - settings.vram_headroom_fraction)
        )
        # Host loading must accommodate all weights, even when device execution fits.
        # This deliberately avoids relying on runtime-specific lazy mmap behavior.
        load_host = (
            memory.weights_bytes + memory.runtime_overhead_bytes + memory.working_buffers_bytes
        )
        if memory.total_bytes <= vram and load_host <= ram_budget:
            candidates.append(
                ExecutionPlan(Execution.GPU, load_host, memory.total_bytes, vram, gpu)
            )
        elif rule.partial_offload and memory.total_bytes <= ram_budget:
            # Conservative hybrid: keep full host allocation and entire KV on the host.
            offload = min(
                memory.weights_bytes,
                max(0, vram - memory.runtime_overhead_bytes - memory.working_buffers_bytes),
            )
            if offload >= memory.weights_bytes * 0.10:
                candidates.append(
                    ExecutionPlan(
                        Execution.HYBRID,
                        memory.total_bytes,
                        offload + memory.runtime_overhead_bytes + memory.working_buffers_bytes,
                        vram,
                        gpu,
                    )
                )
    if candidates:
        return min(
            candidates,
            key=lambda p: (
                p.execution != Execution.GPU,
                -p.device_bytes,
                p.gpu.index if p.gpu else 0,
            ),
        )
    return cpu_plan
