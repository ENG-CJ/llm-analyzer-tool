import logging
import sys
from pathlib import Path

import typer
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm, Prompt

from llm_analyzer.catalog.loader import load_catalog, load_rules
from llm_analyzer.cli.context import CLIState
from llm_analyzer.cli.renderers import emit_json, render_analysis, render_hardware
from llm_analyzer.config.settings import Priority, ReportFormat, UseCase
from llm_analyzer.hardware.scanner import read_scan, scan_hardware
from llm_analyzer.recommendation.engine import analyze
from llm_analyzer.reports.generator import save_report
from llm_analyzer.schemas.hardware import HardwareScanResult
from llm_analyzer.schemas.results import AnalysisRequest
from llm_analyzer.utils.errors import AnalyzerError

logger = logging.getLogger(__name__)


def get_hardware(state: CLIState, scan_file: Path | None = None) -> HardwareScanResult:
    if scan_file:
        return read_scan(scan_file)
    enabled = state.console.is_terminal and not (state.json or state.quiet or state.no_progress)
    with Progress(
        SpinnerColumn(),
        TextColumn("{task.description}"),
        console=state.console,
        disable=not enabled,
    ) as progress:
        task = progress.add_task("Scanning Windows hardware...", total=7)

        def completed(name: str) -> None:
            progress.update(task, advance=1, description=f"Completed: {name}")

        return scan_hardware(progress=completed)


def run_analysis(
    state: CLIState,
    *,
    use_case: UseCase | None = None,
    priority: Priority | None = None,
    context: int | None = None,
    top: int | None = None,
    runtime: str = "auto",
    scan_file: Path | None = None,
    model_id: str | None = None,
    quant: str | None = None,
    interactive: bool = False,
    save: bool = False,
    report_format: ReportFormat | None = None,
    output: str | None = None,
    force: bool = False,
    catalog_file: Path | None = None,
    rules_file: Path | None = None,
    show_hardware: bool = False,
) -> None:
    settings = state.settings
    interactive = interactive and not (state.json or state.quiet)
    if interactive and (not sys.stdin.isatty() or not state.console.is_terminal):
        raise AnalyzerError(
            "Interactive mode requires a terminal; provide command-line options instead", 2
        )
    hardware = get_hardware(state, scan_file)
    if (interactive or show_hardware) and not state.json:
        render_hardware(hardware, state)
    if interactive:
        use_case = UseCase(
            Prompt.ask(
                "What will you use local AI for?",
                choices=[value.value for value in UseCase],
                default=(use_case or settings.default_use_case).value,
                console=state.console,
            )
        )
        priority = Priority(
            Prompt.ask(
                "What should we prioritize?",
                choices=[value.value for value in Priority],
                default=(priority or settings.default_priority).value,
                console=state.console,
            )
        )
        while True:
            value = Prompt.ask(
                "Target context (auto, 4k, 8k, 16k, 32k, or token count)",
                default="auto",
                console=state.console,
            )
            try:
                normalized = value.strip().lower()
                context = (
                    settings.default_context
                    if normalized == "auto"
                    else int(normalized[:-1]) * 1024
                    if normalized.endswith("k")
                    else int(normalized)
                )
                if 128 <= context <= 1048576:
                    break
            except ValueError:
                pass
            state.console.print("Enter a context between 128 and 1,048,576 tokens.", style="yellow")
    request = AnalysisRequest(
        use_case=use_case or settings.default_use_case,
        priority=priority or settings.default_priority,
        context=context or settings.default_context,
        top=top or settings.top_recommendations,
        runtime=runtime,
        model_id=model_id,
        quant=quant.upper() if quant else None,
    )
    result = analyze(
        hardware, load_catalog(catalog_file), load_rules(rules_file), request, settings
    )
    if state.json:
        emit_json(result, state)
    else:
        render_analysis(result, state)
    if interactive and not (save or output):
        save = Confirm.ask("Save a detailed report?", default=True, console=state.console)
        if save:
            report_format = ReportFormat(
                Prompt.ask(
                    "Report format",
                    choices=[f.value for f in ReportFormat],
                    default=settings.default_report_format.value,
                    console=state.console,
                )
            )
            output = (
                Prompt.ask(
                    "Output path (leave empty for Documents)", default="", console=state.console
                )
                or None
            )
    if save or output:
        path = save_report(result, report_format or settings.default_report_format, output, force)
        logger.info(
            "Report saved successfully (%s)",
            (report_format or settings.default_report_format).value,
        )
        if not state.quiet:
            typer.echo(f"Report saved: {path}", err=state.json)
