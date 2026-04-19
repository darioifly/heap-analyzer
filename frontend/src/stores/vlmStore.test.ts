import { describe, it, expect, beforeEach, vi } from 'vitest';
import { useVlmStore } from './vlmStore';

// Mock window.api.vlm
const mockVlmApi = {
  gpuInfo: vi.fn(),
  listModels: vi.fn(),
  isDownloaded: vi.fn(),
  download: vi.fn(),
  cancelDownload: vi.fn(),
  onDownloadProgress: vi.fn(),
  removeDownloadListeners: vi.fn(),
};

Object.defineProperty(globalThis, 'window', {
  value: {
    api: {
      vlm: mockVlmApi,
    },
  },
  writable: true,
});

describe('vlmStore', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useVlmStore.setState({
      gpuStatus: null,
      models: [],
      downloadProgress: {},
      loadedModel: null,
      isLoading: false,
      error: null,
    });
  });

  it('refreshGpuStatus sets gpuStatus on success', async () => {
    const mockStatus = {
      cuda_available: true,
      cuda_version: '12.1',
      device_name: 'NVIDIA GeForce RTX 3090',
      vram_total_mb: 24576,
      vram_free_mb: 20000,
    };
    mockVlmApi.gpuInfo.mockResolvedValue(mockStatus);

    await useVlmStore.getState().refreshGpuStatus();
    expect(useVlmStore.getState().gpuStatus).toEqual(mockStatus);
  });

  it('refreshGpuStatus sets error on failure', async () => {
    mockVlmApi.gpuInfo.mockRejectedValue(new Error('IPC failed'));

    await useVlmStore.getState().refreshGpuStatus();
    expect(useVlmStore.getState().error).toBe('IPC failed');
  });

  it('refreshModels populates models array', async () => {
    const mockModels = [
      {
        name: 'qwen2.5-vl-7b',
        display_name: 'Qwen2.5-VL 7B',
        hf_id: 'Qwen/Qwen2.5-VL-7B-Instruct',
        vram_required_mb: 14000,
        description: 'Test',
        is_downloaded: false,
        warns_if_insufficient: false,
      },
    ];
    mockVlmApi.listModels.mockResolvedValue(mockModels);

    await useVlmStore.getState().refreshModels();
    expect(useVlmStore.getState().models).toHaveLength(1);
    expect(useVlmStore.getState().models[0].name).toBe('qwen2.5-vl-7b');
  });

  it('downloadModel sets and clears progress', async () => {
    mockVlmApi.download.mockResolvedValue({ success: true });
    mockVlmApi.listModels.mockResolvedValue([]);

    await useVlmStore.getState().downloadModel('qwen2.5-vl-7b');

    // After completion, progress should be cleared
    expect(useVlmStore.getState().downloadProgress).not.toHaveProperty('qwen2.5-vl-7b');
    expect(mockVlmApi.removeDownloadListeners).toHaveBeenCalled();
  });

  it('handleDownloadProgress updates progress state', () => {
    useVlmStore.getState().handleDownloadProgress({
      model_name: 'qwen2.5-vl-7b',
      percent: 45,
      message: 'Downloading...',
    });

    const progress = useVlmStore.getState().downloadProgress['qwen2.5-vl-7b'];
    expect(progress).toBeDefined();
    expect(progress.percent).toBe(45);
  });

  it('cancelDownload calls IPC cancel', () => {
    useVlmStore.getState().cancelDownload('qwen2.5-vl-7b');
    expect(mockVlmApi.cancelDownload).toHaveBeenCalled();
  });

  it('sets error when refreshModels fails', async () => {
    mockVlmApi.listModels.mockRejectedValue(new Error('Network error'));

    await useVlmStore.getState().refreshModels();
    expect(useVlmStore.getState().error).toBe('Network error');
  });
});
