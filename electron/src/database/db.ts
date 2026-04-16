import Database from 'better-sqlite3';
import fs from 'fs';
import path from 'path';

// ---------------------------------------------------------------------------
// Types matching SPEC.md [SCHEMA]
// ---------------------------------------------------------------------------

export interface Project {
  id: number;
  name: string;
  location: string | null;
  crs: string;
  notes: string | null;
  material_categories: string | null; // JSON array
  created_at: string;
  updated_at: string;
}

export interface Survey {
  id: number;
  project_id: number;
  survey_date: string;
  operator: string | null;
  las_path: string;
  tiff_path: string;
  processing_params: string | null; // JSON ProcessingConfig
  processing_status: 'pending' | 'processing' | 'completed' | 'error';
  dsm_path: string | null;
  dtm_path: string | null;
  ndsm_path: string | null;
  label_map_path: string | null;
  tiles_path: string | null;
  ndsm_heatmap_path: string | null;
  created_at: string;
  updated_at: string;
}

export interface Heap {
  id: number;
  survey_id: number;
  label: string | null;
  polygon: string; // GeoJSON geometry
  volume: number | null;
  planimetric_area: number | null;
  surface_area: number | null;
  max_height: number | null;
  mean_height: number | null;
  base_elevation: number | null;
  centroid_e: number | null;
  centroid_n: number | null;
  bbox_min_e: number | null;
  bbox_min_n: number | null;
  bbox_max_e: number | null;
  bbox_max_n: number | null;
  material_category: string | null;
  material_confidence: number | null;
  is_manually_confirmed: number;
  is_excluded: number;
  created_at: string;
  updated_at: string;
}

export interface Comparison {
  id: number;
  survey_a_id: number;
  survey_b_id: number;
  results: string | null; // JSON
  created_at: string;
}

// ---------------------------------------------------------------------------
// Database service
// ---------------------------------------------------------------------------

export function initDatabase(dbPath: string): Database.Database {
  const db = new Database(dbPath);
  const schemaPath = path.join(__dirname, 'schema.sql');
  const schema = fs.readFileSync(schemaPath, 'utf8');
  db.exec(schema);
  migrateSchema(db);
  return db;
}

/** Add columns that may be missing from older databases. */
function migrateSchema(db: Database.Database): void {
  const cols = db.prepare('PRAGMA table_info(surveys)').all() as { name: string }[];
  const colNames = new Set(cols.map((c) => c.name));
  if (!colNames.has('tiles_path')) {
    db.exec('ALTER TABLE surveys ADD COLUMN tiles_path TEXT');
  }
  if (!colNames.has('ndsm_heatmap_path')) {
    db.exec('ALTER TABLE surveys ADD COLUMN ndsm_heatmap_path TEXT');
  }
}

export class DatabaseService {
  private readonly db: Database.Database;

  constructor(db: Database.Database) {
    this.db = db;
  }

  // -------------------------------------------------------------------------
  // Projects
  // -------------------------------------------------------------------------

  listProjects(): Project[] {
    return this.db.prepare('SELECT * FROM projects ORDER BY created_at DESC').all() as Project[];
  }

  createProject(data: Omit<Project, 'id' | 'created_at' | 'updated_at'>): Project {
    const stmt = this.db.prepare(`
      INSERT INTO projects (name, location, crs, notes, material_categories)
      VALUES (@name, @location, @crs, @notes, @material_categories)
    `);
    const info = stmt.run(data);
    return this.db
      .prepare('SELECT * FROM projects WHERE id = ?')
      .get(info.lastInsertRowid) as Project;
  }

  updateProject(id: number, data: Partial<Omit<Project, 'id' | 'created_at' | 'updated_at'>>): Project | null {
    const fields = Object.keys(data)
      .map((k) => `${k} = @${k}`)
      .join(', ');
    if (!fields) return this.getProject(id);
    this.db.prepare(`UPDATE projects SET ${fields} WHERE id = @id`).run({ ...data, id });
    return this.getProject(id);
  }

  getProject(id: number): Project | null {
    return (this.db.prepare('SELECT * FROM projects WHERE id = ?').get(id) as Project) ?? null;
  }

  deleteProject(id: number): void {
    this.db.prepare('DELETE FROM projects WHERE id = ?').run(id);
  }

  // -------------------------------------------------------------------------
  // Surveys
  // -------------------------------------------------------------------------

  listSurveys(projectId: number): Survey[] {
    return this.db
      .prepare('SELECT * FROM surveys WHERE project_id = ? ORDER BY survey_date DESC')
      .all(projectId) as Survey[];
  }

  createSurvey(data: Omit<Survey, 'id' | 'created_at' | 'updated_at'>): Survey {
    const stmt = this.db.prepare(`
      INSERT INTO surveys
        (project_id, survey_date, operator, las_path, tiff_path,
         processing_params, processing_status,
         dsm_path, dtm_path, ndsm_path, label_map_path,
         tiles_path, ndsm_heatmap_path)
      VALUES
        (@project_id, @survey_date, @operator, @las_path, @tiff_path,
         @processing_params, @processing_status,
         @dsm_path, @dtm_path, @ndsm_path, @label_map_path,
         @tiles_path, @ndsm_heatmap_path)
    `);
    const info = stmt.run(data);
    return this.db
      .prepare('SELECT * FROM surveys WHERE id = ?')
      .get(info.lastInsertRowid) as Survey;
  }

  updateSurvey(id: number, data: Partial<Omit<Survey, 'id' | 'created_at' | 'updated_at'>>): Survey | null {
    const fields = Object.keys(data)
      .map((k) => `${k} = @${k}`)
      .join(', ');
    if (!fields) return this.getSurvey(id);
    this.db.prepare(`UPDATE surveys SET ${fields} WHERE id = @id`).run({ ...data, id });
    return this.getSurvey(id);
  }

  getSurvey(id: number): Survey | null {
    return (this.db.prepare('SELECT * FROM surveys WHERE id = ?').get(id) as Survey) ?? null;
  }

  deleteSurvey(id: number): void {
    this.db.prepare('DELETE FROM surveys WHERE id = ?').run(id);
  }

  // -------------------------------------------------------------------------
  // Heaps
  // -------------------------------------------------------------------------

  listHeaps(surveyId: number): Heap[] {
    return this.db
      .prepare('SELECT * FROM heaps WHERE survey_id = ? ORDER BY id')
      .all(surveyId) as Heap[];
  }

  createHeap(data: Omit<Heap, 'id' | 'created_at' | 'updated_at'>): Heap {
    const stmt = this.db.prepare(`
      INSERT INTO heaps
        (survey_id, label, polygon, volume, planimetric_area, surface_area,
         max_height, mean_height, base_elevation,
         centroid_e, centroid_n,
         bbox_min_e, bbox_min_n, bbox_max_e, bbox_max_n,
         material_category, material_confidence,
         is_manually_confirmed, is_excluded)
      VALUES
        (@survey_id, @label, @polygon, @volume, @planimetric_area, @surface_area,
         @max_height, @mean_height, @base_elevation,
         @centroid_e, @centroid_n,
         @bbox_min_e, @bbox_min_n, @bbox_max_e, @bbox_max_n,
         @material_category, @material_confidence,
         @is_manually_confirmed, @is_excluded)
    `);
    const info = stmt.run(data);
    return this.db.prepare('SELECT * FROM heaps WHERE id = ?').get(info.lastInsertRowid) as Heap;
  }

  updateHeap(id: number, data: Partial<Omit<Heap, 'id' | 'created_at' | 'updated_at'>>): Heap | null {
    const fields = Object.keys(data)
      .map((k) => `${k} = @${k}`)
      .join(', ');
    if (!fields) return this.getHeap(id);
    this.db.prepare(`UPDATE heaps SET ${fields} WHERE id = @id`).run({ ...data, id });
    return this.getHeap(id);
  }

  getHeap(id: number): Heap | null {
    return (this.db.prepare('SELECT * FROM heaps WHERE id = ?').get(id) as Heap) ?? null;
  }

  bulkCreateHeaps(heaps: Omit<Heap, 'id' | 'created_at' | 'updated_at'>[]): Heap[] {
    const insert = this.db.prepare(`
      INSERT INTO heaps
        (survey_id, label, polygon, volume, planimetric_area, surface_area,
         max_height, mean_height, base_elevation,
         centroid_e, centroid_n,
         bbox_min_e, bbox_min_n, bbox_max_e, bbox_max_n,
         material_category, material_confidence,
         is_manually_confirmed, is_excluded)
      VALUES
        (@survey_id, @label, @polygon, @volume, @planimetric_area, @surface_area,
         @max_height, @mean_height, @base_elevation,
         @centroid_e, @centroid_n,
         @bbox_min_e, @bbox_min_n, @bbox_max_e, @bbox_max_n,
         @material_category, @material_confidence,
         @is_manually_confirmed, @is_excluded)
    `);
    const insertMany = this.db.transaction((items: typeof heaps) => {
      return items.map((item) => {
        const info = insert.run(item);
        return this.db.prepare('SELECT * FROM heaps WHERE id = ?').get(info.lastInsertRowid) as Heap;
      });
    });
    return insertMany(heaps);
  }

  // -------------------------------------------------------------------------
  // Comparisons
  // -------------------------------------------------------------------------

  createComparison(surveyAId: number, surveyBId: number, results: string): Comparison {
    const stmt = this.db.prepare(`
      INSERT INTO comparisons (survey_a_id, survey_b_id, results)
      VALUES (?, ?, ?)
    `);
    const info = stmt.run(surveyAId, surveyBId, results);
    return this.db
      .prepare('SELECT * FROM comparisons WHERE id = ?')
      .get(info.lastInsertRowid) as Comparison;
  }

  listComparisons(surveyId: number): Comparison[] {
    return this.db
      .prepare(
        'SELECT * FROM comparisons WHERE survey_a_id = ? OR survey_b_id = ? ORDER BY created_at DESC',
      )
      .all(surveyId, surveyId) as Comparison[];
  }
}
