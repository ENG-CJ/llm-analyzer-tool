"""Validate all shipped data and optionally regenerate versioned JSON schemas."""

import argparse
import json
from pathlib import Path

from llm_analyzer.catalog.loader import load_catalog, load_rules, validate_relationships
from llm_analyzer.catalog.schemas import Catalog, RuntimeRules
from llm_analyzer.schemas.hardware import HardwareScanResult
from llm_analyzer.schemas.results import AnalysisResult, BenchmarkResult, RecommendationResult


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-schemas", action="store_true")
    args = parser.parse_args()
    catalog, rules = load_catalog(), load_rules()
    validate_relationships(catalog, rules)
    directory = Path(__file__).resolve().parents[1] / "src/llm_analyzer/data/schema"
    for name, model in (
        ("models", Catalog),
        ("runtime-rules", RuntimeRules),
        ("hardware-scan", HardwareScanResult),
        ("recommendation", RecommendationResult),
        ("analysis", AnalysisResult),
        ("benchmark", BenchmarkResult),
    ):
        schema = model.model_json_schema()
        schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
        file = directory / f"{name}-1.0.json"
        if args.write_schemas:
            directory.mkdir(parents=True, exist_ok=True)
            file.write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")
        elif not file.exists() or json.loads(file.read_text(encoding="utf-8")) != schema:
            raise SystemExit(
                f"Outdated or missing schema: {file.name}; run --write-schemas and review the diff"
            )
    print(
        f"Validated {len(catalog.models)} models/profiles, {len(rules.runtimes)} runtime rules and six JSON schemas"
    )


if __name__ == "__main__":
    main()
