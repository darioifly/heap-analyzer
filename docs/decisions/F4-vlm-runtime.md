# F4 VLM Runtime Decision: transformers + torch

## Decision

Use **`transformers` + `torch`** (HuggingFace ecosystem) for local VLM inference on RTX 3090.

## Comparison

| Criterion | transformers + torch | llama-cpp-python (GGUF) |
|---|---|---|
| **VRAM for Qwen2.5-VL-7B** | ~14 GB (FP16/BF16) | ~5-8 GB (Q4/Q5 quant) — but vision quality drops |
| **Windows CUDA install** | Pre-built wheels via `--index-url https://download.pytorch.org/whl/cu121` — no build tools needed | Requires CUDA toolkit + C++ compiler (Visual Studio Build Tools) for GPU build; fragile on Windows |
| **Batched inference** | Native `model.generate()` with batched inputs; `AutoProcessor` handles multi-image batching | Single-request only; no native batch support for vision models |
| **Streaming output** | Supported via `TextStreamer` / `TextIteratorStreamer` | Supported natively |
| **Model availability** | First-class support: Qwen2.5-VL, Gemma-3 vision available as official HF checkpoints | Qwen2.5-VL GGUF: community-only, vision support incomplete; Gemma-3 GGUF: limited |
| **Vision model maturity** | `AutoModelForImageTextToText` is the official pipeline; well-tested for Qwen2.5-VL | llama.cpp vision (llava-cli) is less mature; Qwen2-VL support is experimental |

## Rationale

1. **Model quality**: FP16 inference preserves full model quality for material classification — critical since we're classifying visually similar industrial materials (scrap vs. cast iron vs. slag).
2. **RTX 3090 has 24 GB VRAM**: Qwen2.5-VL-7B at ~14 GB FP16 fits comfortably with room for the image.
3. **Windows ergonomics**: `pip install torch --index-url ...cu121` is a one-liner. `llama-cpp-python` with CUDA requires `CMAKE_ARGS`, CUDA toolkit, and VS Build Tools — a known pain point on Windows.
4. **Official model support**: Qwen2.5-VL and Gemma-3 both publish official HF weights with tested `transformers` integration. GGUF equivalents for vision models are community-maintained and less reliable.
5. **Batch capability**: We classify 4-50 heaps per survey. Batched inference saves time vs. sequential GGUF calls.

## Trade-offs accepted

- **Larger download**: ~14 GB model weights vs. ~5 GB GGUF. Acceptable for a desktop app with persistent cache.
- **Higher VRAM usage**: 14 GB vs. 5-8 GB. RTX 3090 has 24 GB — sufficient.
- **Slower first load**: ~30s model load time. Mitigated by keeping model loaded across classification session.

## Implementation

- Pin `torch` with CUDA 12.1 index URL in `pyproject.toml`
- Use `AutoModelForImageTextToText` + `AutoProcessor` from `transformers`
- Use `huggingface_hub.snapshot_download()` for model download with progress
- Models cached in `app.getPath('userData')/heap-analyzer/models`
