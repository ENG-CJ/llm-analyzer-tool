import html
from datetime import UTC, datetime
from pathlib import Path

from llm_analyzer.config.paths import report_directory
from llm_analyzer.config.settings import ReportFormat
from llm_analyzer.schemas.results import AnalysisResult, ModelRecommendation
from llm_analyzer.utils.errors import AnalyzerError
from llm_analyzer.utils.files import atomic_write

EXTENSIONS = {
    ReportFormat.MARKDOWN: ".md",
    ReportFormat.JSON: ".json",
    ReportFormat.TEXT: ".txt",
    ReportFormat.HTML: ".html",
}


def gib(value: int | None) -> str:
    return "Unknown" if value is None else f"{value / 1024**3:.2f} GiB"


def hardware_summary(analysis: AnalysisResult) -> str:
    hw = analysis.hardware
    lines = [
        f"OS: {hw.platform.edition or hw.platform.os}; version {hw.platform.version or 'unknown'}; build {hw.platform.build or 'unknown'}",
        f"Architecture: {hw.platform.architecture}; native: {hw.platform.machine_architecture}",
        f"System: {hw.platform.manufacturer or 'unknown'} / {hw.platform.model or 'unknown'}",
        f"CPU: {hw.cpu.brand or 'unknown'}; vendor: {hw.cpu.vendor or 'unknown'}",
        f"Cores: {hw.cpu.physical_cores or 'unknown'} physical / {hw.cpu.logical_cores or 'unknown'} logical",
        f"Instruction flags: {', '.join(hw.cpu.flags) if hw.cpu.flags_known else 'unknown'}",
        f"CPU frequency: {str(hw.cpu.frequency_mhz) + ' MHz' if hw.cpu.frequency_mhz else 'unknown'}",
        f"RAM installed: {gib(hw.memory.total_bytes)}; currently available: {gib(hw.memory.available_bytes)}; used: {gib(hw.memory.used_bytes)}",
        f"RAM evidence: {hw.memory.evidence.source} ({hw.memory.evidence.confidence.value})",
        f"Pagefile/swap total: {gib(hw.memory.swap_total_bytes)}; free: {gib(hw.memory.swap_free_bytes)} (not counted as physical capacity)",
        f"Storage ({hw.storage.scope}): total {gib(hw.storage.total_bytes)}; used {gib(hw.storage.used_bytes)}; free {gib(hw.storage.free_bytes)}",
        f"Storage type: {hw.storage.drive_type}; source: {hw.storage.evidence.source}",
    ]
    for gpu in hw.gpus:
        lines.extend(
            [
                "",
                f"GPU {gpu.index}: {gpu.vendor} / {gpu.name}; type: {gpu.gpu_type}",
                f"Dedicated VRAM: {gib(gpu.dedicated_vram_bytes)}; free: {gib(gpu.free_vram_bytes)}; used: {gib(gpu.used_vram_bytes)}",
                f"Shared-system memory limit: {gib(gpu.shared_memory_bytes)} (not dedicated VRAM)",
                f"Driver: {gpu.driver_version or 'unknown'}; compute capability: {gpu.compute_capability if gpu.compute_capability is not None else 'unknown'}",
            ]
        )
        lines.extend(
            f"Evidence {field}: {evidence.source}; {evidence.status.value}; {evidence.confidence.value} confidence"
            for field, evidence in gpu.evidence.items()
        )
    if not hw.gpus:
        lines.append("No GPU adapters reported; review probe status before assuming none exist.")
    lines.append("\nAcceleration probes")
    for name, backend in hw.backends.items():
        lines.append(
            f"{name}: {backend.status.value}; version {backend.version or 'unknown'}; source {backend.source}. {backend.note}"
        )
    lines.append("\nRuntime discovery")
    for runtime in hw.runtimes:
        lines.append(
            f"{runtime.name}: {'installed' if runtime.installed else 'not found'}; version {runtime.version or 'unknown'}; status {runtime.status.value}. {runtime.note}"
        )
    lines.append("\nProbe status")
    lines.extend(f"{name}: {probe.status.value}. {probe.note}" for name, probe in hw.probes.items())
    return "\n".join(lines)


def recommendation_lines(item: ModelRecommendation) -> list[str]:
    lines = [
        f"{item.display_name} / {item.quantization}: {item.fit.value}",
        f"Runtime: {item.runtime} ({item.runtime_compatibility}); installed: {item.runtime_installed}",
        f"Execution plan: {item.execution.value}; backend: {item.backend}; context: {item.context}",
        f"Confidence: {item.confidence.value}; qualitative performance: {item.performance_class} ({item.performance_confidence.value} confidence)",
        f"Weights: ~{gib(item.memory.weights_bytes)}; KV cache: ~{gib(item.memory.kv_cache_bytes)}",
        f"Runtime overhead: ~{gib(item.memory.runtime_overhead_bytes)}; buffers: ~{gib(item.memory.working_buffers_bytes)}",
        f"Total execution estimate: ~{gib(item.memory.total_bytes)}; disk requirement: ~{gib(item.memory.storage_required_bytes)}",
        f"Host estimate: ~{gib(item.estimated_host_bytes)}; safe RAM: {gib(item.safe_ram_bytes)}",
        f"Device estimate: ~{gib(item.estimated_device_bytes)}; safe VRAM: {gib(item.safe_vram_bytes)}",
    ]
    if item.gpu_name:
        lines.append(f"GPU: {item.gpu_name} (index {item.gpu_index})")
    lines.extend(f"[{reason.level.upper()}] {reason.message}" for reason in item.reasons)
    lines.extend(f"Assumption: {assumption}" for assumption in item.memory.assumptions)
    return lines


def report_sections(analysis: AnalysisResult) -> list[tuple[str, str]]:
    hw, result = analysis.hardware, analysis.result
    sections = [
        (
            "Overview",
            f"Local LLM Analyzer {analysis.application_version}\nGenerated: {analysis.generated_at.isoformat()}\nHardware captured: {hw.generated_at.isoformat()}\n{result.capability_summary}\n{result.capability_reason}",
        ),
        (
            "Request",
            f"Use case: {result.request.use_case.value}\nPriority: {result.request.priority.value}\nContext: {result.request.context}\nRuntime preference: {result.request.runtime}",
        ),
        ("Hardware", hardware_summary(analysis)),
        (
            "Recommendations",
            "\n\n".join("\n".join(recommendation_lines(item)) for item in result.recommendations)
            or "No named recommendation meets the requested constraints.",
        ),
        (
            "Rejected models",
            "\n\n".join("\n".join(recommendation_lines(item)) for item in result.rejected)
            or "None.",
        ),
        (
            "Unknown configurations",
            "\n\n".join("\n".join(recommendation_lines(item)) for item in result.unknown)
            or "None.",
        ),
        (
            "Generic capacity estimates",
            "\n\n".join("\n".join(recommendation_lines(item)) for item in result.generic_capacity)
            or "None selected.",
        ),
        ("Warnings", "\n".join(result.warnings) or "None."),
        ("Methodology", analysis.methodology),
        (
            "Reproducibility",
            f"Catalog: {result.catalog_version}\nSHA-256: {result.catalog_sha256}\nRuntime rules: {result.rules_version}\nSHA-256: {result.rules_sha256}\nEvaluated configurations: {len(result.evaluated_configurations)}\nSettings:\n{analysis.settings.model_dump_json(indent=2)}\nExport JSON for all per-runtime/per-quantization evaluations.",
        ),
    ]
    return sections


def render_report(analysis: AnalysisResult, format: ReportFormat) -> str:
    if format == ReportFormat.JSON:
        return analysis.model_dump_json(indent=2) + "\n"
    sections = report_sections(analysis)
    if format == ReportFormat.HTML:
        body = "".join(
            f"<section><h2>{html.escape(title)}</h2><pre>{html.escape(content)}</pre></section>"
            for title, content in sections
        )
        return (
            '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Local LLM Analysis</title><style>body{font:16px/1.6 system-ui,sans-serif;background:#f4f7fa;color:#182a3a;max-width:1050px;margin:40px auto;padding:0 24px}h1{font-size:36px;letter-spacing:-1px}h2{color:#096779;font-size:22px}section{background:white;padding:20px 28px;margin:20px 0;border:1px solid #d6e0e7;border-radius:12px}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:14px/1.65 ui-monospace,Consolas,monospace}@media print{body{background:white;margin:0}section{break-inside:auto;border:0;padding:0}}</style><h1>Local LLM Analysis</h1><p>Local hardware. Explainable recommendations. Explicit uncertainty.</p>'
            + body
            + "</html>\n"
        )
    if format == ReportFormat.MARKDOWN:
        # Indented blocks preserve untrusted model/hardware text literally in Markdown.
        return (
            "# Local LLM Analysis\n\n"
            + "\n\n".join(
                f"## {title}\n\n" + "\n".join("    " + line for line in content.splitlines())
                for title, content in sections
            )
            + "\n"
        )
    return (
        "LOCAL LLM ANALYSIS\n\n"
        + "\n\n".join(
            f"{title.upper()}\n{'=' * len(title)}\n{content}" for title, content in sections
        )
        + "\n"
    )


def resolve_report_path(output: str | None, format: ReportFormat) -> Path:
    filename = f"llm-analysis-{datetime.now(UTC):%Y%m%d-%H%M%S-%f}{EXTENSIONS[format]}"
    if output is None:
        return report_directory() / filename
    path = Path(output).expanduser()
    if path.is_dir() or output.endswith(("/", "\\")):
        return path / filename
    return path


def save_report(
    analysis: AnalysisResult, format: ReportFormat, output: str | None, force: bool = False
) -> Path:
    try:
        return atomic_write(
            resolve_report_path(output, format), render_report(analysis, format), force
        )
    except (OSError, ValueError) as exc:
        message = (
            "Output already exists; choose another path or use --force"
            if isinstance(exc, FileExistsError)
            else "Could not write report; check the output path and permissions"
        )
        raise AnalyzerError(message, 6) from exc
