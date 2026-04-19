import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import { VLMSettings } from './VLMSettings';
import { useVlmStore } from '@/stores/vlmStore';
import type { GpuStatus, ModelInfo } from '@/stores/vlmStore';

// Standard GPU and model fixtures
const GPU_AVAILABLE: GpuStatus = {
  cuda_available: true,
  cuda_version: '12.1',
  device_name: 'NVIDIA GeForce RTX 3090',
  vram_total_mb: 24576,
  vram_free_mb: 20000,
};

const GPU_UNAVAILABLE: GpuStatus = {
  cuda_available: false,
  cuda_version: null,
  device_name: null,
  vram_total_mb: null,
  vram_free_mb: null,
};

const MODEL_NOT_DOWNLOADED: ModelInfo = {
  name: 'qwen2.5-vl-7b',
  display_name: 'Qwen2.5-VL 7B',
  hf_id: 'Qwen/Qwen2.5-VL-7B-Instruct',
  vram_required_mb: 14000,
  description: 'Test model',
  is_downloaded: false,
  warns_if_insufficient: false,
};

const MODEL_DOWNLOADED: ModelInfo = {
  ...MODEL_NOT_DOWNLOADED,
  is_downloaded: true,
};

// Mock window.api.vlm on the existing window object
const mockVlmApi = {
  gpuInfo: vi.fn(),
  listModels: vi.fn(),
  isDownloaded: vi.fn(),
  download: vi.fn(),
  cancelDownload: vi.fn(),
  onDownloadProgress: vi.fn(),
  removeDownloadListeners: vi.fn(),
};

beforeEach(() => {
  // Attach mock API to existing window (don't replace window)
  (window as unknown as Record<string, unknown>).api = { vlm: mockVlmApi };
});

describe('VLMSettings', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Default mocks
    mockVlmApi.gpuInfo.mockResolvedValue(GPU_UNAVAILABLE);
    mockVlmApi.listModels.mockResolvedValue([]);
    // Reset store
    useVlmStore.setState({
      gpuStatus: null,
      models: [],
      downloadProgress: {},
      loadedModel: null,
      isLoading: false,
      error: null,
    });
  });

  it('renders GPU non disponibile when cuda not available', async () => {
    mockVlmApi.gpuInfo.mockResolvedValue(GPU_UNAVAILABLE);
    mockVlmApi.listModels.mockResolvedValue([]);

    await act(async () => {
      render(<VLMSettings />);
    });

    expect(screen.getByText(/GPU CUDA non disponibile/)).toBeDefined();
  });

  it('renders GPU available when cuda is available', async () => {
    mockVlmApi.gpuInfo.mockResolvedValue(GPU_AVAILABLE);
    mockVlmApi.listModels.mockResolvedValue([]);

    await act(async () => {
      render(<VLMSettings />);
    });

    expect(screen.getByText(/CUDA disponibile/)).toBeDefined();
    expect(screen.getByText(/RTX 3090/)).toBeDefined();
  });

  it('renders model table with models', async () => {
    mockVlmApi.gpuInfo.mockResolvedValue(GPU_AVAILABLE);
    mockVlmApi.listModels.mockResolvedValue([MODEL_NOT_DOWNLOADED]);

    await act(async () => {
      render(<VLMSettings />);
    });

    expect(screen.getByText('Qwen2.5-VL 7B')).toBeDefined();
    expect(screen.getByText('Da scaricare')).toBeDefined();
    expect(screen.getByText('Scarica')).toBeDefined();
  });

  it('shows Scaricato badge when model is downloaded', async () => {
    mockVlmApi.gpuInfo.mockResolvedValue(GPU_AVAILABLE);
    mockVlmApi.listModels.mockResolvedValue([MODEL_DOWNLOADED]);

    await act(async () => {
      render(<VLMSettings />);
    });

    expect(screen.getByText('Scaricato')).toBeDefined();
  });

  it('disables download button when GPU unavailable', async () => {
    mockVlmApi.gpuInfo.mockResolvedValue(GPU_UNAVAILABLE);
    mockVlmApi.listModels.mockResolvedValue([MODEL_NOT_DOWNLOADED]);

    await act(async () => {
      render(<VLMSettings />);
    });

    const btn = screen.getByText('Scarica');
    expect(btn.closest('button')?.disabled).toBe(true);
  });

  it('shows progress bar during download', async () => {
    mockVlmApi.gpuInfo.mockResolvedValue(GPU_AVAILABLE);
    mockVlmApi.listModels.mockResolvedValue([MODEL_NOT_DOWNLOADED]);

    useVlmStore.setState({
      downloadProgress: {
        'qwen2.5-vl-7b': {
          model_name: 'qwen2.5-vl-7b',
          percent: 42,
          message: 'Downloading...',
        },
      },
    });

    await act(async () => {
      render(<VLMSettings />);
    });

    expect(screen.getByText('42%')).toBeDefined();
  });
});
