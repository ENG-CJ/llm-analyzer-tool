# Source verification

Reviewed on 2026-09-09. Normal app execution does not visit these links. A verified-on date records metadata review, not a guarantee of subsequent compatibility.

## Platform and software

- [Microsoft DXGI_ADAPTER_DESC1](https://learn.microsoft.com/en-us/windows/win32/api/dxgi/ns-dxgi-dxgi_adapter_desc1): dedicated video memory and shared-system memory have different meanings. The native structure uses SIZE_T memory fields.
- [Microsoft Win32_VideoController](https://learn.microsoft.com/en-us/windows/win32/cimwin32prov/win32-videocontroller): AdapterRAM is a uint32 property; the fallback deliberately does not treat it as reliable large-VRAM evidence.
- [NVIDIA System Management Interface](https://docs.nvidia.com/deploy/nvidia-smi/index.html): local CSV queries, GPU counters and driver reporting. CUDA API capability and developer Toolkit installation are separate probes.
- [Ollama hardware support](https://docs.ollama.com/gpu): NVIDIA eligibility uses the documented compute-capability and driver branches in the versioned rules. Backend presence alone does not establish a particular artifact's execution.
- [Ollama FAQ](https://docs.ollama.com/faq): model placement, context and parallelism considerations. V1 models a single sequence and keeps conservative host allocations for hybrid plans.
- [llama.cpp build documentation](https://github.com/ggml-org/llama.cpp/blob/master/docs/build.md): backend support depends on build configuration. The app does not equate GPU vendor with a usable runtime backend.
- [PyInstaller runtime information](https://pyinstaller.org/en/stable/runtime-information.html): bundled package resources and frozen runtime behavior.
- [Typer callback documentation](https://typer.tiangolo.com/tutorial/commands/callback/), [Rich progress documentation](https://rich.readthedocs.io/en/stable/progress.html): command orchestration and progress driven by actual tasks.

## Catalog

`catalog-source-snapshot.json` records selected publisher config fields, parameter totals and GGUF file inventories from the publisher repositories' Hugging Face API. Exact source revisions are retained in each catalog entry. The source snapshot is development provenance and does not load publisher Python code (`auto_map` strings in original configs are data only).

- Qwen2.5 instruction models: publisher [0.5B](https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct), [3B](https://huggingface.co/Qwen/Qwen2.5-3B-Instruct), [7B](https://huggingface.co/Qwen/Qwen2.5-7B-Instruct), [14B](https://huggingface.co/Qwen/Qwen2.5-14B-Instruct), [32B](https://huggingface.co/Qwen/Qwen2.5-32B-Instruct), [72B](https://huggingface.co/Qwen/Qwen2.5-72B-Instruct) configs and corresponding `-GGUF` repositories.
- [Qwen2.5-Coder-7B-Instruct](https://huggingface.co/Qwen/Qwen2.5-Coder-7B-Instruct) and publisher GGUF artifacts.
- [Qwen3-4B](https://huggingface.co/Qwen/Qwen3-4B), [publisher GGUF](https://huggingface.co/Qwen/Qwen3-4B-GGUF), [Ollama Qwen3 capabilities](https://ollama.com/library/qwen3). The exact original revision is used; mutable tags are not treated as stable metadata.
- [Nomic Embed Text v1.5](https://huggingface.co/nomic-ai/nomic-embed-text-v1.5), [publisher GGUF](https://huggingface.co/nomic-ai/nomic-embed-text-v1.5-GGUF), [runtime entry](https://ollama.com/library/nomic-embed-text). Encoder context comes from the publisher's 8192-position configuration, and no decoder KV allocation is assumed.
- [Qwen2.5-VL-7B-Instruct](https://huggingface.co/Qwen/Qwen2.5-VL-7B-Instruct), [Ollama quantized artifact](https://ollama.com/library/qwen2.5vl:7b-q4_K_M). The required Ollama version is recorded, and complete vision memory remains explicitly unknown.

Generic 1/3/8/14/20/32/70B profiles are authored calculation scenarios. Their parameter counts, use cases and context are not claims about published models. All quantization and memory assumptions are documented in methodology.

To revise data, review official config/artifact inventories, update the snapshot and capability annotations in `scripts/generate_catalog.py`, regenerate the catalog and run schema, relationship and fixture tests. Updating the snapshot never downloads model weights. Do not update verification dates without reviewing the evidence.
