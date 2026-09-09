import math

from llm_analyzer.catalog.schemas import ModelDefinition, QuantizationDefinition
from llm_analyzer.config.settings import Settings
from llm_analyzer.schemas.common import Confidence
from llm_analyzer.schemas.results import MemoryEstimate

GIB = 1024**3
FALLBACK_KV_BYTES_PER_TOKEN_PER_BILLION = 65536


def safe_ram(available: int | None, settings: Settings) -> int | None:
    if available is None:
        return None
    reserve = max(
        settings.minimum_ram_reserve_gib * GIB, available * settings.ram_headroom_fraction
    )
    return max(0, math.floor(available - reserve))


def estimate_memory(
    model: ModelDefinition, quant: QuantizationDefinition, context: int, settings: Settings
) -> MemoryEstimate:
    assumptions = [
        "Single sequence; requested context includes input and generated tokens",
        "FP16 KV cache (2 bytes per element); no cache quantization assumed",
    ]
    weights = quant.file_size_bytes
    confidence = Confidence.MEDIUM
    if weights is None:
        weights = math.ceil(model.parameters * quant.bits_estimate / 8 * 1.05)
        assumptions.append(
            "Weights estimated using effective quantization bits plus 5% format overhead"
        )
        confidence = Confidence.LOW
    else:
        assumptions.append("Weights use verified GGUF artifact size (all shards when split)")
    if model.embedding:
        kv = 0
        # Encoder attention is not a persistent decoder KV cache. Account conservatively
        # for quadratic attention workspace without assuming flash attention support.
        heads = model.kv_heads or 16
        workspace = context * context * heads * 4 + context * (model.head_dim or 128) * heads * 16
        assumptions.append(
            "Encoder: no persistent KV; FP32 quadratic attention workspace for one layer"
        )
    elif model.layers and model.kv_heads and model.head_dim:
        kv = 2 * model.layers * model.kv_heads * model.head_dim * context * 2
        workspace = context * model.kv_heads * model.head_dim * 16
        assumptions.append("KV = 2 (K,V) x layers x KV heads x head dimension x tokens x 2 bytes")
    else:
        kv = math.ceil(
            max(1, model.parameters / 1e9) * context * FALLBACK_KV_BYTES_PER_TOKEN_PER_BILLION
        )
        workspace = context * 65536
        confidence = Confidence.LOW
        assumptions.append(
            "Incomplete architecture: conservative 64 KiB KV/token/billion parameters; not an upper bound for every architecture"
        )
    overhead = math.ceil(settings.runtime_overhead_gib * GIB)
    buffers = math.ceil(max(0.25 * GIB, weights * settings.working_buffer_fraction) + workspace)
    if "image" in model.modalities:
        assumptions.append(
            "Image encoder/projector and image-dependent activations are unbounded here; total is a lower-bound estimate only"
        )
        confidence = Confidence.LOW
    total = weights + kv + overhead + buffers
    return MemoryEstimate(
        weights_bytes=weights,
        kv_cache_bytes=kv,
        runtime_overhead_bytes=overhead,
        working_buffers_bytes=buffers,
        total_bytes=total,
        storage_required_bytes=math.ceil(weights * settings.storage_multiplier),
        confidence=confidence,
        assumptions=assumptions,
    )
