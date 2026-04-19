"""VLM Service — GPU detection, model management (download, load, unload).

This module manages the lifecycle of Vision-Language Models for material
classification. It uses the HuggingFace transformers + torch stack with
CUDA acceleration on NVIDIA GPUs.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from pydantic import BaseModel

from heap_analyzer.utils.logging import get_stderr_logger

_log = get_stderr_logger(__name__)

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class GpuStatus(BaseModel):
    """GPU hardware status."""

    cuda_available: bool
    cuda_version: str | None = None
    device_name: str | None = None
    vram_total_mb: int | None = None
    vram_free_mb: int | None = None


class ModelInfo(BaseModel):
    """Descriptor for a supported VLM model."""

    name: str
    display_name: str
    hf_id: str
    vram_required_mb: int
    description: str
    is_downloaded: bool = False
    warns_if_insufficient: bool = False


class DownloadProgress(BaseModel):
    """Progress of model download."""

    model_name: str
    downloaded_bytes: int
    total_bytes: int
    percent: float
    message: str


# ---------------------------------------------------------------------------
# Model registry
# ---------------------------------------------------------------------------

_MODEL_REGISTRY: list[dict[str, object]] = [
    {
        "name": "qwen2.5-vl-7b",
        "display_name": "Qwen2.5-VL 7B",
        "hf_id": "Qwen/Qwen2.5-VL-7B-Instruct",
        "vram_required_mb": 14000,
        "description": "Modello visione-linguaggio 7B parametri. Richiede ~14 GB VRAM.",
        "warns_if_insufficient": False,
    },
    {
        "name": "qwen2.5-vl-3b",
        "display_name": "Qwen2.5-VL 3B",
        "hf_id": "Qwen/Qwen2.5-VL-3B-Instruct",
        "vram_required_mb": 7000,
        "description": "Modello visione-linguaggio 3B parametri. Richiede ~7 GB VRAM.",
        "warns_if_insufficient": False,
    },
    {
        "name": "gemma-3-12b",
        "display_name": "Gemma 3 12B",
        "hf_id": "google/gemma-3-12b-it",
        "vram_required_mb": 24000,
        "description": "Modello visione-linguaggio 12B parametri. Richiede ~24 GB VRAM.",
        "warns_if_insufficient": True,
    },
]


# ---------------------------------------------------------------------------
# VLMService
# ---------------------------------------------------------------------------


class VLMService:
    """Manages VLM model lifecycle: GPU detection, download, load, unload.

    Args:
        models_dir: Directory for storing downloaded model weights.
    """

    def __init__(self, models_dir: Path) -> None:
        self._models_dir = models_dir
        self._models_dir.mkdir(parents=True, exist_ok=True)
        self._loaded_model_name: str | None = None
        self._model: object | None = None
        self._processor: object | None = None

    # ---- GPU status -------------------------------------------------------

    def check_gpu(self) -> GpuStatus:
        """Detect GPU hardware and CUDA availability."""
        try:
            import torch
        except ImportError:
            _log.warning("torch not installed — GPU detection unavailable")
            return GpuStatus(cuda_available=False)

        if not torch.cuda.is_available():
            return GpuStatus(cuda_available=False)

        try:
            device_name = torch.cuda.get_device_name(0)
            vram_total, vram_free = torch.cuda.mem_get_info(0)
            return GpuStatus(
                cuda_available=True,
                cuda_version=torch.version.cuda,
                device_name=device_name,
                vram_total_mb=int(vram_total / (1024 * 1024)),
                vram_free_mb=int(vram_free / (1024 * 1024)),
            )
        except Exception as exc:  # noqa: BLE001
            _log.error("GPU detection error: %s", exc)
            return GpuStatus(cuda_available=False)

    # ---- Model listing ----------------------------------------------------

    def list_available_models(self) -> list[ModelInfo]:
        """Return list of supported models with download status."""
        gpu = self.check_gpu()
        models: list[ModelInfo] = []
        for entry in _MODEL_REGISTRY:
            name = str(entry["name"])
            vram_req = int(entry["vram_required_mb"])  # type: ignore[arg-type]
            warns = bool(
                entry.get("warns_if_insufficient", False)
                or (gpu.vram_total_mb is not None and vram_req > gpu.vram_total_mb)
            )
            models.append(
                ModelInfo(
                    name=name,
                    display_name=str(entry["display_name"]),
                    hf_id=str(entry["hf_id"]),
                    vram_required_mb=vram_req,
                    description=str(entry["description"]),
                    is_downloaded=self.is_downloaded(name),
                    warns_if_insufficient=warns,
                )
            )
        return models

    # ---- Download ---------------------------------------------------------

    def is_downloaded(self, model_name: str) -> bool:
        """Check if a model's weights are present on disk."""
        info = self._get_registry_entry(model_name)
        hf_id = str(info["hf_id"])
        # Check for the snapshot directory from huggingface_hub
        model_dir = self._model_path(hf_id)
        if model_dir is not None and model_dir.exists():
            # Must contain at least a config.json to be considered complete
            return (model_dir / "config.json").exists()
        return False

    def download_model(
        self,
        model_name: str,
        progress_cb: Callable[[DownloadProgress], None] | None = None,
    ) -> None:
        """Download model weights from HuggingFace Hub.

        Args:
            model_name: Short model name (e.g. 'qwen2.5-vl-7b').
            progress_cb: Optional callback for download progress updates.
        """
        from huggingface_hub import snapshot_download

        info = self._get_registry_entry(model_name)
        hf_id = str(info["hf_id"])

        _log.info("Downloading model %s (%s) to %s", model_name, hf_id, self._models_dir)

        if progress_cb:
            progress_cb(DownloadProgress(
                model_name=model_name,
                downloaded_bytes=0,
                total_bytes=0,
                percent=0.0,
                message=f"Avvio download {model_name}...",
            ))

        snapshot_download(
            repo_id=hf_id,
            cache_dir=str(self._models_dir),
            # Ignore large safetensors shards that are not needed for inference
            # (the model will pick the right format automatically)
            ignore_patterns=["*.bin", "*.msgpack", "consolidated*"],
        )

        if progress_cb:
            progress_cb(DownloadProgress(
                model_name=model_name,
                downloaded_bytes=0,
                total_bytes=0,
                percent=100.0,
                message=f"Download {model_name} completato",
            ))

        _log.info("Download complete for %s", model_name)

    # ---- Load / Unload ----------------------------------------------------

    def load_model(self, model_name: str) -> None:
        """Load a downloaded model onto the GPU.

        Args:
            model_name: Short model name.

        Raises:
            RuntimeError: If model not downloaded or CUDA not available.
        """
        if self._loaded_model_name == model_name:
            _log.info("Model %s already loaded", model_name)
            return

        if self._loaded_model_name is not None:
            self.unload_model()

        if not self.is_downloaded(model_name):
            raise RuntimeError(f"Model {model_name} is not downloaded")

        gpu = self.check_gpu()
        if not gpu.cuda_available:
            raise RuntimeError("CUDA not available — cannot load VLM model")

        import torch

        info = self._get_registry_entry(model_name)
        hf_id = str(info["hf_id"])

        _log.info("Loading model %s (%s) onto GPU...", model_name, hf_id)

        # Use model-specific class for Qwen2.5-VL, AutoModel for others
        if "qwen2.5-vl" in model_name:
            from transformers import AutoProcessor, Qwen2_5_VLForConditionalGeneration

            model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
                hf_id,
                cache_dir=str(self._models_dir),
                torch_dtype=torch.float16,
                device_map="auto",
                attn_implementation="sdpa",
            )
            processor = AutoProcessor.from_pretrained(
                hf_id,
                cache_dir=str(self._models_dir),
            )
        else:
            from transformers import AutoModelForImageTextToText, AutoProcessor

            model = AutoModelForImageTextToText.from_pretrained(
                hf_id,
                cache_dir=str(self._models_dir),
                torch_dtype=torch.float16,
                device_map="auto",
                attn_implementation="sdpa",
            )
            processor = AutoProcessor.from_pretrained(
                hf_id,
                cache_dir=str(self._models_dir),
            )

        self._model = model
        self._processor = processor
        self._loaded_model_name = model_name

        _log.info("Model %s loaded successfully", model_name)

    def unload_model(self) -> None:
        """Unload the current model from GPU memory."""
        if self._model is None:
            return

        model_name = self._loaded_model_name
        _log.info("Unloading model %s...", model_name)

        del self._model
        del self._processor
        self._model = None
        self._processor = None
        self._loaded_model_name = None

        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                import gc

                gc.collect()
        except ImportError:
            pass

        _log.info("Model %s unloaded", model_name)

    def loaded_model(self) -> str | None:
        """Return the name of the currently loaded model, or None."""
        return self._loaded_model_name

    @property
    def model(self) -> object:
        """Return the loaded model instance. Raises if no model loaded."""
        if self._model is None:
            raise RuntimeError("No model loaded — call load_model() first")
        return self._model

    @property
    def processor(self) -> object:
        """Return the loaded processor instance. Raises if no model loaded."""
        if self._processor is None:
            raise RuntimeError("No model loaded — call load_model() first")
        return self._processor

    # ---- Internal ---------------------------------------------------------

    def _get_registry_entry(self, model_name: str) -> dict[str, object]:
        """Look up a model by short name in the registry."""
        for entry in _MODEL_REGISTRY:
            if entry["name"] == model_name:
                return entry
        available = [str(e["name"]) for e in _MODEL_REGISTRY]
        raise ValueError(f"Unknown model '{model_name}'. Available: {available}")

    def _model_path(self, hf_id: str) -> Path | None:
        """Resolve the local path where a HF model's snapshot lives.

        HuggingFace Hub stores snapshots under:
        cache_dir/models--org--name/snapshots/<hash>/
        """
        # Convert hf_id like "Qwen/Qwen2.5-VL-7B-Instruct" to dir name
        dir_name = f"models--{hf_id.replace('/', '--')}"
        model_base = self._models_dir / dir_name
        if not model_base.exists():
            return None

        snapshots_dir = model_base / "snapshots"
        if not snapshots_dir.exists():
            return None

        # Return the first (most recent) snapshot directory
        snapshot_dirs = sorted(
            snapshots_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True,
        )
        return snapshot_dirs[0] if snapshot_dirs else None
