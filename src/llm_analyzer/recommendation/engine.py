from typing import Literal

from llm_analyzer.catalog.loader import fingerprint, validate_relationships
from llm_analyzer.catalog.schemas import (
    Catalog,
    ModelDefinition,
    QuantizationDefinition,
    RuntimeRule,
    RuntimeRules,
)
from llm_analyzer.config.settings import Settings
from llm_analyzer.recommendation.compatibility import check_compatibility, reason
from llm_analyzer.recommendation.memory import GIB, estimate_memory, safe_ram
from llm_analyzer.recommendation.planning import choose_plan
from llm_analyzer.recommendation.ranking import best_per_model
from llm_analyzer.schemas.common import Confidence
from llm_analyzer.schemas.hardware import HardwareScanResult
from llm_analyzer.schemas.results import (
    AnalysisRequest,
    AnalysisResult,
    Execution,
    Fit,
    ModelRecommendation,
    RecommendationResult,
)
from llm_analyzer.utils.errors import AnalyzerError

METHODOLOGY = (
    "Recommendations derive from detected hardware, current available memory, versioned model metadata, "
    "quantized artifact sizes, context/KV estimates, runtime/backend rules, disk capacity and configured "
    "headroom. These are conditional capacity estimates, not execution guarantees. Single-sequence inference "
    "is assumed. Performance classes are qualitative and low confidence; no LLM benchmark was run."
)


def evaluate(
    model: ModelDefinition,
    quant: QuantizationDefinition,
    rule: RuntimeRule,
    hardware: HardwareScanResult,
    request: AnalysisRequest,
    settings: Settings,
) -> ModelRecommendation:
    memory = estimate_memory(model, quant, request.context, settings)
    ram = safe_ram(hardware.memory.available_bytes, settings)
    reasons = check_compatibility(model, quant, rule, hardware, request)
    plan = choose_plan(hardware, rule, memory, ram, settings)
    if ram is None:
        reasons.append(reason("ram_unknown", "unknown", "Currently available RAM is unknown"))
    elif plan.host_bytes > (hardware.memory.available_bytes or 0):
        reasons.append(
            reason("ram_hard", "fail", "Estimated host allocation exceeds currently available RAM")
        )
    elif plan.host_bytes > ram:
        reasons.append(
            reason(
                "ram_headroom",
                "warning",
                "May fit physical RAM but violates the configured safety reserve",
            )
        )
    else:
        reasons.append(
            reason(
                "ram_fit", "pass", "Estimated host allocation fits the safe available RAM budget"
            )
        )
    if hardware.storage.free_bytes is None:
        reasons.append(
            reason(
                "storage_unknown",
                "unknown",
                "Free storage on the model download drive could not be verified",
            )
        )
    elif memory.storage_required_bytes > hardware.storage.free_bytes:
        reasons.append(
            reason(
                "storage",
                "fail",
                "Insufficient free system-drive storage for the artifact and download headroom",
            )
        )
    else:
        reasons.append(
            reason(
                "storage",
                "pass",
                "System-drive storage covers weights plus configured download headroom",
            )
        )
    if plan.execution == Execution.GPU:
        reasons.append(
            reason(
                "gpu_fit",
                "pass",
                "Full model execution allocation fits one device's safe free dedicated VRAM",
            )
        )
        reasons.append(
            reason(
                "gpu_build",
                "warning",
                "Requires a compatible CUDA-enabled runtime build; CUDA Toolkit is not used as a requirement",
            )
        )
    elif plan.execution == Execution.HYBRID:
        reasons.append(
            reason(
                "hybrid",
                "warning",
                "Partial CUDA offload is supported by runtime rules; full host allocation retained conservatively. Expect transfer overhead.",
            )
        )
    elif hardware.gpus:
        reasons.append(
            reason(
                "cpu_fallback",
                "warning",
                "Using a CPU plan: GPU backend, device compatibility or free VRAM was insufficient or unverified",
            )
        )
    if "image" in model.modalities:
        reasons.append(
            reason(
                "vision_memory",
                "unknown",
                "Vision encoder/projector and image-size memory are not bounded by this estimator; cannot establish a complete multimodal fit",
            )
        )
    if model.generic:
        reasons.append(
            reason(
                "generic",
                "warning",
                "Hypothetical dense capacity profile, not a verified model artifact or runtime architecture",
            )
        )
    if quant.bits_estimate < 4:
        reasons.append(
            reason(
                "low_quant",
                "warning",
                "Aggressive quantization trades quality for memory; validate task quality before relying on it",
            )
        )
    for note in model.notes:
        reasons.append(reason("catalog_note", "info", note))
    fit = Fit.GOOD
    confidence = memory.confidence
    if any(r.level == "fail" for r in reasons):
        fit = Fit.NOT_RECOMMENDED
    elif any(r.level == "unknown" for r in reasons):
        fit, confidence = Fit.UNKNOWN, Confidence.UNKNOWN
    elif (
        plan.host_bytes > (ram or 0)
        or plan.execution == Execution.HYBRID
        or quant.bits_estimate < 4
    ):
        fit = Fit.BORDERLINE
    elif ram and plan.host_bytes <= ram * 0.7 and plan.execution == Execution.GPU:
        fit = Fit.EXCELLENT
    if model.generic:
        confidence = Confidence.LOW
        if fit == Fit.EXCELLENT:
            fit = Fit.GOOD
    if model.metadata_confidence in {Confidence.LOW, Confidence.UNKNOWN}:
        confidence = model.metadata_confidence
    performance: Literal["fast", "moderate", "slow", "very_slow", "unknown"] = "unknown"
    if fit in {Fit.EXCELLENT, Fit.GOOD, Fit.BORDERLINE}:
        performance = "moderate" if plan.execution == Execution.GPU else "slow"
        if plan.execution == Execution.CPU and model.parameters > 14_000_000_000:
            performance = "very_slow"
    return ModelRecommendation(
        model_id=model.id,
        display_name=model.display_name,
        parameters=model.parameters,
        quantization=quant.name,
        bits_estimate=quant.bits_estimate,
        generic=model.generic,
        context=request.context,
        runtime=rule.name,
        runtime_installed=any(r.name == rule.name and r.installed for r in hardware.runtimes),
        runtime_compatibility="unsupported"
        if any(
            r.code in {"runtime_format", "architecture", "platform", "runtime_version", "cpu_flags"}
            and r.level == "fail"
            for r in reasons
        )
        else "unknown"
        if any(
            r.code in {"runtime_version", "runtime_health", "cpu_flags"} and r.level == "unknown"
            for r in reasons
        )
        else "conditional",
        fit=fit,
        execution=plan.execution,
        gpu_index=plan.gpu.index if plan.gpu else None,
        gpu_name=plan.gpu.name if plan.gpu else None,
        backend="cuda" if plan.gpu else "cpu",
        memory=memory,
        safe_ram_bytes=ram,
        safe_vram_bytes=plan.safe_vram,
        estimated_host_bytes=plan.host_bytes,
        estimated_device_bytes=plan.device_bytes,
        confidence=confidence,
        performance_class=performance,
        reasons=reasons,
    )


def capability_summary(items: list[ModelRecommendation]) -> tuple[str, str]:
    suitable = [item for item in items if item.fit in {Fit.EXCELLENT, Fit.GOOD}]
    gpu = [item for item in suitable if item.execution == Execution.GPU]
    if gpu:
        capacity = max(item.safe_vram_bytes or 0 for item in gpu)
        label = (
            "Workstation-class local AI"
            if capacity >= 20 * GIB
            else "Balanced local AI"
            if capacity >= 6 * GIB
            else "Entry local AI"
        )
        return (
            label,
            "Based on the largest verified single-device safe VRAM budget with a suitable full-GPU configuration",
        )
    if suitable:
        return (
            "CPU-focused local AI",
            "At least one catalog configuration fits safely; no full-GPU plan established",
        )
    return (
        "Limited or unknown local AI capacity",
        "No comfortable configuration established for the selected request",
    )


def analyze(
    hardware: HardwareScanResult,
    catalog: Catalog,
    rules: RuntimeRules,
    request: AnalysisRequest,
    settings: Settings,
) -> AnalysisResult:
    validate_relationships(catalog, rules)
    if request.runtime != "auto" and request.runtime not in {r.name for r in rules.runtimes}:
        raise AnalyzerError("Unknown runtime; choose auto, ollama or llama.cpp", 2)
    models = [
        model
        for model in catalog.models
        if request.model_id is None or model.id == request.model_id
    ]
    if not models:
        raise AnalyzerError("Unknown model ID; use catalog search or catalog list", 2)
    if request.quant and not any(q.name == request.quant for m in models for q in m.quantizations):
        raise AnalyzerError("Requested quantization is not available for the selected model(s)", 2)
    evaluations = [
        evaluate(model, quant, rule, hardware, request, settings)
        for model in models
        for quant in model.quantizations
        for rule in rules.runtimes
        if (request.quant is None or request.quant == quant.name)
        and (
            request.runtime == "auto"
            and rule.name in model.runtime_support
            or request.runtime == rule.name
        )
    ]
    best = best_per_model(evaluations, request.priority)
    named = [item for item in best if not item.generic]
    good = [item for item in named if item.fit in {Fit.EXCELLENT, Fit.GOOD, Fit.BORDERLINE}]
    summary, explanation = capability_summary(named)
    warnings = list(hardware.warnings)
    if not good:
        warnings.append(
            "No named configuration is recommended for this request; inspect unknown and rejected results."
        )
    result = RecommendationResult(
        request=request,
        catalog_version=catalog.catalog_version,
        catalog_sha256=fingerprint(catalog),
        rules_version=rules.rules_version,
        rules_sha256=fingerprint(rules),
        recommendations=good[: request.top],
        rejected=[item for item in named if item.fit == Fit.NOT_RECOMMENDED],
        unknown=[item for item in named if item.fit == Fit.UNKNOWN],
        generic_capacity=[item for item in best if item.generic],
        evaluated_configurations=evaluations,
        capability_summary=summary,
        capability_reason=explanation,
        warnings=warnings,
    )
    return AnalysisResult(
        hardware=hardware, result=result, settings=settings, methodology=METHODOLOGY
    )
