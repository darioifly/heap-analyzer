import { describe, it, expect, afterEach } from 'vitest';
import Database from 'better-sqlite3';
import fs from 'fs';
import path from 'path';
import os from 'os';
import { initDatabase } from './db';

// Helper: list columns present in `surveys` table.
function columnsOf(db: Database.Database, table: string): string[] {
  return (db.prepare(`PRAGMA table_info(${table})`).all() as { name: string }[]).map(
    (c) => c.name,
  );
}

const tempFiles: string[] = [];

afterEach(() => {
  for (const f of tempFiles) {
    try {
      fs.unlinkSync(f);
    } catch {
      /* ignore */
    }
  }
  tempFiles.length = 0;
});

function freshDbPath(): string {
  const p = path.join(os.tmpdir(), `heap-migrate-${Date.now()}-${Math.random()}.db`);
  tempFiles.push(p);
  return p;
}

describe('schema migration — F2.S10 DJI columns', () => {
  it('fresh DB includes surveys.source_type and surveys.dji_folder_path', () => {
    const dbPath = freshDbPath();
    const db = initDatabase(dbPath);
    try {
      const cols = columnsOf(db, 'surveys');
      expect(cols).toContain('source_type');
      expect(cols).toContain('dji_folder_path');
    } finally {
      db.close();
    }
  });

  it('migrates an older DB missing the DJI columns without losing data', () => {
    const dbPath = freshDbPath();

    // Manually build a legacy surveys table missing the new columns.
    const legacy = new Database(dbPath);
    legacy.exec(`
      CREATE TABLE projects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        location TEXT,
        crs TEXT,
        notes TEXT,
        material_categories TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
      );
      CREATE TABLE surveys (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id INTEGER NOT NULL,
        survey_date DATE NOT NULL,
        operator TEXT,
        las_path TEXT NOT NULL,
        tiff_path TEXT NOT NULL,
        processing_params TEXT,
        processing_status TEXT DEFAULT 'pending',
        dsm_path TEXT,
        dtm_path TEXT,
        ndsm_path TEXT,
        label_map_path TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
      );
    `);
    // Seed one project + one survey (pre-migration).
    legacy.prepare(`INSERT INTO projects (name, crs) VALUES ('Legacy', 'EPSG:32632')`).run();
    legacy
      .prepare(
        `INSERT INTO surveys (project_id, survey_date, las_path, tiff_path)
         VALUES (1, '2025-06-01', '/old.las', '/old.tif')`,
      )
      .run();
    legacy.close();

    // Re-open through initDatabase — migration should add the missing columns
    // without touching existing rows.
    const migrated = initDatabase(dbPath);
    try {
      const cols = columnsOf(migrated, 'surveys');
      expect(cols).toContain('source_type');
      expect(cols).toContain('dji_folder_path');

      const row = migrated
        .prepare(`SELECT * FROM surveys WHERE id = 1`)
        .get() as Record<string, unknown>;
      expect(row.las_path).toBe('/old.las');
      expect(row.tiff_path).toBe('/old.tif');
      // Default 'manual' applied to the pre-existing row by ALTER TABLE ... DEFAULT.
      expect(row.source_type).toBe('manual');
      expect(row.dji_folder_path).toBeNull();
    } finally {
      migrated.close();
    }
  });

  it('re-running migration on already-migrated DB is a no-op', () => {
    const dbPath = freshDbPath();
    const db1 = initDatabase(dbPath);
    db1.close();

    // Open again — initDatabase calls migrateSchema unconditionally; verify no crash.
    const db2 = initDatabase(dbPath);
    try {
      const cols = columnsOf(db2, 'surveys');
      const sourceCount = cols.filter((c) => c === 'source_type').length;
      expect(sourceCount).toBe(1);
    } finally {
      db2.close();
    }
  });
});
