/**
 * VLM Service — Electron-side orchestrator for VLM operations.
 *
 * Spawns Python CLI commands and forwards JSON Lines progress to the renderer.
 */

import { app, BrowserWindow } from 'electron';
import path from 'path';
import { PythonBridge } from '../ipc/python-bridge';
import type { ResultMessage } from '../ipc/python-bridge';

/** GPU hardware status. */
export interface GpuStatus {
  cuda_available: boolean;
  cuda_version: string | null;
  device_name: string | null;
  vram_total_mb: number | null;
  vram_free_mb: number | null;
}

/** VLM model descriptor. */
export interface ModelInfo {
  name: string;
  display_name: string;
  hf_id: string;
  vram_required_mb: number;
  description: string;
  is_downloaded: boolean;
  warns_if_insufficient: boolean;
}

/** Download progress payload sent to renderer. */
export interface VlmDownloadProgress {
  model_name: string;
  phase: string;
  percent: number;
  message: string;
}

/** Returns the models directory path. */
function getModelsDir(): string {
  return path.join(app.getPath('userData'), 'heap-analyzer', 'models');
}

/** Active download bridge — kept alive for cancellation. */
let activeBridge: PythonBridge | null = null;

export async function getGpuInfo(): Promise<GpuStatus> {
  const bridge = new PythonBridge();
  const result: ResultMessage = await bridge.execute('vlm', ['gpu-info']);
  return result.data as unknown as GpuStatus;
}

export async function listModels(): Promise<ModelInfo[]> {
  const bridge = new PythonBridge();
  const result: ResultMessage = await bridge.execute('vlm', [
    'list-models',
    '--models-dir',
    getModelsDir(),
  ]);
  const data = result.data as { models: ModelInfo[] };
  return data.models;
}

export async function isModelDownloaded(modelName: string): Promise<boolean> {
  const bridge = new PythonBridge();
  const result: ResultMessage = await bridge.execute('vlm', [
    'is-downloaded',
    '--model',
    modelName,
    '--models-dir',
    getModelsDir(),
  ]);
  const data = result.data as { downloaded: boolean };
  return data.downloaded;
}

export async function downloadModel(
  modelName: string,
  sender: BrowserWindow['webContents'],
): Promise<void> {
  activeBridge = new PythonBridge(60 * 60 * 1000); // 1 hour timeout for download

  activeBridge.on('progress', (data: VlmDownloadProgress) => {
    sender.send('vlm:downloadProgress', {
      model_name: modelName,
      phase: data.phase,
      percent: data.percent,
      message: data.message,
    });
  });

  try {
    await activeBridge.execute('vlm', [
      'download',
      '--model',
      modelName,
      '--models-dir',
      getModelsDir(),
    ]);
  } finally {
    activeBridge = null;
  }
}

export function cancelDownload(): void {
  activeBridge?.cancel();
}
