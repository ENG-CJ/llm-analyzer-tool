from dataclasses import dataclass

import typer
from rich.console import Console

from llm_analyzer.config.settings import Settings


@dataclass
class CLIState:
    settings: Settings
    console: Console
    json: bool = False
    quiet: bool = False
    no_progress: bool = False
    debug: bool = False


def state(ctx: typer.Context) -> CLIState:
    value = ctx.find_root().obj
    if not isinstance(value, CLIState):
        raise RuntimeError("CLI context was not initialized")
    return value
