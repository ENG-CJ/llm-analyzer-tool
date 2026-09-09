from packaging.version import InvalidVersion, Version

from llm_analyzer.catalog.schemas import ModelDefinition, QuantizationDefinition, RuntimeRule
from llm_analyzer.schemas.common import Status
from llm_analyzer.schemas.hardware import GPUInfo, HardwareScanResult, RuntimeInfo
from llm_analyzer.schemas.results import AnalysisRequest, RecommendationReason


def reason(code: str, level: str, message: str) -> RecommendationReason:
    return RecommendationReason.model_validate({"code": code, "level": level, "message": message})


def check_compatibility(
    model: ModelDefinition,
    quant: QuantizationDefinition,
    rule: RuntimeRule,
    hardware: HardwareScanResult,
    request: AnalysisRequest,
) -> list[RecommendationReason]:
    reasons: list[RecommendationReason] = []
    if (
        hardware.platform.os.lower() not in rule.platforms
        or hardware.platform.architecture not in rule.architectures
    ):
        reasons.append(
            reason(
                "platform",
                "fail",
                "Platform/architecture is outside this runtime rule's supported scope",
            )
        )
    if not model.generic and model.architecture not in rule.model_architectures:
        reasons.append(
            reason(
                "architecture",
                "fail",
                "Model architecture is not represented by this runtime's support rules",
            )
        )
    if (
        model.format not in rule.formats
        or quant.name not in rule.quantizations
        or rule.name not in model.runtime_support
    ):
        reasons.append(
            reason(
                "runtime_format",
                "fail",
                "Runtime does not support this catalog format/quantization configuration",
            )
        )
    if request.context > model.context_maximum:
        reasons.append(
            reason(
                "context",
                "fail",
                f"Requested context {request.context} exceeds catalog limit {model.context_maximum}",
            )
        )
    else:
        reasons.append(
            reason(
                "context",
                "pass",
                f"Requested {request.context} tokens are within the catalog context limit",
            )
        )
    if request.use_case not in model.capabilities:
        reasons.append(
            reason(
                "use_case",
                "fail",
                f"Catalog does not establish suitability for {request.use_case.value}",
            )
        )
    else:
        reasons.append(
            reason("use_case", "pass", f"Catalog capability matches {request.use_case.value}")
        )
    if not hardware.cpu.flags_known:
        reasons.append(
            reason(
                "cpu_flags",
                "unknown",
                "CPU instruction support is unknown; runtime CPU requirements cannot be verified",
            )
        )
    elif not set(rule.required_cpu_flags) <= set(hardware.cpu.flags):
        reasons.append(
            reason(
                "cpu_flags",
                "fail",
                "Required CPU instructions are missing for the runtime build targeted by these rules",
            )
        )
    runtime = next(
        (r for r in hardware.runtimes if r.name == rule.name), RuntimeInfo(name=rule.name)
    )
    minimum = model.runtime_minimum_versions.get(rule.name) or rule.minimum_version
    if runtime.installed and minimum:
        try:
            if runtime.version is None:
                reasons.append(
                    reason(
                        "runtime_version",
                        "unknown",
                        f"Cannot verify required {rule.name} version >= {minimum}",
                    )
                )
            elif Version(runtime.version) < Version(minimum):
                reasons.append(
                    reason(
                        "runtime_version",
                        "fail",
                        f"Installed {rule.name} must be upgraded to >= {minimum}",
                    )
                )
        except InvalidVersion:
            reasons.append(
                reason(
                    "runtime_version", "unknown", "Installed runtime version could not be compared"
                )
            )
    if not runtime.installed:
        reasons.append(
            reason(
                "runtime_install",
                "warning",
                f"Install a current compatible {rule.name} build to use this configuration; nothing is installed automatically",
            )
        )
    elif runtime.status != Status.AVAILABLE:
        reasons.append(
            reason(
                "runtime_health",
                "unknown",
                "Runtime executable was found, but its version/health could not be verified",
            )
        )
    reasons.append(
        reason(
            "runtime_conditional",
            "warning",
            "Runtime family supports this catalog recipe; the installed build and exact model artifact have not been execution-tested",
        )
    )
    return reasons


def cuda_eligible(gpu: GPUInfo, rule: RuntimeRule, hardware: HardwareScanResult) -> bool:
    capability = hardware.backends.get("cuda_driver")
    if "cuda" not in rule.backends or not capability or capability.status != Status.AVAILABLE:
        return False
    if (
        gpu.vendor != "NVIDIA"
        or gpu.gpu_type in {"integrated", "software"}
        or gpu.compute_capability is None
    ):
        return False
    if rule.cuda is None or gpu.driver_version is None:
        return False
    try:
        driver = int(gpu.driver_version.split(".")[0])
    except ValueError:
        return False
    policy = rule.cuda
    minimum_driver = policy.minimum_driver_major
    if policy.legacy_compute_below and gpu.compute_capability < policy.legacy_compute_below:
        minimum_driver = policy.legacy_minimum_driver_major or minimum_driver
    return gpu.compute_capability >= policy.minimum_compute_capability and driver >= minimum_driver
