import { Page } from '@playwright/test';
import path from 'path';
import fs from 'fs';

const SCREENSHOT_DIR = path.join(__dirname, 'screenshots');

/** Capture a screenshot and save it to the screenshots directory. */
export async function captureScreenshot(page: Page, name: string): Promise<string> {
  if (!fs.existsSync(SCREENSHOT_DIR)) {
    fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
  }
  const filePath = path.join(SCREENSHOT_DIR, `${name}.png`);
  await page.screenshot({ path: filePath, fullPage: true });
  return filePath;
}

/** Wait until the OpenLayers map canvas is visible (placeholder). */
export async function waitForMapReady(page: Page): Promise<void> {
  // Will be implemented in F2.S04 when OpenLayers is added
  await page.waitForTimeout(500);
}

/** Wait until the Potree 3D viewer is ready (placeholder). */
export async function waitForThreeReady(page: Page): Promise<void> {
  // Will be implemented in F3.S01 when Potree is added
  await page.waitForTimeout(500);
}
