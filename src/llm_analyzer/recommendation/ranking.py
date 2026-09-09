from llm_analyzer.config.settings import Priority
from llm_analyzer.schemas.results import Execution, Fit, ModelRecommendation

FIT_ORDER = {
    Fit.EXCELLENT: 0,
    Fit.GOOD: 1,
    Fit.BORDERLINE: 2,
    Fit.UNKNOWN: 3,
    Fit.NOT_RECOMMENDED: 4,
}
EXECUTION_ORDER = {Execution.GPU: 0, Execution.HYBRID: 1, Execution.CPU: 2, Execution.NONE: 3}


def ranking_key(item: ModelRecommendation, priority: Priority) -> tuple[float | str, ...]:
    """Lexicographic, documented policy; compatibility always precedes preferences."""
    common: tuple[float | str, ...] = (FIT_ORDER[item.fit],)
    preference: tuple[float, ...]
    if priority == Priority.LOW_MEMORY:
        preference = (item.memory.total_bytes, -item.bits_estimate, -item.parameters)
    elif priority == Priority.SPEED:
        preference = (EXECUTION_ORDER[item.execution], item.parameters, item.memory.total_bytes)
    elif priority == Priority.QUALITY:
        preference = (item.bits_estimate < 4, -item.parameters, -item.bits_estimate)
    else:
        # Prefer Q4_K_M-like balance over extreme quantization, then an accelerated plan,
        # then parameter capacity. Parameters are only a size proxy, not measured quality.
        preference = (
            abs(item.bits_estimate - 4.85),
            EXECUTION_ORDER[item.execution],
            -item.parameters,
        )
    return (
        common
        + preference
        + (not item.runtime_installed, item.model_id, item.quantization, item.runtime)
    )


def best_per_model(
    items: list[ModelRecommendation], priority: Priority
) -> list[ModelRecommendation]:
    selected: dict[str, ModelRecommendation] = {}
    for item in sorted(items, key=lambda row: ranking_key(row, priority)):
        selected.setdefault(item.model_id, item)
    return list(selected.values())
