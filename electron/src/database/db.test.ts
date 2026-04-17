import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import Database from 'better-sqlite3';
import fs from 'fs';
import path from 'path';
import os from 'os';
import { initDatabase, DatabaseService } from './db';

let dbPath: string;
let db: Database.Database;
let service: DatabaseService;

beforeEach(() => {
  dbPath = path.join(os.tmpdir(), `heap-analyzer-test-${Date.now()}.db`);
  db = initDatabase(dbPath);
  service = new DatabaseService(db);
});

afterEach(() => {
  // Must close connection before deleting on Windows (file lock)
  db.close();
  if (fs.existsSync(dbPath)) fs.unlinkSync(dbPath);
});

describe('DatabaseService — Projects', () => {
  it('creates and lists projects', () => {
    const created = service.createProject({
      name: 'Test Project',
      location: 'Milano',
      crs: 'EPSG:32632',
      notes: null,
      material_categories: '["rottame"]',
    });

    expect(created.id).toBeTypeOf('number');
    expect(created.name).toBe('Test Project');
    expect(created.crs).toBe('EPSG:32632');

    const list = service.listProjects();
    expect(list).toHaveLength(1);
    expect(list[0].id).toBe(created.id);
  });

  it('updates a project', () => {
    const project = service.createProject({
      name: 'Old Name',
      location: null,
      crs: 'EPSG:32632',
      notes: null,
      material_categories: null,
    });

    const updated = service.updateProject(project.id, { name: 'New Name', notes: 'updated' });
    expect(updated?.name).toBe('New Name');
    expect(updated?.notes).toBe('updated');
  });

  it('deletes a project', () => {
    const project = service.createProject({
      name: 'To Delete',
      location: null,
      crs: 'EPSG:32632',
      notes: null,
      material_categories: null,
    });

    service.deleteProject(project.id);
    expect(service.listProjects()).toHaveLength(0);
  });
});

describe('DatabaseService — Surveys (FK cascade)', () => {
  it('creates a survey linked to a project', () => {
    const project = service.createProject({
      name: 'P',
      location: null,
      crs: 'EPSG:32632',
      notes: null,
      material_categories: null,
    });

    const survey = service.createSurvey({
      project_id: project.id,
      survey_date: '2026-04-01',
      operator: 'Mario',
      las_path: '/data/test.las',
      tiff_path: '/data/test.tif',
      processing_params: null,
      processing_status: 'pending',
      dsm_path: null,
      dtm_path: null,
      ndsm_path: null,
      label_map_path: null,
      tiles_path: null,
      ndsm_heatmap_path: null,
      base_elevation: null,
      potree_path: null,
    });

    expect(survey.project_id).toBe(project.id);
    expect(survey.processing_status).toBe('pending');
    expect(service.listSurveys(project.id)).toHaveLength(1);
  });

  it('cascades delete: removing project removes surveys', () => {
    const project = service.createProject({
      name: 'P',
      location: null,
      crs: 'EPSG:32632',
      notes: null,
      material_categories: null,
    });

    const survey = service.createSurvey({
      project_id: project.id,
      survey_date: '2026-04-01',
      operator: null,
      las_path: '/x.las',
      tiff_path: '/x.tif',
      processing_params: null,
      processing_status: 'pending',
      dsm_path: null,
      dtm_path: null,
      ndsm_path: null,
      label_map_path: null,
      tiles_path: null,
      ndsm_heatmap_path: null,
      base_elevation: null,
      potree_path: null,
    });

    service.deleteProject(project.id);
    expect(service.getSurvey(survey.id)).toBeNull();
  });
});

describe('DatabaseService — Heaps (FK cascade)', () => {
  it('bulk creates heaps and cascades on survey delete', () => {
    const project = service.createProject({
      name: 'P',
      location: null,
      crs: 'EPSG:32632',
      notes: null,
      material_categories: null,
    });

    const survey = service.createSurvey({
      project_id: project.id,
      survey_date: '2026-04-01',
      operator: null,
      las_path: '/x.las',
      tiff_path: '/x.tif',
      processing_params: null,
      processing_status: 'completed',
      dsm_path: null,
      dtm_path: null,
      ndsm_path: null,
      label_map_path: null,
      tiles_path: null,
      ndsm_heatmap_path: null,
      base_elevation: null,
      potree_path: null,
    });

    const heapData = {
      survey_id: survey.id,
      label: 'heap-1',
      polygon: '{"type":"Polygon","coordinates":[]}',
      volume: 1178.1,
      planimetric_area: 706.8,
      surface_area: 760.0,
      max_height: 5.0,
      mean_height: 2.5,
      base_elevation: 100.0,
      centroid_e: 500050,
      centroid_n: 5000050,
      bbox_min_e: 500035,
      bbox_min_n: 5000035,
      bbox_max_e: 500065,
      bbox_max_n: 5000065,
      material_category: null,
      material_confidence: null,
      is_manually_confirmed: 0,
      is_excluded: 0,
    };

    const heaps = service.bulkCreateHeaps([heapData, { ...heapData, label: 'heap-2' }]);
    expect(heaps).toHaveLength(2);
    expect(service.listHeaps(survey.id)).toHaveLength(2);

    // Delete project → cascade to surveys → cascade to heaps
    service.deleteProject(project.id);
    expect(service.listHeaps(survey.id)).toHaveLength(0);
  });
});

describe('DatabaseService — Schema compliance', () => {
  it('project has all SPEC columns with correct defaults', () => {
    const p = service.createProject({
      name: 'Schema Test',
      location: null,
      crs: 'EPSG:32632',
      notes: null,
      material_categories: null,
    });

    expect(p).toHaveProperty('id');
    expect(p).toHaveProperty('name');
    expect(p).toHaveProperty('location');
    expect(p).toHaveProperty('crs');
    expect(p).toHaveProperty('notes');
    expect(p).toHaveProperty('material_categories');
    expect(p).toHaveProperty('created_at');
    expect(p).toHaveProperty('updated_at');
    expect(p.crs).toBe('EPSG:32632');
  });

  it('heap has all SPEC columns', () => {
    const project = service.createProject({ name: 'P', location: null, crs: 'EPSG:32632', notes: null, material_categories: null });
    const survey = service.createSurvey({ project_id: project.id, survey_date: '2026-04-01', operator: null, las_path: '/x.las', tiff_path: '/x.tif', processing_params: null, processing_status: 'pending', dsm_path: null, dtm_path: null, ndsm_path: null, label_map_path: null, tiles_path: null, ndsm_heatmap_path: null, base_elevation: null, potree_path: null });
    const heap = service.createHeap({ survey_id: survey.id, label: 'h1', polygon: '{}', volume: 100, planimetric_area: 50, surface_area: 55, max_height: 3, mean_height: 1.5, base_elevation: 100, centroid_e: 500000, centroid_n: 5000000, bbox_min_e: 499990, bbox_min_n: 4999990, bbox_max_e: 500010, bbox_max_n: 5000010, material_category: null, material_confidence: null, is_manually_confirmed: 0, is_excluded: 0 });

    const requiredCols = ['id','survey_id','label','polygon','volume','planimetric_area','surface_area','max_height','mean_height','base_elevation','centroid_e','centroid_n','bbox_min_e','bbox_min_n','bbox_max_e','bbox_max_n','material_category','material_confidence','is_manually_confirmed','is_excluded','created_at','updated_at'];
    for (const col of requiredCols) {
      expect(heap).toHaveProperty(col);
    }
  });
});
