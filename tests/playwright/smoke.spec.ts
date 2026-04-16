import { test, expect } from '@playwright/test';
import { captureScreenshot } from './helpers';
import path from 'path';
import fs from 'fs';

/**
 * Smoke test: verifies the app loads and shows "Heap Analyzer".
 *
 * Note: In CI/test environments without a running Electron instance,
 * this test loads the built frontend HTML directly via file:// URL.
 * For full Electron integration, use electron-playwright-helpers in F0.S08+.
 */
test.describe('Smoke Test', () => {
  test('frontend build shows Heap Analyzer title', async ({ page }) => {
    // Try to load from built frontend, fall back to dev server
    const builtIndex = path.join(__dirname, '../../dist/frontend/index.html');
    const devUrl = 'http://localhost:5173';

    if (fs.existsSync(builtIndex)) {
      await page.goto(`file://${builtIndex.replace(/\\/g, '/')}`);
    } else {
      // Dev server mode — requires Vite to be running
      try {
        await page.goto(devUrl, { timeout: 5000 });
      } catch {
        test.skip(true, 'Dev server not running and no built frontend found — skipping visual test');
        return;
      }
    }

    // Verify "Heap Analyzer" text is present
    await expect(page.locator('h1')).toContainText('Heap Analyzer');

    // Capture screenshot
    const screenshotPath = await captureScreenshot(page, 'smoke-test');
    const stats = fs.statSync(screenshotPath);
    expect(stats.size).toBeGreaterThan(0);
    console.log(`Screenshot saved: ${screenshotPath}`);
  });
});
