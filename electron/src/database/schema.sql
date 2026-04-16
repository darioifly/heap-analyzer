PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS projects (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  location TEXT,
  crs TEXT DEFAULT 'EPSG:32632',
  notes TEXT,
  material_categories TEXT, -- JSON array di stringhe
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS surveys (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  survey_date DATE NOT NULL,
  operator TEXT,
  las_path TEXT NOT NULL,
  tiff_path TEXT NOT NULL,
  processing_params TEXT, -- JSON ProcessingConfig
  processing_status TEXT DEFAULT 'pending', -- pending|processing|completed|error
  dsm_path TEXT,
  dtm_path TEXT,
  ndsm_path TEXT,
  label_map_path TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS heaps (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  survey_id INTEGER NOT NULL REFERENCES surveys(id) ON DELETE CASCADE,
  label TEXT,
  polygon TEXT NOT NULL, -- GeoJSON geometry
  volume REAL,
  planimetric_area REAL,
  surface_area REAL,
  max_height REAL,
  mean_height REAL,
  base_elevation REAL,
  centroid_e REAL,
  centroid_n REAL,
  bbox_min_e REAL,
  bbox_min_n REAL,
  bbox_max_e REAL,
  bbox_max_n REAL,
  material_category TEXT,
  material_confidence REAL,
  is_manually_confirmed INTEGER DEFAULT 0,
  is_excluded INTEGER DEFAULT 0,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS comparisons (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  survey_a_id INTEGER NOT NULL REFERENCES surveys(id),
  survey_b_id INTEGER NOT NULL REFERENCES surveys(id),
  results TEXT, -- JSON matching results
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Triggers for updated_at
CREATE TRIGGER IF NOT EXISTS projects_updated_at
  AFTER UPDATE ON projects
BEGIN
  UPDATE projects SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS surveys_updated_at
  AFTER UPDATE ON surveys
BEGIN
  UPDATE surveys SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS heaps_updated_at
  AFTER UPDATE ON heaps
BEGIN
  UPDATE heaps SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;
