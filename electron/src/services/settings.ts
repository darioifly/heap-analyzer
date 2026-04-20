/**
 * Persistent user settings — loaded from and saved to `<userData>/settings.json`.
 *
 * Writes are atomic (tmp file + rename) so a crash mid-write never corrupts
 * the JSON. Parse errors fall back to defaults rather than throwing.
 */

import fs from 'fs';
import path from 'path';
import { app } from 'electron';
import { z } from 'zod';

// ---------------------------------------------------------------------------
// Schema — keep in sync with frontend/src/stores/settingsStore.ts
// ---------------------------------------------------------------------------

export const SettingsSchema = z.object({
  general: z.object({
    dataDir: z.string().nullable().default(null),
    language: z.enum(['it']).default('it'),
    theme: z.enum(['dark', 'light']).default('dark'),
  }),
  processing: z.object({
    overrides: z.record(z.string(), z.union([z.number(), z.string(), z.boolean()])).default({}),
    pythonExecutable: z.string().nullable().default(null),
  }),
  vlm: z.object({
    modelsDir: z.string().nullable().default(null),
    preferredModel: z.string().nullable().default(null),
    estimatedVramGb: z.number().min(2).max(24).default(8),
  }),
  report: z.object({
    logoPath: z.string().nullable().default(null),
    companyName: z.string().default(''),
    defaultOperatorName: z.string().default(''),
    footerText: z.string().default(''),
  }),
});

export type Settings = z.infer<typeof SettingsSchema>;

/**
 * Build the default Settings object.
 *
 * Zod 4 treats each nested `z.object({...})` as required even when every
 * child has a `.default(...)`, so parsing `{}` against the top-level schema
 * would fail. We hand-build the defaults once and use the schema only to
 * validate incoming patches.
 */
export function defaultSettings(): Settings {
  return {
    general: {
      dataDir: null,
      language: 'it',
      theme: 'dark',
    },
    processing: {
      overrides: {},
      pythonExecutable: null,
    },
    vlm: {
      modelsDir: null,
      preferredModel: null,
      estimatedVramGb: 8,
    },
    report: {
      logoPath: null,
      companyName: '',
      defaultOperatorName: '',
      footerText: '',
    },
  };
}

// ---------------------------------------------------------------------------
// Filesystem helpers
// ---------------------------------------------------------------------------

function settingsPath(): string {
  return path.join(app.getPath('userData'), 'settings.json');
}

/** Deep-merge `patch` into `base`. Plain objects recurse; arrays + scalars replace. */
function deepMerge<T>(base: T, patch: unknown): T {
  if (
    base === null
    || typeof base !== 'object'
    || Array.isArray(base)
    || patch === null
    || typeof patch !== 'object'
    || Array.isArray(patch)
  ) {
    return (patch ?? base) as T;
  }
  const result: Record<string, unknown> = { ...(base as Record<string, unknown>) };
  for (const [key, value] of Object.entries(patch as Record<string, unknown>)) {
    const current = (base as Record<string, unknown>)[key];
    if (
      current !== null
      && typeof current === 'object'
      && !Array.isArray(current)
      && value !== null
      && typeof value === 'object'
      && !Array.isArray(value)
    ) {
      result[key] = deepMerge(current, value);
    } else {
      result[key] = value;
    }
  }
  return result as T;
}

/**
 * Load persisted settings. Returns defaults if:
 *   - file does not exist (first launch)
 *   - file is unreadable (permissions, disk error)
 *   - JSON is malformed or fails schema validation
 *
 * The fallback path is silent by design — starting with defaults beats
 * blocking the app launch on a corrupted file.
 */
export function loadSettings(): Settings {
  const filePath = settingsPath();
  if (!fs.existsSync(filePath)) {
    return defaultSettings();
  }
  try {
    const raw = fs.readFileSync(filePath, 'utf-8');
    const parsed = JSON.parse(raw);
    // Merge onto defaults before validating so missing sections don't fail.
    const merged = deepMerge(defaultSettings(), parsed);
    return SettingsSchema.parse(merged);
  } catch {
    return defaultSettings();
  }
}

/**
 * Save a partial patch (deep-merged into current settings) atomically.
 *
 * Atomicity: write to `<path>.tmp` then rename — rename is atomic on NTFS
 * via `fs.renameSync` under normal conditions, so a crash cannot leave a
 * half-written file at the canonical path.
 */
export function saveSettings(patch: Partial<Settings> | Record<string, unknown>): Settings {
  const current = loadSettings();
  const merged = deepMerge(current, patch);
  const validated = SettingsSchema.parse(merged);

  const filePath = settingsPath();
  const tmpPath = `${filePath}.tmp`;
  const dir = path.dirname(filePath);

  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }

  fs.writeFileSync(tmpPath, JSON.stringify(validated, null, 2), 'utf-8');
  fs.renameSync(tmpPath, filePath);

  return validated;
}

/** Reset settings to defaults and persist. */
export function resetSettings(): Settings {
  const defaults = defaultSettings();
  const filePath = settingsPath();
  const tmpPath = `${filePath}.tmp`;
  const dir = path.dirname(filePath);
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
  fs.writeFileSync(tmpPath, JSON.stringify(defaults, null, 2), 'utf-8');
  fs.renameSync(tmpPath, filePath);
  return defaults;
}
