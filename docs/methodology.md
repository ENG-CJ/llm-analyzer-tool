# Recommendation methodology

All memory values are bytes internally and GiB (2^30 bytes) in human output. These estimates target one active inference sequence. Input tokens and reserved generation tokens both count against the requested context. Parallel requests, runtime scheduling, image preprocessing and artifact details can change allocations.

## Weights and runtime memory

Verified GGUF file sizes take precedence over parameter arithmetic. For sharded artifacts the catalog sums the complete shard set. When both complete and sharded copies exist, the generator selects the complete artifact; it never sums both. Publisher API snapshots and revision URLs are checked in for review.

When artifact size is absent:

```
weights = ceil(parameters × effective_bits / 8 × 1.05)
```

The 5% overhead is a policy estimate, not a measured artifact size. Effective bit estimates are Q2_K 2.625, Q3_K_M 3.5, Q4_0 4.5, Q4_K_M 4.85, Q5_K_M 5.7, Q6_K 6.56, Q8_0 8.5, FP16/BF16 16. Mixed precision and embedding tensors mean these averages are not universal. Only quantizations represented by the selected model and runtime rules are evaluated.

For a decoder with known geometry:

```
KV = 2 × layers × KV_heads × head_dimension × context_tokens × 2 bytes
workspace = context_tokens × KV_heads × head_dimension × 16 bytes
buffers = max(0.25 GiB, weights × working_buffer_fraction) + workspace
runtime_total = weights + KV + buffers + runtime_overhead
```

The first 2 counts key and value tensors; the last 2 is FP16 storage. The separate workspace is a conservative policy allowance, not another KV allocation. GQA KV-head counts and explicit head dimensions are used where provided (not hidden_size/heads when an explicit head dimension exists). Default runtime overhead is 0.5 GiB and working-buffer fraction is 10%.

With incomplete geometry, KV falls back to 64 KiB/token/billion parameters, with at least one billion as the calculation floor. Additional workspace is 64 KiB/token. This fallback is deliberately conservative for the bundled dense GQA models, but cannot bound all possible architectures. Generic results therefore carry low confidence and never promise artifact/runtime compatibility.

Embedding encoders do not allocate a persistent decoder KV cache. Their estimate instead reserves a quadratic FP32 attention workspace for one layer (`tokens² × heads × 4`) plus linear activations (`tokens × head_dim × heads × 16`). This can overestimate implementations using optimized attention, and it does not model multi-document batching.

The vision entry always receives an unknown complete-fit verdict when other constraints do not already fail: image dimensions, encoder/projector behavior and vision activations are not bounded. Its reported total is explicitly a lower-bound text/weights calculation. It is never presented as a verified multimodal recommendation.

## Available budgets

```
safe_RAM = max(0, available_RAM - max(1 GiB, available_RAM × 15%))
safe_VRAM = min(free_VRAM, dedicated_VRAM) × 90%
disk_requirement = weights × 1.2
```

The RAM reserve is additional headroom. Existing OS/application usage is already excluded by the currently available counter, so it is not subtracted twice. Swap/pagefile is reported but never counted as physical model capacity. When free VRAM is unavailable, a present-time GPU fit is not established from total VRAM alone. Shared system graphics memory is never added to either dedicated VRAM or available RAM.

Disk headroom covers a typical download plus extra metadata, not arbitrary duplicate caches or shard merging. Checks cover the system drive. A different storage target needs a corresponding validated profile; this version does not inspect runtime model-store locations.

## Execution plans

CPU plans reserve the entire runtime total in RAM. Full-GPU plans require the entire runtime estimate to fit one device's safe free VRAM and a host loading allocation of weights + overhead + buffers to fit safe RAM. This is intentionally more conservative than lazy mmap loading.

Hybrid plans require a runtime rule permitting partial offload, a verified eligible device and at least 10% of model weights fitting after device buffers/overhead. They retain the full host runtime allocation and host KV conservatively; no assumed RAM savings are taken. This can under-recommend useful hybrid setups, but avoids manufacturing free memory. No exact layer split or tokens/second is claimed.

V1 can establish a CUDA recipe from Ollama's documented NVIDIA driver/compute-capability rules. The Toolkit is independent. AMD/Intel, Vulkan, HIP and DirectML are reported with uncertainty unless their specific usability can be established; merely enumerating a Vulkan device is insufficient. llama.cpp's CUDA build/device architecture pairing remains unverified and receives a CPU recipe. All runtime compatibility is conditional on installing/using a current suitable build and the exact catalog artifact.

## Verdicts and confidence

The evaluation precedence is known failure, unknown required data, borderline reserve/quantization/offload compromise, then good/excellent.

- `NOT_RECOMMENDED`: known platform, architecture, runtime, context, use-case, available RAM or disk constraint. An unrelated unknown does not erase a known failure.
- `UNKNOWN`: no known hard failure, but required RAM/disk/CPU/version/vision evidence is missing. Unknown never means unsupported.
- `BORDERLINE`: fits currently available memory but exceeds safety reserve, uses hybrid offload or uses effective precision below 4 bits.
- `GOOD`: satisfies modeled constraints with configured reserve.
- `EXCELLENT`: additionally uses a single-device full-GPU plan and host allocation consumes at most 70% of safe RAM. This is a capacity category, not a performance guarantee.

Measured hardware fields may have high confidence. Overall runtime memory is at most medium confidence because workspace/overhead remain estimates. Incomplete weight/geometry metadata and generic profiles lower confidence. Performance is always low-confidence qualitative guidance: full GPU `moderate`; CPU/hybrid `slow`; CPU models above 14 billion parameters `very_slow`. No numeric inference speeds are inferred.

## Ranking, without an opaque score

Configurations sort lexicographically. Fit category always precedes user preference. Each model appears once in the main list with its best evaluated recipe; every runtime/quantization evaluation remains in JSON. Rejected and unknown best recipes remain visible. Generic profiles are listed separately.

Within the same fit category:

- Balanced: effective precision nearest 4.85 bits, execution preference full GPU → hybrid → CPU, then larger parameter count.
- Quality: avoid sub-4-bit precision, prefer larger parameter capacity, then higher precision.
- Low memory: lower total execution memory, then higher precision, then parameter capacity.
- Speed: execution preference, fewer parameters, then lower runtime memory.

Installed runtime, stable model ID, quantization and runtime name break ties. Parameter count is a transparent capacity proxy, not a benchmark ranking across model families. Workload suitability is an eligibility filter rather than a made-up capability score. The bundled Qwen3 revision supports reasoning/agents; similarly named mutable tags may refer to different revisions.

Capability summaries are derived from suitable named results. A suitable full-GPU recipe with safe VRAM of at least 20 GiB is labeled workstation-class, at least 6 GiB balanced, otherwise entry. Suitable CPU recipes are CPU-focused. Without comfortable results the summary is limited/unknown. These labels describe the selected request, not the whole machine in all situations.
