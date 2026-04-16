import type { Polygon } from "geojson";

export type Crs = "EPSG:32632" | "EPSG:32633";

export interface Project {
  id: number;
  name: string;
  location: string | null;
  crs: Crs;
  notes: string | null;
  materialCategories: string[];
  createdAt: string;
  updatedAt: string;
}

export type ProcessingStatus = "pending" | "processing" | "completed" | "error";

export interface Survey {
  id: number;
  projectId: number;
  surveyDate: string;
  operator: string | null;
  lasPath: string;
  tiffPath: string;
  processingParams: Record<string, unknown> | null;
  processingStatus: ProcessingStatus;
  dsmPath: string | null;
  dtmPath: string | null;
  ndsmPath: string | null;
  labelMapPath: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface Heap {
  id: number;
  surveyId: number;
  label: string | null;
  polygon: Polygon;
  volume: number;
  planimetricArea: number;
  surfaceArea: number;
  maxHeight: number;
  meanHeight: number;
  baseElevation: number;
  centroidE: number;
  centroidN: number;
  bboxMinE: number;
  bboxMinN: number;
  bboxMaxE: number;
  bboxMaxN: number;
  materialCategory: string | null;
  materialConfidence: number | null;
  isManuallyConfirmed: boolean;
  isExcluded: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface ProcessingProgress {
  phase: string;
  percent: number;
  message: string;
}

export interface ProcessingState {
  isRunning: boolean;
  surveyId: number | null;
  progress: ProcessingProgress | null;
  startTime: number | null;
  warnings: string[];
}
