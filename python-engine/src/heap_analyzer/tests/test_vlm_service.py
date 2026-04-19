"""Tests for VLM service — GPU detection, model listing, download, load/unload.

These tests use the REAL GPU and REAL model downloads.
First run will download Qwen2.5-VL-7B (~14 GB) and takes ~20 minutes.
Subsequent runs use cached weights.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from heap_analyzer.classification.vlm_service import (
    GpuStatus,
    ModelInfo,
    VLMService,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def models_dir() -> Path:
    """Persistent models directory — NOT tmp_path, survives across runs."""
    env_dir = os.environ.get("HEAP_ANALYZER_MODELS_DIR")
    d = Path(env_dir) if env_dir else Path.home() / ".cache" / "heap-analyzer" / "models"
    d.mkdir(parents=True, exist_ok=True)
    return d


@pytest.fixture(scope="session")
def vlm_service(models_dir: Path) -> VLMService:
    """Session-scoped VLMService instance."""
    return VLMService(models_dir=models_dir)


# ---------------------------------------------------------------------------
# GPU detection tests
# ---------------------------------------------------------------------------

class TestGpuDetection:
    """Tests for GPU/CUDA detection."""

    def test_check_gpu_returns_gpu_status(self, vlm_service: VLMService) -> None:
        """check_gpu() returns a valid GpuStatus."""
        status = vlm_service.check_gpu()
        assert isinstance(status, GpuStatus)
        assert isinstance(status.cuda_available, bool)

    def test_check_gpu_reports_cuda(self, vlm_service: VLMService) -> None:
        """GPU should be CUDA-capable (RTX 3090 expected)."""
        status = vlm_service.check_gpu()
        # If torch CUDA is not available, skip gracefully
        if not status.cuda_available:
            pytest.skip(
                "CUDA not available — torch may not be built with CUDA support. "
                "Install torch with CUDA: pip install torch --index-url "
                "https://download.pytorch.org/whl/cu121"
            )
        assert status.cuda_version is not None
        assert status.device_name is not None
        assert status.vram_total_mb is not None
        assert status.vram_total_mb >= 20000, (
            f"Expected >= 20 GB VRAM (RTX 3090), got {status.vram_total_mb} MB"
        )


# ---------------------------------------------------------------------------
# Model listing tests
# ---------------------------------------------------------------------------

class TestModelListing:
    """Tests for model listing."""

    def test_list_models_contains_qwen_7b(self, vlm_service: VLMService) -> None:
        """list_available_models() includes qwen2.5-vl-7b."""
        models = vlm_service.list_available_models()
        names = [m.name for m in models]
        assert "qwen2.5-vl-7b" in names

    def test_list_models_returns_model_info(self, vlm_service: VLMService) -> None:
        """All returned models have valid fields."""
        models = vlm_service.list_available_models()
        assert len(models) >= 2
        for m in models:
            assert isinstance(m, ModelInfo)
            assert m.name
            assert m.hf_id
            assert m.vram_required_mb > 0

    def test_is_downloaded_false_for_unknown(self, vlm_service: VLMService) -> None:
        """is_downloaded() raises for unknown model name."""
        with pytest.raises(ValueError, match="Unknown model"):
            vlm_service.is_downloaded("nonexistent-model")


# ---------------------------------------------------------------------------
# Download + Load tests (REAL — slow on first run)
# ---------------------------------------------------------------------------

class TestDownloadAndLoad:
    """Real download and GPU load tests. First run downloads ~14 GB."""

    @pytest.mark.slow
    def test_download_qwen_7b_real(self, vlm_service: VLMService) -> None:
        """Download Qwen2.5-VL-7B weights (cached after first run)."""
        progress_messages: list[str] = []

        def on_progress(p: object) -> None:
            from heap_analyzer.classification.vlm_service import DownloadProgress
            if isinstance(p, DownloadProgress):
                progress_messages.append(p.message)

        vlm_service.download_model("qwen2.5-vl-7b", progress_cb=on_progress)
        assert vlm_service.is_downloaded("qwen2.5-vl-7b")
        assert len(progress_messages) >= 1

    @pytest.mark.slow
    def test_load_and_unload_qwen_7b_real(self, vlm_service: VLMService) -> None:
        """Load model onto GPU, verify VRAM usage, then unload."""
        gpu_before = vlm_service.check_gpu()
        if not gpu_before.cuda_available:
            pytest.skip("CUDA not available")

        if not vlm_service.is_downloaded("qwen2.5-vl-7b"):
            pytest.skip("Model not downloaded — run test_download_qwen_7b_real first")

        vlm_service.load_model("qwen2.5-vl-7b")
        assert vlm_service.loaded_model() == "qwen2.5-vl-7b"

        gpu_loaded = vlm_service.check_gpu()
        assert gpu_loaded.vram_free_mb is not None
        assert gpu_before.vram_free_mb is not None
        vram_used = gpu_before.vram_free_mb - gpu_loaded.vram_free_mb
        assert vram_used > 10000, f"Expected >10 GB VRAM consumed, got {vram_used} MB"

        vlm_service.unload_model()
        assert vlm_service.loaded_model() is None


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------

class TestVlmCli:
    """Test VLM CLI commands emit valid JSON Lines."""

    def test_cli_gpu_info_emits_json(self) -> None:
        """vlm gpu-info emits valid JSON Lines."""
        result = subprocess.run(
            ["py", "-3.11", "-m", "heap_analyzer.cli", "vlm", "gpu-info"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        for line in result.stdout.strip().split("\n"):
            if line.strip():
                parsed = json.loads(line)
                assert "type" in parsed

    def test_cli_list_models_emits_json(self) -> None:
        """vlm list-models emits valid JSON Lines."""
        result = subprocess.run(
            ["py", "-3.11", "-m", "heap_analyzer.cli", "vlm", "list-models"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        for line in result.stdout.strip().split("\n"):
            if line.strip():
                parsed = json.loads(line)
                assert "type" in parsed
                if parsed["type"] == "result":
                    assert "models" in parsed["data"]

    def test_cli_is_downloaded_emits_json(self) -> None:
        """vlm is-downloaded emits valid JSON Lines."""
        result = subprocess.run(
            [
                "py", "-3.11", "-m", "heap_analyzer.cli",
                "vlm", "is-downloaded", "--model", "qwen2.5-vl-7b",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        for line in result.stdout.strip().split("\n"):
            if line.strip():
                parsed = json.loads(line)
                assert "type" in parsed
                if parsed["type"] == "result":
                    assert "downloaded" in parsed["data"]
