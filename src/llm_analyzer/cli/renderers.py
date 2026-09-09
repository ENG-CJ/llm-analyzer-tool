import json
from typing import Any

from pydantic import BaseModel
from rich import box
from rich.panel import Panel
from rich.table import Table

from llm_analyzer.cli.context import CLIState
from llm_analyzer.reports.generator import gib
from llm_analyzer.schemas.hardware import HardwareScanResult
from llm_analyzer.schemas.results import AnalysisResult, ModelRecommendation

COLORS = {
    "EXCELLENT": "green",
    "GOOD": "cyan",
    "BORDERLINE": "yellow",
    "NOT_RECOMMENDED": "red",
    "UNKNOWN": "yellow",
}


def emit_json(value: BaseModel | dict[str, Any], state: CLIState) -> None:
    text = (
        value.model_dump_json(indent=2)
        if isinstance(value, BaseModel)
        else json.dumps(value, ensure_ascii=True, indent=2)
    )
    # Plain write avoids Rich wrapping and ANSI, even with forced-color environments.
    state.console.file.write(text + "\n")
    state.console.file.flush()


def render_hardware(hw: HardwareScanResult, state: CLIState) -> None:
    if state.quiet:
        return
    table = Table("Component", "Detected", box=box.SIMPLE, expand=True)
    rows = [
        ("Operating system", f"{hw.platform.edition or hw.platform.os} {hw.platform.architecture}"),
        ("CPU", hw.cpu.brand or "Unknown"),
        (
            "Cores",
            f"{hw.cpu.physical_cores or '?'} physical / {hw.cpu.logical_cores or '?'} logical",
        ),
        (
            "CPU flags",
            ", ".join(
                flag for flag in hw.cpu.flags if flag in {"avx", "avx2", "avx512f", "fma", "sse2"}
            )
            if hw.cpu.flags_known
            else "Unknown",
        ),
        ("Installed RAM", gib(hw.memory.total_bytes)),
        ("Available RAM", gib(hw.memory.available_bytes)),
        ("Storage free", gib(hw.storage.free_bytes)),
    ]
    for gpu in hw.gpus:
        rows += [
            ("GPU", gpu.name),
            (
                "Dedicated / free VRAM",
                f"{gib(gpu.dedicated_vram_bytes)} / {gib(gpu.free_vram_bytes)}",
            ),
            ("Driver", gpu.driver_version or "Unknown"),
        ]
    if not hw.gpus:
        rows.append(("GPU", "No adapters reported; see probe status for detection failures"))
    for name, backend in hw.backends.items():
        rows.append(
            (name.replace("_", " ").title(), f"{backend.status.value} {backend.version or ''}")
        )
    for runtime in hw.runtimes:
        rows.append(
            (
                runtime.name,
                f"{'Installed' if runtime.installed else 'Not found'}; {runtime.version or 'version unknown'}; {runtime.status.value}",
            )
        )
    for label, value in rows:
        table.add_row(label, value)
    state.console.print(Panel(table, title="Hardware profile", border_style="cyan"))
    for warning in hw.warnings:
        state.console.print(f"Warning: {warning}", style="yellow")


def render_recommendation(item: ModelRecommendation, state: CLIState) -> None:
    lines = [
        f"{item.fit.value} | {item.quantization} | {item.runtime} | {item.execution.value}",
        f"Context {item.context:,} | confidence {item.confidence.value} | runtime {item.runtime_compatibility}",
        f"Weights ~{gib(item.memory.weights_bytes)} | KV ~{gib(item.memory.kv_cache_bytes)} | total ~{gib(item.memory.total_bytes)}",
        f"Host ~{gib(item.estimated_host_bytes)} / safe RAM {gib(item.safe_ram_bytes)}",
        f"Device ~{gib(item.estimated_device_bytes)} / safe VRAM {gib(item.safe_vram_bytes)}",
    ]
    symbols = {"pass": "+", "warning": "!", "fail": "x", "unknown": "?", "info": "i"}
    lines.extend(f"{symbols[reason.level]} {reason.message}" for reason in item.reasons)
    state.console.print(
        Panel("\n".join(lines), title=item.display_name, border_style=COLORS[item.fit.value])
    )


def render_analysis(analysis: AnalysisResult, state: CLIState) -> None:
    if state.quiet:
        return
    result = analysis.result
    state.console.print(
        Panel(
            f"{result.capability_summary}\n{result.request.use_case.value} | {result.request.priority.value} | {result.request.context:,} tokens",
            title="Best local LLM options",
            border_style="cyan",
        )
    )
    for item in result.recommendations:
        render_recommendation(item, state)
    for label, items in (
        ("Unknown configurations", result.unknown),
        ("Not recommended", result.rejected),
    ):
        if items:
            state.console.print(label, style="bold")
            for item in items:
                if result.request.model_id:
                    render_recommendation(item, state)
                else:
                    reasons = "; ".join(
                        r.message for r in item.reasons if r.level in {"fail", "unknown"}
                    )
                    state.console.print(f"  {item.model_id}: {reasons}")
    if result.generic_capacity:
        table = Table("Generic capacity estimate", "Quant", "Fit", "Memory", box=box.SIMPLE)
        for item in result.generic_capacity:
            table.add_row(
                item.model_id, item.quantization, item.fit.value, "~" + gib(item.memory.total_bytes)
            )
        state.console.print(table)
        state.console.print(
            "Generic profiles are hypothetical capacity estimates, not verified model recommendations.",
            style="dim",
        )
    for warning in result.warnings:
        state.console.print(f"Warning: {warning}", style="yellow")
    state.console.print(analysis.methodology, style="dim")
