from pathlib import Path

import typer

from llm_analyzer.cli.context import state
from llm_analyzer.cli.workflow import run_analysis
from llm_analyzer.config.settings import Priority, ReportFormat, UseCase


def analysis_command(
    ctx: typer.Context,
    use_case: UseCase | None = typer.Option(
        None, help="Workload to match against catalog capabilities."
    ),
    priority: Priority | None = typer.Option(
        None, help="Ranking preference; never overrides compatibility."
    ),
    context: int | None = typer.Option(
        None, min=128, max=1048576, help="Total context tokens (input plus generation)."
    ),
    top: int | None = typer.Option(None, min=1, max=100, help="Maximum named recommendations."),
    runtime: str = typer.Option("auto", help="auto, ollama or llama.cpp."),
    scan_file: Path | None = typer.Option(None, help="Analyze a saved Windows hardware scan."),
    catalog_file: Path | None = typer.Option(
        None, help="Use a validated replacement model catalog."
    ),
    rules_file: Path | None = typer.Option(None, help="Use replacement runtime rules."),
    interactive: bool = typer.Option(
        False, "--interactive", "-i", help="Ask workload and report questions on a terminal."
    ),
    save_report: bool = typer.Option(
        False, help="Save a detailed report to Documents or --output."
    ),
    report_format: ReportFormat | None = typer.Option(None, help="Report format."),
    output: str | None = typer.Option(None, help="Report file or directory; implies saving."),
    force: bool = typer.Option(False, help="Allow replacing an existing output file."),
) -> None:
    """Scan and recommend local models, with reasons and optional reports."""
    run_analysis(
        state(ctx),
        use_case=use_case,
        priority=priority,
        context=context,
        top=top,
        runtime=runtime,
        scan_file=scan_file,
        catalog_file=catalog_file,
        rules_file=rules_file,
        interactive=interactive,
        save=save_report,
        report_format=report_format,
        output=output,
        force=force,
        show_hardware=ctx.info_name == "analyze",
    )


def check_command(
    ctx: typer.Context,
    model_id: str = typer.Argument(..., help="Stable ID from catalog list."),
    quant: str | None = typer.Option(
        None, help="Only evaluate this catalog quantization, e.g. Q4_K_M."
    ),
    context: int | None = typer.Option(None, min=128, max=1048576),
    use_case: UseCase | None = typer.Option(None),
    priority: Priority | None = typer.Option(None),
    runtime: str = typer.Option("auto"),
    scan_file: Path | None = typer.Option(None),
    output: str | None = typer.Option(None),
    report_format: ReportFormat | None = typer.Option(None),
    force: bool = typer.Option(False),
) -> None:
    """Can I run this model? Evaluate its memory, context, runtime and use-case fit."""
    run_analysis(
        state(ctx),
        model_id=model_id,
        quant=quant,
        context=context,
        use_case=use_case,
        priority=priority,
        runtime=runtime,
        scan_file=scan_file,
        output=output,
        report_format=report_format,
        force=force,
    )


def report_command(
    ctx: typer.Context,
    format: ReportFormat | None = typer.Option(None, "--format", "--report-format"),
    output: str | None = typer.Option(
        None, help="File or directory; defaults to Documents known folder."
    ),
    scan_file: Path | None = typer.Option(None),
    use_case: UseCase | None = typer.Option(None),
    priority: Priority | None = typer.Option(None),
    context: int | None = typer.Option(None, min=128, max=1048576),
    top: int | None = typer.Option(None, min=1, max=100),
    runtime: str = typer.Option("auto"),
    force: bool = typer.Option(False),
) -> None:
    """Generate a detailed Markdown, JSON, text or HTML analysis report."""
    run_analysis(
        state(ctx),
        save=True,
        report_format=format,
        output=output,
        scan_file=scan_file,
        use_case=use_case,
        priority=priority,
        context=context,
        top=top,
        runtime=runtime,
        force=force,
    )
