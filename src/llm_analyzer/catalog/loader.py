import hashlib
import json
from importlib.resources import files
from pathlib import Path

from pydantic import ValidationError

from llm_analyzer.catalog.schemas import Catalog, RuntimeRules
from llm_analyzer.utils.errors import AnalyzerError
from llm_analyzer.utils.files import read_json


def resource_text(name: str) -> str:
    """Package-relative resources work in wheels and PyInstaller's bundled package."""
    return files("llm_analyzer").joinpath("data", name).read_text(encoding="utf-8")


def load_catalog(path: Path | None = None) -> Catalog:
    try:
        return Catalog.model_validate(
            read_json(path) if path else json.loads(resource_text("models.json"))
        )
    except (OSError, ValueError, ValidationError) as exc:
        raise AnalyzerError(
            "Invalid model catalog; run catalog validate with a trusted catalog", 5
        ) from exc


def load_rules(path: Path | None = None) -> RuntimeRules:
    try:
        return RuntimeRules.model_validate(
            read_json(path) if path else json.loads(resource_text("runtime_rules.json"))
        )
    except (OSError, ValueError, ValidationError) as exc:
        raise AnalyzerError("Invalid runtime rules; restore a validated rules file", 5) from exc


def validate_relationships(catalog: Catalog, rules: RuntimeRules) -> None:
    known = {rule.name for rule in rules.runtimes}
    for model in catalog.models:
        if not set(model.runtime_support) <= known:
            raise AnalyzerError(f"Catalog model {model.id} references an unknown runtime", 5)


def fingerprint(value: Catalog | RuntimeRules) -> str:
    canonical = json.dumps(value.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()
