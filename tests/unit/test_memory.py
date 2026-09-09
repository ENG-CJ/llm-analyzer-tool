import pytest

from llm_analyzer.recommendation.memory import GIB, estimate_memory, safe_ram


def test_verified_weight_size_preferred(catalog, settings):
    model = next(m for m in catalog.models if m.id == "qwen2.5-7b-instruct")
    quant = next(q for q in model.quantizations if q.name == "Q4_K_M")
    estimate = estimate_memory(model, quant, 8192, settings)
    assert estimate.weights_bytes == 4683073632
    assert estimate.kv_cache_bytes == 2 * 28 * 4 * 128 * 8192 * 2
    assert (
        estimate.total_bytes
        == estimate.weights_bytes
        + estimate.kv_cache_bytes
        + estimate.runtime_overhead_bytes
        + estimate.working_buffers_bytes
    )
    assert estimate.total_bytes > quant.file_size_bytes


@pytest.mark.parametrize("context", [4096, 8192, 16384, 32768])
def test_context_increases_memory(catalog, settings, context):
    model = next(m for m in catalog.models if m.id == "qwen3-4b")
    small = estimate_memory(model, model.quantizations[0], context, settings)
    large = estimate_memory(model, model.quantizations[0], context * 2, settings)
    assert large.kv_cache_bytes == small.kv_cache_bytes * 2
    assert large.total_bytes > small.total_bytes
    assert small.kv_cache_bytes == 2 * 36 * 8 * 128 * context * 2


def test_encoder_has_no_decoder_kv(catalog, settings):
    model = next(m for m in catalog.models if m.embedding)
    small = estimate_memory(model, model.quantizations[0], 1024, settings)
    large = estimate_memory(model, model.quantizations[0], 8192, settings)
    assert small.kv_cache_bytes == 0
    assert large.working_buffers_bytes > small.working_buffers_bytes * 4


def test_unknown_architecture_is_low_confidence(catalog, settings):
    model = next(m for m in catalog.models if m.generic)
    value = estimate_memory(model, model.quantizations[0], 8192, settings)
    assert value.confidence == "low"
    assert "Incomplete architecture" in " ".join(value.assumptions)


def test_headroom_uses_available_not_installed(settings):
    assert safe_ram(8 * GIB, settings) == int(8 * GIB * 0.85)
    assert safe_ram(GIB // 2, settings) == 0
    assert safe_ram(None, settings) is None


def test_more_headroom_reduces_budget(settings):
    conservative = settings.model_copy(update={"ram_headroom_fraction": 0.4})
    assert safe_ram(8 * GIB, conservative) < safe_ram(8 * GIB, settings)
