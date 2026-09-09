import json

import pytest
from pydantic import ValidationError

from llm_analyzer.catalog.loader import load_catalog, load_rules, validate_relationships
from llm_analyzer.catalog.schemas import Catalog, RuntimeRules
from llm_analyzer.schemas.hardware import HardwareScanResult
from llm_analyzer.utils.errors import AnalyzerError


@pytest.mark.parametrize("mutation", ["duplicate", "context", "quant", "missing", "version"])
def test_catalog_rejects_malformed_entries(catalog, mutation):
    data = catalog.model_dump(mode="json")
    if mutation == "duplicate":
        data["models"].append(data["models"][0])
    elif mutation == "context":
        data["models"][0]["context_maximum"] = 0
    elif mutation == "quant":
        data["models"][0]["quantizations"][0]["bits_estimate"] = -4
    elif mutation == "missing":
        del data["models"][0]["parameters"]
    else:
        data["schema_version"] = "99"
    with pytest.raises(ValidationError):
        Catalog.model_validate(data)


def test_malformed_catalog_friendly_error(tmp_path):
    path = tmp_path / "models.json"
    path.write_text('{"models":', encoding="utf-8")
    with pytest.raises(AnalyzerError) as error:
        load_catalog(path)
    assert error.value.code == 5


def test_runtime_rules_validate(rules):
    data = rules.model_dump(mode="json")
    data["runtimes"][0]["quantizations"] = ["BOGUS"]
    with pytest.raises(ValidationError):
        RuntimeRules.model_validate(data)


def test_relationship_validation(catalog, rules):
    catalog.models[0].runtime_support = ["missing-runtime"]
    with pytest.raises(AnalyzerError):
        validate_relationships(catalog, rules)


@pytest.mark.parametrize("counter", ["available_bytes", "used_bytes"])
def test_saved_memory_counters_cannot_exceed_total(hardware, counter):
    data = hardware.model_dump(mode="json")
    data["memory"][counter] = data["memory"]["total_bytes"] + 1
    with pytest.raises(ValidationError):
        HardwareScanResult.model_validate(data)


def test_saved_scan_rejects_extra_private_fields(hardware):
    data = hardware.model_dump(mode="json")
    data["hostname"] = "not-allowed"
    with pytest.raises(ValidationError):
        HardwareScanResult.model_validate(data)


def test_nan_settings_or_scan_not_allowed(hardware):
    data = hardware.model_dump(mode="json")
    data["memory"]["utilization_percent"] = float("nan")
    with pytest.raises(ValidationError):
        HardwareScanResult.model_validate(data)


def test_packaged_rules_roundtrip(tmp_path, rules):
    path = tmp_path / "rules.json"
    path.write_text(json.dumps(rules.model_dump(mode="json")), encoding="utf-8")
    assert load_rules(path) == rules
