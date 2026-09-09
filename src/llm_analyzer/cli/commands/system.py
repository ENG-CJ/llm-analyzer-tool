import os
import sys
from pathlib import Path

import typer
from rich.prompt import Confirm
from rich.table import Table

from llm_analyzer.benchmark import system_benchmark
from llm_analyzer.catalog.loader import load_catalog, load_rules, validate_relationships
from llm_analyzer.cli.context import state
from llm_analyzer.cli.renderers import emit_json, render_hardware
from llm_analyzer.cli.workflow import get_hardware
from llm_analyzer.config.paths import APP_DIRS, config_path, log_path, report_directory
from llm_analyzer.schemas.common import Envelope, Status
from llm_analyzer.utils.errors import AnalyzerError
from llm_analyzer.utils.files import atomic_write


def scan_command(
    ctx: typer.Context,
    output: Path | None = typer.Option(None, help="Save the versioned hardware JSON."),
    force: bool = typer.Option(False, help="Allow replacing an existing scan file."),
) -> None:
    """Scan local Windows hardware without downloading models or contacting services."""
    current = state(ctx)
    hardware = get_hardware(current)
    if output:
        try:
            atomic_write(output, hardware.model_dump_json(indent=2) + "\n", force)
        except (OSError, ValueError) as exc:
            raise AnalyzerError(
                "Cannot save hardware scan; check permissions and use --force only to overwrite", 6
            ) from exc
    if current.json:
        emit_json(hardware, current)
    else:
        render_hardware(hardware, current)


def runtimes_command(ctx: typer.Context, scan_file: Path | None = typer.Option(None)) -> None:
    """Show discovered runtimes and version confidence; no daemon connections are made."""
    current = state(ctx)
    if scan_file:
        runtimes = get_hardware(current, scan_file).runtimes
    else:
        from llm_analyzer.runtimes.detector import detect_runtimes

        runtimes = detect_runtimes()
    if current.json:
        emit_json(
            {
                **Envelope().model_dump(mode="json"),
                "runtimes": [r.model_dump(mode="json") for r in runtimes],
            },
            current,
        )
    elif not current.quiet:
        table = Table("Runtime", "Installed", "Version", "Status / limitations")
        for item in runtimes:
            table.add_row(
                item.name,
                "Yes" if item.installed else "No",
                item.version or "Unknown",
                f"{item.status.value}\n{item.note}",
            )
        current.console.print(table)


def doctor_command(
    ctx: typer.Context,
    scan_file: Path | None = typer.Option(None),
    catalog_file: Path | None = typer.Option(None),
    rules_file: Path | None = typer.Option(None),
) -> None:
    """Diagnose platform, hardware probes, catalogs, runtime discovery and output access."""
    current = state(ctx)
    checks: list[dict[str, str]] = []
    exit_code = 0
    try:
        validate_relationships(load_catalog(catalog_file), load_rules(rules_file))
        checks.append(
            {"check": "Catalog and runtime rules", "status": "available", "advice": "Validated"}
        )
    except AnalyzerError as exc:
        checks.append({"check": "Catalog and runtime rules", "status": "error", "advice": str(exc)})
        exit_code = exc.code
    try:
        hardware = get_hardware(current, scan_file)
        checks.append(
            {
                "check": "Platform",
                "status": "available"
                if hardware.platform.os == "Windows" and hardware.platform.architecture == "x86_64"
                else "unsupported",
                "advice": "Live scanner targets Windows 10/11 x64",
            }
        )
        for name, probe in hardware.probes.items():
            checks.append(
                {
                    "check": name,
                    "status": probe.status.value,
                    "advice": probe.note or "Probe completed",
                }
            )
        checks.append(
            {
                "check": "CPU capabilities",
                "status": "available" if hardware.cpu.flags_known else "unknown",
                "advice": "Use --debug to inspect CPUID probe failures",
            }
        )
        for runtime in hardware.runtimes:
            checks.append(
                {"check": runtime.name, "status": runtime.status.value, "advice": runtime.note}
            )
        for name, backend in hardware.backends.items():
            checks.append(
                {
                    "check": name,
                    "status": backend.status.value,
                    "advice": backend.note or "Runtime-specific support must also be checked",
                }
            )
        for warning in hardware.warnings:
            checks.append({"check": "Hardware warning", "status": "unknown", "advice": warning})
        if any(p.status == Status.UNKNOWN for p in hardware.probes.values()):
            checks.append(
                {
                    "check": "Remediation",
                    "status": "unknown",
                    "advice": "Review debug logs; ensure standard Windows hardware services and vendor drivers are available. Administrator access is not required.",
                }
            )
    except AnalyzerError as exc:
        checks.append({"check": "Hardware provider", "status": "error", "advice": str(exc)})
        exit_code = exit_code or exc.code
    for label, path in (("Logs", log_path().parent), ("Reports", report_directory())):
        ancestor = path
        while not ancestor.exists() and ancestor != ancestor.parent:
            ancestor = ancestor.parent
        writable = os.access(ancestor, os.W_OK)
        checks.append(
            {
                "check": label,
                "status": "available" if writable else "unknown",
                "advice": "Parent appears writable; actual writes may still fail"
                if writable
                else "Select another output location",
            }
        )
    if current.json:
        emit_json({**Envelope().model_dump(mode="json"), "checks": checks}, current)
    elif not current.quiet:
        table = Table("Check", "Status", "Advice")
        for item in checks:
            table.add_row(item["check"], item["status"], item["advice"])
        current.console.print(table)
    if exit_code:
        raise typer.Exit(exit_code)


def benchmark_command(
    ctx: typer.Context,
    yes: bool = typer.Option(
        False, "--yes", help="Explicitly authorize the bounded system benchmark."
    ),
    seconds: float = typer.Option(
        1.0, min=0.1, max=10, help="Measurement duration; no inference model is loaded."
    ),
) -> None:
    """Measure local CPU hashing throughput. This is not an LLM tokens/second benchmark."""
    current = state(ctx)
    if not yes:
        if (
            current.json
            or current.quiet
            or not sys.stdin.isatty()
            or not current.console.is_terminal
        ):
            raise AnalyzerError("Benchmark requires explicit --yes in non-interactive mode", 2)
        if not Confirm.ask(
            "Run a brief CPU hashing benchmark? No models will be loaded.",
            default=False,
            console=current.console,
        ):
            raise typer.Exit(130)
    result = system_benchmark(seconds)
    if current.json:
        emit_json(result, current)
    elif not current.quiet:
        current.console.print(
            f"Measured SHA-256 throughput: {result.throughput_mib_per_second:.1f} MiB/s over {result.elapsed_seconds:.2f} seconds"
        )
        current.console.print(result.note)


def config_show(ctx: typer.Context) -> None:
    """Show effective defaults and application file locations (paths are intentionally local)."""
    current = state(ctx)
    value = {
        **Envelope().model_dump(mode="json"),
        "settings": current.settings.model_dump(mode="json"),
        "paths": {
            "config": str(config_path()),
            "logs": str(log_path()),
            "cache": str(APP_DIRS.user_cache_path),
            "reports": str(report_directory()),
        },
    }
    if current.json:
        emit_json(value, current)
    elif not current.quiet:
        current.console.print_json(data=value)
