"""Rebuild bundled data from reviewed, checked-in publisher metadata snapshots (offline)."""

import json
import re
from pathlib import Path

from llm_analyzer.catalog.schemas import QUANT_BITS, Catalog, RuntimeRules

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    snapshot = json.loads((ROOT / "docs/catalog-source-snapshot.json").read_text(encoding="utf-8"))
    quant_metadata = {item["repo"]: item for item in snapshot["quantizations"]}
    models = []
    for meta in snapshot["models"]:
        repo, cfg = meta["repo"], meta["config"]
        name = repo.split("/")[-1]
        vision, embedding = "VL-" in name, "nomic-embed" in name
        quant_meta = quant_metadata.get(repo + "-GGUF")
        quants = []
        if quant_meta:
            for quant, bits in QUANT_BITS.items():
                pattern = "(?:fp16|f16)" if quant == "FP16" else re.escape(quant)
                matched = [
                    file
                    for file in quant_meta["files"]
                    if re.search(
                        r"[.-]" + pattern + r"(?:-\d{5}-of-\d{5})?\.gguf$", file["name"], re.I
                    )
                ]
                if not matched:
                    continue
                whole = [
                    file for file in matched if not re.search(r"-\d{5}-of-\d{5}", file["name"])
                ]
                chosen = whole[:1] or matched
                if not whole:
                    shard_count = int(re.search(r"-of-(\d{5})", chosen[0]["name"])[1])
                    if len(chosen) != shard_count:
                        raise ValueError("Incomplete GGUF shard set")
                quants.append(
                    {
                        "name": quant,
                        "bits_estimate": bits,
                        "file_size_bytes": sum(file["size"] for file in chosen),
                        "source": f"https://huggingface.co/{quant_meta['repo']}/tree/{quant_meta['sha']}",
                    }
                )
        elif vision:
            quants = [
                {
                    "name": "Q4_K_M",
                    "bits_estimate": QUANT_BITS["Q4_K_M"],
                    "source": "https://ollama.com/library/qwen2.5vl:7b-q4_K_M",
                }
            ]
        else:
            raise ValueError(f"No artifact metadata: {repo}")
        capabilities = (
            ["embeddings"]
            if embedding
            else ["multimodal", "chat"]
            if vision
            else ["coding", "chat"]
            if "Coder" in name
            else ["chat", "rag", "coding", "reasoning", "agents"]
            if "Qwen3" in name
            else ["chat", "rag"]
        )
        model = {
            "id": name.lower(),
            "display_name": name,
            "family": "Nomic BERT" if embedding else "Qwen3" if "Qwen3" in name else "Qwen2.5",
            "publisher": repo.split("/")[0],
            "parameters": meta["safetensors"]["total"],
            "architecture": cfg["model_type"],
            "modalities": ["text", "image"] if vision else ["text"],
            "capabilities": capabilities,
            "context_maximum": cfg["n_positions"]
            if embedding
            else min(cfg["max_position_embeddings"], 32768)
            if vision
            else cfg["max_position_embeddings"],
            "layers": cfg["num_hidden_layers"],
            "kv_heads": cfg.get("num_key_value_heads", cfg["num_attention_heads"]),
            "head_dim": cfg.get("head_dim", cfg["hidden_size"] // cfg["num_attention_heads"]),
            "embedding": embedding,
            "quantizations": quants,
            "runtime_support": ["ollama"] if vision else ["ollama", "llama.cpp"],
            "runtime_minimum_versions": {"ollama": "0.7.0"} if vision else {},
            "sources": [
                f"https://huggingface.co/{repo}/blob/{meta['sha']}/config.json",
                f"https://huggingface.co/{repo}",
            ],
            "source_revision": meta["sha"],
            "last_verified_at": snapshot["verified_at"],
            "metadata_confidence": "high",
            "notes": [
                "Use this exact publisher artifact; similarly named mutable runtime tags may refer to a different model revision."
            ],
        }
        if vision:
            model["sources"].append("https://ollama.com/library/qwen2.5vl:7b-q4_K_M")
            model["notes"].append(
                "Vision configuration is included for explicit uncertainty analysis; image memory has not been calibrated."
            )
        if embedding:
            model["notes"].append(
                "Use task prefixes from the model card; embeddings do not generate chat responses."
            )
        models.append(model)
    for size in (1, 3, 8, 14, 20, 32, 70):
        models.append(
            {
                "id": f"generic-{size}b",
                "display_name": f"Generic {size}B dense capacity estimate",
                "family": "Generic",
                "publisher": "Hypothetical profile",
                "parameters": size * 10**9,
                "architecture": "generic_dense",
                "modalities": ["text"],
                "capabilities": ["chat", "rag", "coding", "agents", "reasoning"],
                "context_maximum": 32768,
                "generic": True,
                "quantizations": [
                    {"name": q, "bits_estimate": bits} for q, bits in QUANT_BITS.items()
                ],
                "runtime_support": ["ollama", "llama.cpp"],
                "sources": ["https://github.com/ggml-org/llama.cpp"],
                "last_verified_at": snapshot["verified_at"],
                "metadata_confidence": "low",
                "notes": [
                    "Sizes and context are illustrative scenarios; no specific artifact or capability is verified."
                ],
            }
        )
    catalog = Catalog.model_validate({"catalog_version": "2026.09.09", "models": models})
    runtimes = []
    for runtime in ("ollama", "llama.cpp"):
        runtimes.append(
            {
                "name": runtime,
                "platforms": ["windows"],
                "architectures": ["x86_64"],
                "model_architectures": ["qwen2", "qwen3", "nomic_bert", "qwen2_5_vl"]
                if runtime == "ollama"
                else ["qwen2", "qwen3", "nomic_bert"],
                "formats": ["gguf"],
                "quantizations": list(QUANT_BITS),
                "backends": ["cpu", "cuda", "vulkan"],
                "partial_offload": True,
                "required_cpu_flags": ["avx2"],
                "cuda": {
                    "minimum_compute_capability": 5.0,
                    "minimum_driver_major": 550,
                    "legacy_compute_below": 6.3,
                    "legacy_minimum_driver_major": 570,
                }
                if runtime == "ollama"
                else None,
                "source": "https://docs.ollama.com/gpu"
                if runtime == "ollama"
                else "https://github.com/ggml-org/llama.cpp/blob/master/docs/build.md",
                "last_verified_at": snapshot["verified_at"],
                "note": "Targets an AVX2-capable current Windows x64 build. This is a conservative analyzer policy; custom baseline CPU builds may work on older CPUs. CUDA recipe eligibility is established only for Ollama's documented device/driver matrix. Other backend builds require manual validation.",
            }
        )
    rules = RuntimeRules.model_validate({"rules_version": "2026.09.09", "runtimes": runtimes})
    target = ROOT / "src/llm_analyzer/data"
    target.mkdir(parents=True, exist_ok=True)
    (target / "models.json").write_text(catalog.model_dump_json(indent=2) + "\n", encoding="utf-8")
    (target / "runtime_rules.json").write_text(
        rules.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )
    print(f"Generated {len(models)} catalog entries from reviewed snapshots")


if __name__ == "__main__":
    main()
