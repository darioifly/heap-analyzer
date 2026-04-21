import express, { Request, Response } from 'express';
import path from 'path';
import fs from 'fs';
import http from 'http';
import type { DatabaseService } from '../database/db';

/**
 * Express-based tile server for serving map tiles, metadata, and heatmaps
 * from the Electron main process.
 */
export class TileServer {
  private readonly app: express.Express;
  private readonly dbService: DatabaseService;
  private readonly port: number;
  private server: http.Server | null = null;

  constructor(dbService: DatabaseService, port: number = 3001) {
    this.dbService = dbService;
    this.port = port;
    this.app = express();
    this.setupMiddleware();
    this.setupRoutes();
  }

  /** Start the tile server and return its base URL. */
  async start(): Promise<string> {
    return new Promise<string>((resolve, reject) => {
      this.server = this.app.listen(this.port, '127.0.0.1', () => {
        resolve(this.getBaseUrl());
      });
      this.server.on('error', reject);
    });
  }

  /** Stop the tile server gracefully. */
  async stop(): Promise<void> {
    return new Promise<void>((resolve, reject) => {
      if (!this.server) {
        resolve();
        return;
      }
      this.server.close((err) => {
        this.server = null;
        if (err) {
          reject(err);
        } else {
          resolve();
        }
      });
    });
  }

  /** Get the base URL of the running server. */
  getBaseUrl(): string {
    return `http://127.0.0.1:${this.port}`;
  }

  // ---------------------------------------------------------------------------
  // Middleware
  // ---------------------------------------------------------------------------

  private setupMiddleware(): void {
    this.app.use((req: Request, res: Response, next) => {
      res.setHeader('Access-Control-Allow-Origin', '*');
      // potree-core issues Range-requests for octree/hierarchy chunks with
      // a custom Content-Type; that promotes the request to a CORS-
      // "non-simple" fetch, which needs a preflight OPTIONS to succeed
      // before the GET is sent. Without these two headers (and an OPTIONS
      // short-circuit below) the browser blocks the GET with
      //   "Response to preflight request doesn't pass access control check"
      // and the 3D viewer never loads hierarchy.bin.
      res.setHeader('Access-Control-Allow-Methods', 'GET, HEAD, OPTIONS');
      res.setHeader(
        'Access-Control-Allow-Headers',
        'Content-Type, Range, Accept, Origin',
      );
      res.setHeader('Access-Control-Expose-Headers', 'Content-Length, Content-Range, Accept-Ranges');
      // no-cache forces the browser/OL to revalidate before serving from
      // cache. Without this, regenerating tile pyramids is invisible to
      // the operator because the 24h max-age tiles remain cached.
      res.setHeader('Cache-Control', 'no-cache');
      if (req.method === 'OPTIONS') {
        res.status(204).end();
        return;
      }
      next();
    });
  }

  // ---------------------------------------------------------------------------
  // Routes
  // ---------------------------------------------------------------------------

  private setupRoutes(): void {
    // Serve individual map tiles
    this.app.get(
      '/tiles/:surveyId/:z/:x/:y.png',
      (req: Request, res: Response): void => {
        const surveyId = parseInt(req.params.surveyId as string, 10);
        if (isNaN(surveyId)) {
          res.status(400).json({ error: 'Invalid survey ID' });
          return;
        }

        const survey = this.dbService.getSurvey(surveyId);
        if (!survey || !survey.tiles_path) {
          res.status(404).json({ error: 'Survey or tiles not found' });
          return;
        }

        const z = req.params.z as string;
        const x = req.params.x as string;
        const y = req.params.y as string;
        const tilePath = path.join(survey.tiles_path, z, x, `${y}.png`);

        if (!fs.existsSync(tilePath)) {
          res.status(404).json({ error: 'Tile not found' });
          return;
        }

        res.sendFile(tilePath);
      },
    );

    // Serve tile metadata
    this.app.get(
      '/tiles/:surveyId/metadata.json',
      (req: Request, res: Response): void => {
        const surveyId = parseInt(req.params.surveyId as string, 10);
        if (isNaN(surveyId)) {
          res.status(400).json({ error: 'Invalid survey ID' });
          return;
        }

        const survey = this.dbService.getSurvey(surveyId);
        if (!survey || !survey.tiles_path) {
          res.status(404).json({ error: 'Survey or tiles not found' });
          return;
        }

        const metadataPath = path.join(survey.tiles_path, 'metadata.json');

        if (!fs.existsSync(metadataPath)) {
          res.status(404).json({ error: 'Metadata not found' });
          return;
        }

        res.sendFile(metadataPath);
      },
    );

    // Serve Potree files: /potree/:surveyId/*
    this.app.use(
      '/potree/:surveyId',
      (req: Request, res: Response, next) => {
        const surveyId = parseInt(req.params.surveyId as string, 10);
        if (isNaN(surveyId)) {
          res.status(400).json({ error: 'Invalid survey ID' });
          return;
        }

        const survey = this.dbService.getSurvey(surveyId);
        if (!survey || !survey.potree_path) {
          res.status(404).json({ error: 'Potree data not available' });
          return;
        }

        express.static(survey.potree_path)(req, res, next);
      },
    );

    // Serve nDSM heatmap image
    this.app.get(
      '/heatmap/:surveyId.png',
      (req: Request, res: Response): void => {
        const surveyId = parseInt(req.params.surveyId as string, 10);
        if (isNaN(surveyId)) {
          res.status(400).json({ error: 'Invalid survey ID' });
          return;
        }

        const survey = this.dbService.getSurvey(surveyId);
        if (!survey || !survey.ndsm_heatmap_path) {
          res.status(404).json({ error: 'Survey or heatmap not found' });
          return;
        }

        if (!fs.existsSync(survey.ndsm_heatmap_path)) {
          res.status(404).json({ error: 'Heatmap file not found' });
          return;
        }

        res.sendFile(survey.ndsm_heatmap_path);
      },
    );
  }
}
