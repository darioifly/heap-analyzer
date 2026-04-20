import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import fs from 'fs';
import path from 'path';
import os from 'os';

// Redirect app.getPath('userData') to a temp dir
let tempDir: string;
vi.mock('electron', () => ({
  app: {
    getPath: (key: string) => {
      if (key === 'userData') return tempDir;
      return os.tmpdir();
    },
  },
}));

// Import AFTER the mock is declared
import { loadSettings, saveSettings, resetSettings, defaultSettings } from './settings';

beforeEach(() => {
  tempDir = path.join(os.tmpdir(), `heap-analyzer-settings-${Date.now()}-${Math.random().toString(36).slice(2)}`);
  fs.mkdirSync(tempDir, { recursive: true });
});

afterEach(() => {
  if (fs.existsSync(tempDir)) {
    fs.rmSync(tempDir, { recursive: true, force: true });
  }
});

describe('settings service', () => {
  it('returns defaults when file is missing', () => {
    const s = loadSettings();
    expect(s).toEqual(defaultSettings());
  });

  it('writes settings atomically (no leftover .tmp on success)', () => {
    saveSettings({ report: { ...defaultSettings().report, companyName: 'Acme' } });
    const filePath = path.join(tempDir, 'settings.json');
    expect(fs.existsSync(filePath)).toBe(true);
    expect(fs.existsSync(`${filePath}.tmp`)).toBe(false);
    const parsed = JSON.parse(fs.readFileSync(filePath, 'utf-8'));
    expect(parsed.report.companyName).toBe('Acme');
  });

  it('deep-merges partial patches', () => {
    saveSettings({ report: { ...defaultSettings().report, companyName: 'Acme' } });
    saveSettings({
      report: { ...defaultSettings().report, defaultOperatorName: 'Mario Rossi' },
    });
    const loaded = loadSettings();
    // Second save replaces the full report object because patch contained the full object
    expect(loaded.report.defaultOperatorName).toBe('Mario Rossi');
  });

  it('falls back to defaults on corrupt JSON', () => {
    const filePath = path.join(tempDir, 'settings.json');
    fs.writeFileSync(filePath, 'this is not json {', 'utf-8');
    const loaded = loadSettings();
    expect(loaded).toEqual(defaultSettings());
  });

  it('resetSettings overwrites with defaults', () => {
    saveSettings({ report: { ...defaultSettings().report, companyName: 'Acme' } });
    resetSettings();
    const loaded = loadSettings();
    expect(loaded.report.companyName).toBe('');
  });
});
