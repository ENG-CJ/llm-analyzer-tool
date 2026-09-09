# Changelog

## 0.1.0 — initial implementation

- Windows x64 CIM/DXGI/CPUID/psutil hardware scanning with NVIDIA memory fallbacks and per-field evidence.
- Separate CUDA driver and Toolkit states; conservative GPU/runtime support rules.
- Versioned catalog with 10 named models and seven explicitly generic capacity profiles.
- Deterministic memory, context, disk, runtime and use-case checks; explanations and visible rejections/unknowns.
- Guided Typer/Rich CLI, saved-scan analysis, clean JSON output, configuration and rotating logs.
- Markdown, JSON, text and standalone escaped HTML reports with safe custom paths.
- Optional confirmed CPU hashing benchmark, without inferred LLM throughput.
- Synthetic fixture tests, strict typing, lint, Windows/Linux CI and Windows PyInstaller release workflow.

Runtime/model execution is not benchmarked or guaranteed. Multimodal memory remains unknown; non-NVIDIA GPU execution requires further device/runtime validation. No automatic installations, downloads or system modifications are performed.
