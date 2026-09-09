import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

import typer
from pydantic import ValidationError
from rich.console import Console
from rich.panel import Panel
from typer.core import TyperGroup

from llm_analyzer import __version__
from llm_analyzer.cli.commands.analysis import analysis_command, check_command, report_command
from llm_analyzer.cli.commands.catalog import catalog_app
from llm_analyzer.cli.commands.system import (
    benchmark_command,
    config_show,
    doctor_command,
    runtimes_command,
    scan_command,
)
from llm_analyzer.cli.context import CLIState, state
from llm_analyzer.cli.renderers import emit_json
from llm_analyzer.config.settings import load_settings
from llm_analyzer.logging_config import configure_logging
from llm_analyzer.schemas.common import Envelope
from llm_analyzer.utils.errors import AnalyzerError

logger = logging.getLogger(__name__)


class GlobalOptionsGroup(TyperGroup):
    """Accept documented display options on either side of the subcommand."""

    def parse_args(self, ctx: Any, args: list[str]) -> list[str]:
        flags = {
            "--json",
            "--no-color",
            "--no-progress",
            "--quiet",
            "--verbose",
            "-v",
            "--debug",
            "--version",
        }
        values = {"--config", "--log-file"}
        global_args, rest = [], []
        index = 0
        while index < len(args):
            arg = args[index]
            if arg == "--":
                rest.extend(args[index:])
                break
            if arg in flags or any(arg.startswith(name + "=") for name in values):
                global_args.append(arg)
            elif arg in values:
                global_args.append(arg)
                if index + 1 < len(args):
                    index += 1
                    global_args.append(args[index])
            else:
                rest.append(arg)
            index += 1
        return super().parse_args(ctx, global_args + rest)

    def invoke(self, ctx: Any) -> Any:
        try:
            return super().invoke(ctx)
        except AnalyzerError as exc:
            typer.echo(f"Error: {exc}", err=True)
            logger.error("Application error, exit code %s", exc.code)
            if isinstance(ctx.obj, CLIState) and ctx.obj.debug:
                Console(stderr=True).print_exception(show_locals=False)
            raise typer.Exit(exc.code) from exc
        except ValidationError as exc:
            typer.echo(
                "Error: invalid input values; inspect the command options or JSON schema", err=True
            )
            raise typer.Exit(2) from exc
        except (KeyboardInterrupt, typer.Abort) as exc:
            typer.echo("Analysis cancelled.", err=True)
            raise typer.Exit(130) from exc
        except (typer.Exit, typer.TyperException):
            raise
        except Exception as exc:
            logger.error("Unexpected application failure: %s", type(exc).__name__)
            typer.echo("Error: operation failed; run with --debug for diagnostic details", err=True)
            if isinstance(ctx.obj, CLIState) and ctx.obj.debug:
                Console(stderr=True).print_exception(show_locals=False)
            raise typer.Exit(1) from exc


app = typer.Typer(
    cls=GlobalOptionsGroup,
    invoke_without_command=True,
    no_args_is_help=False,
    add_completion=False,
    pretty_exceptions_enable=False,
    help="Local LLM Analyzer - offline Windows hardware and model guidance.",
)


@app.callback()
def root(
    ctx: typer.Context,
    json_output: bool = typer.Option(
        False, "--json", help="JSON only on stdout; disables interactive UI."
    ),
    no_color: bool = typer.Option(
        False, "--no-color", help="Disable colors (also respects NO_COLOR)."
    ),
    no_progress: bool = typer.Option(False, "--no-progress", help="Disable scan progress."),
    quiet: bool = typer.Option(
        False, "--quiet", help="Suppress nonessential human-readable output."
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Send probe diagnostics to stderr."
    ),
    debug: bool = typer.Option(
        False, "--debug", help="Enable diagnostic details and debug logging."
    ),
    config: Path | None = typer.Option(None, help="Alternative TOML configuration file."),
    log_file: Path | None = typer.Option(None, help="Alternative rotating log file."),
    version: bool = typer.Option(
        False, "--version", is_eager=True, help="Print application version."
    ),
) -> None:
    if version:
        typer.echo(Envelope().model_dump_json(indent=2) if json_output else __version__)
        raise typer.Exit()
    settings = load_settings(config)
    console = Console(
        no_color=no_color or not settings.color or "NO_COLOR" in os.environ or json_output,
        markup=False,
        highlight=False,
        safe_box=True,
    )
    ctx.obj = CLIState(
        settings, console, json_output, quiet, no_progress or not settings.progress, debug
    )
    try:
        configure_logging(debug, verbose and not quiet, log_file)
    except OSError:
        typer.echo(
            "Warning: log directory is unavailable; continuing without persistent logs", err=True
        )
    if ctx.invoked_subcommand is None:
        from llm_analyzer.cli.workflow import run_analysis

        interactive = console.is_terminal and sys.stdin.isatty() and not (json_output or quiet)
        if interactive:
            console.print(
                Panel(
                    "Analyze your computer for local AI models.",
                    title="Local LLM Analyzer",
                    border_style="cyan",
                )
            )
        run_analysis(state(ctx), interactive=interactive, show_hardware=True)


app.command("analyze")(analysis_command)
app.command("recommend")(analysis_command)
app.command("check")(check_command)
app.command("report")(report_command)
app.command("scan")(scan_command)
app.command("runtimes")(runtimes_command)
app.command("doctor")(doctor_command)
app.command("benchmark")(benchmark_command)
app.add_typer(catalog_app, name="catalog")
config_app = typer.Typer(help="Inspect configuration and file locations.", no_args_is_help=True)
config_app.command("show")(config_show)
app.add_typer(config_app, name="config")


@app.command("version")
def version_command(ctx: typer.Context) -> None:
    """Print the canonical application version."""
    current = state(ctx)
    if current.json:
        emit_json(Envelope(), current)
    elif not current.quiet:
        typer.echo(__version__)


def main() -> None:
    import multiprocessing

    multiprocessing.freeze_support()
    if sys.argv[1:] == ["--internal-cpu-probe"]:
        import cpuinfo

        info = cpuinfo.get_cpu_info()
        # Export only explicit CPU properties, never the complete library environment.
        print(
            json.dumps(
                {key: info[key] for key in ("brand_raw", "vendor_id_raw", "flags") if key in info}
            )
        )
        return
    app()
