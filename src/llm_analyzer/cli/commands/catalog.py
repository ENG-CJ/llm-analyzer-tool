from pathlib import Path

import typer
from rich.table import Table

from llm_analyzer.catalog.loader import load_catalog, load_rules, validate_relationships
from llm_analyzer.catalog.schemas import ModelDefinition
from llm_analyzer.cli.context import state
from llm_analyzer.cli.renderers import emit_json
from llm_analyzer.schemas.common import Envelope
from llm_analyzer.utils.errors import AnalyzerError

catalog_app = typer.Typer(
    help="Browse and validate the offline, versioned model catalog.", no_args_is_help=True
)


def show_models(ctx: typer.Context, models: list[ModelDefinition]) -> None:
    current = state(ctx)
    if current.json:
        emit_json(
            {
                **Envelope().model_dump(mode="json"),
                "models": [m.model_dump(mode="json") for m in models],
            },
            current,
        )
    elif not current.quiet:
        table = Table("Model ID", "Use cases", "Context", "Quantizations")
        for model in models:
            table.add_row(
                model.id,
                ", ".join(model.capabilities),
                str(model.context_maximum),
                ", ".join(q.name for q in model.quantizations),
            )
        current.console.print(table)


@catalog_app.command("list")
def list_models(ctx: typer.Context, catalog_file: Path | None = typer.Option(None)) -> None:
    """List named models and clearly labeled generic capacity profiles."""
    show_models(ctx, load_catalog(catalog_file).models)


@catalog_app.command("search")
def search_models(
    ctx: typer.Context, query: str, catalog_file: Path | None = typer.Option(None)
) -> None:
    """Search model IDs, family names and workload capabilities."""
    models = load_catalog(catalog_file).models
    show_models(
        ctx,
        [
            m
            for m in models
            if query.casefold()
            in " ".join([m.id, m.display_name, m.family, *m.capabilities]).casefold()
        ],
    )


@catalog_app.command("show")
def show_model(
    ctx: typer.Context, model_id: str, catalog_file: Path | None = typer.Option(None)
) -> None:
    """Show a model's full specifications, provenance and available quantizations."""
    model = next((m for m in load_catalog(catalog_file).models if m.id == model_id), None)
    if model is None:
        raise AnalyzerError("Unknown model ID; use catalog search", 2)
    current = state(ctx)
    value = {**Envelope().model_dump(mode="json"), "model": model.model_dump(mode="json")}
    if current.json:
        emit_json(value, current)
    elif not current.quiet:
        current.console.print_json(data=value)


@catalog_app.command("validate")
def validate_catalog(
    ctx: typer.Context,
    catalog_file: Path | None = typer.Option(None),
    rules_file: Path | None = typer.Option(None),
) -> None:
    """Validate schemas, unique IDs, quantizations, runtime rules and relationships."""
    catalog, rules = load_catalog(catalog_file), load_rules(rules_file)
    validate_relationships(catalog, rules)
    current = state(ctx)
    if current.json:
        emit_json(
            {
                **Envelope().model_dump(mode="json"),
                "valid": True,
                "models": len(catalog.models),
                "catalog_version": catalog.catalog_version,
                "rules_version": rules.rules_version,
            },
            current,
        )
    elif not current.quiet:
        current.console.print(
            f"Catalog valid: {len(catalog.models)} models/profiles; {len(rules.runtimes)} runtime rules",
            style="green",
        )
