from pathlib import Path

import pytest

from llm_analyzer.config.settings import Priority, UseCase
from llm_analyzer.hardware.scanner import read_scan
from llm_analyzer.recommendation.engine import analyze, evaluate
from llm_analyzer.recommendation.memory import GIB, estimate_memory
from llm_analyzer.schemas.results import AnalysisRequest, Execution, Fit
from llm_analyzer.utils.errors import AnalyzerError

FIXTURES = Path(__file__).parents[1] / "fixtures"


@pytest.mark.parametrize("file", sorted(FIXTURES.glob("*.json")), ids=lambda p: p.stem)
def test_all_fixture_profiles_are_deterministic(file, catalog, rules, settings):
    hardware = read_scan(file)
    first = analyze(hardware, catalog, rules, AnalysisRequest(), settings)
    second = analyze(hardware, catalog, rules, AnalysisRequest(), settings)
    assert first.result.model_dump(exclude={"generated_at"}) == second.result.model_dump(
        exclude={"generated_at"}
    )
    assert len(first.result.catalog_sha256) == 64
    for item in first.result.recommendations:
        assert item.reasons
        assert item.fit not in {Fit.UNKNOWN, Fit.NOT_RECOMMENDED}
        model = next(m for m in catalog.models if m.id == item.model_id)
        assert item.quantization in [q.name for q in model.quantizations]


@pytest.mark.parametrize("use_case", list(UseCase))
def test_use_case_never_recommends_incompatible_model(use_case, hardware, catalog, rules, settings):
    result = analyze(hardware, catalog, rules, AnalysisRequest(use_case=use_case), settings)
    for recommendation in result.result.recommendations:
        model = next(m for m in catalog.models if m.id == recommendation.model_id)
        assert use_case in model.capabilities
    if use_case == UseCase.MULTIMODAL:
        assert not result.result.recommendations
        assert any(item.model_id == "qwen2.5-vl-7b-instruct" for item in result.result.unknown)


@pytest.mark.parametrize("priority", list(Priority))
def test_priorities_preserve_constraints(priority, hardware, catalog, rules, settings):
    result = analyze(hardware, catalog, rules, AnalysisRequest(priority=priority), settings)
    assert len({r.model_id for r in result.result.recommendations}) == len(
        result.result.recommendations
    )
    assert all(r.memory.total_bytes > r.memory.weights_bytes for r in result.result.recommendations)


@pytest.mark.parametrize(
    "fixture, reason", [("windows_low_disk", "storage"), ("windows_low_available_ram", "ram_hard")]
)
def test_real_resource_failures_reject(fixture, reason, catalog, rules, settings):
    result = analyze(
        read_scan(FIXTURES / f"{fixture}.json"), catalog, rules, AnalysisRequest(), settings
    )
    assert not result.result.recommendations
    assert any(
        r.code == reason and r.level == "fail"
        for item in result.result.rejected
        for r in item.reasons
    )


@pytest.mark.parametrize(
    "fixture", ["windows_unknown_vram", "windows_amd", "windows_intel_integrated"]
)
def test_unknown_gpu_support_has_cpu_fallback(fixture, catalog, rules, settings):
    result = analyze(
        read_scan(FIXTURES / f"{fixture}.json"), catalog, rules, AnalysisRequest(), settings
    )
    assert result.result.recommendations
    assert all(item.execution == Execution.CPU for item in result.result.recommendations)


def test_multiple_gpus_are_not_pooled(catalog, rules, settings):
    hw = read_scan(FIXTURES / "windows_multiple_gpus.json")
    result = analyze(
        hw,
        catalog,
        rules,
        AnalysisRequest(model_id="qwen2.5-7b-instruct", quant="Q4_K_M"),
        settings,
    )
    assert all(item.execution != Execution.GPU for item in result.result.evaluated_configurations)
    assert any(
        item.execution == Execution.HYBRID for item in result.result.evaluated_configurations
    )


def test_cuda_toolkit_not_required(hardware, catalog, rules, settings):
    result = analyze(
        hardware,
        catalog,
        rules,
        AnalysisRequest(model_id="qwen2.5-7b-instruct", quant="Q4_K_M"),
        settings,
    )
    assert hardware.backends["cuda_toolkit"].status == "not_available"
    assert any(item.execution == Execution.GPU for item in result.result.evaluated_configurations)


def test_excessive_context_rejects(hardware, catalog, rules, settings):
    result = analyze(
        hardware,
        catalog,
        rules,
        AnalysisRequest(model_id="qwen2.5-7b-instruct", context=65536),
        settings,
    )
    assert result.result.rejected
    assert not result.result.recommendations
    assert all(
        any(r.code == "context" and r.level == "fail" for r in item.reasons)
        for item in result.result.evaluated_configurations
    )


def test_unknown_memory_is_not_rejection(hardware, catalog, rules, settings):
    hardware.memory.available_bytes = None
    result = analyze(
        hardware, catalog, rules, AnalysisRequest(model_id="qwen2.5-3b-instruct"), settings
    )
    assert result.result.unknown
    assert not result.result.rejected


def test_missing_runtime_is_explicit(catalog, rules, settings):
    result = analyze(
        read_scan(FIXTURES / "windows_no_ollama.json"), catalog, rules, AnalysisRequest(), settings
    )
    assert result.result.recommendations
    assert all(not r.runtime_installed for r in result.result.recommendations)
    assert all(
        any(reason.code == "runtime_install" for reason in r.reasons)
        for r in result.result.recommendations
    )


def test_tight_memory_is_borderline(hardware, catalog, rules, settings):
    model = next(m for m in catalog.models if m.id == "qwen2.5-3b-instruct")
    quant = next(q for q in model.quantizations if q.name == "Q4_K_M")
    request = AnalysisRequest(runtime="llama.cpp")
    memory = estimate_memory(model, quant, request.context, settings)
    hardware.memory.available_bytes = memory.total_bytes + GIB // 2
    result = evaluate(model, quant, rules.runtimes[1], hardware, request, settings)
    assert result.fit == Fit.BORDERLINE


def test_unsupported_architecture_rejected(hardware, catalog, rules, settings):
    model = catalog.models[0].model_copy(update={"architecture": "unrepresented_architecture"})
    result = evaluate(
        model, model.quantizations[0], rules.runtimes[0], hardware, AnalysisRequest(), settings
    )
    assert result.fit == Fit.NOT_RECOMMENDED
    assert result.runtime_compatibility == "unsupported"


def test_unknown_quantization_is_input_error(hardware, catalog, rules, settings):
    with pytest.raises(AnalyzerError) as error:
        analyze(hardware, catalog, rules, AnalysisRequest(quant="FAKE"), settings)
    assert error.value.code == 2


def test_lower_free_vram_changes_plan(hardware, catalog, rules, settings):
    request = AnalysisRequest(model_id="qwen2.5-7b-instruct", quant="Q4_K_M", runtime="ollama")
    before = analyze(hardware, catalog, rules, request, settings)
    hardware.gpus[0].free_vram_bytes = 100 * 1024**2
    after = analyze(hardware, catalog, rules, request, settings)
    assert before.result.recommendations[0].execution == Execution.GPU
    assert after.result.recommendations[0].execution == Execution.CPU


@pytest.mark.parametrize(
    "compute,driver,expected",
    [
        (4.9, "580.1", False),
        (5.0, "550.1", False),
        (5.0, "570.1", True),
        (6.2, "569.9", False),
        (6.3, "550.1", True),
        (8.6, "549.9", False),
        (8.6, "580.1", True),
    ],
)
def test_cuda_driver_matrix(compute, driver, expected, hardware, rules):
    from llm_analyzer.recommendation.compatibility import cuda_eligible

    hardware.gpus[0].compute_capability = compute
    hardware.gpus[0].driver_version = driver
    assert cuda_eligible(hardware.gpus[0], rules.runtimes[0], hardware) is expected


def test_old_runtime_rejected_for_known_minimum(hardware, catalog, rules, settings):
    hardware.runtimes[0].version = "0.6.0"
    result = analyze(
        hardware,
        catalog,
        rules,
        AnalysisRequest(model_id="qwen2.5-vl-7b-instruct", use_case="multimodal"),
        settings,
    )
    assert result.result.rejected
    assert any(
        r.code == "runtime_version" and r.level == "fail" for r in result.result.rejected[0].reasons
    )
