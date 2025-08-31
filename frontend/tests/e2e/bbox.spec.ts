// tests/e2e/bbox.spec.ts
import { test, expect } from '@playwright/test';
import 'dotenv/config';

const MODE = (process.env.E2E_MAP || 'both').trim().toLowerCase();
const runMaplibre = MODE === 'both' || MODE === 'maplibre';
const runMapbox   = MODE === 'both' || MODE === 'mapbox';

async function runBBoxTest(page: any, opts: { name: string; url: string; isMapbox: boolean }) {
  const { name, url, isMapbox } = opts;

  await page.goto(url);

  // Wait for dev-exposed stores
  await page.waitForFunction(() =>
    (window as any).useUIStore && (window as any).useWaypointStore
  );

  // Turn BBox tool on
  await page.evaluate(() => (window as any).useUIStore.getState().setDrawBBoxEnabled(true));

  // Choose a click target:
  // - On Mapbox, prefer our overlay (data-testid="bbox-click-overlay") if present
  // - Otherwise, fall back to the map canvas
  const overlay = page.locator('[data-testid="bbox-click-overlay"]');
  const mapCanvas = isMapbox
    ? page.locator('canvas.mapboxgl-canvas').first()
    : page.locator('canvas').first();

  let target = overlay;
  if (isMapbox) {
    // If overlay isn’t visible (e.g. not added), use canvas
    try {
      await expect(overlay).toBeVisible({ timeout: 1000 });
    } catch {
      target = mapCanvas;
    }
  } else {
    await expect(mapCanvas).toBeVisible();
    target = mapCanvas;
  }

  const box = await target.boundingBox();
  if (!box) throw new Error(`[${name}] no bounding box for target element`);
  const A = { x: box.x + box.width * 0.35, y: box.y + box.height * 0.45 };
  const B = { x: box.x + box.width * 0.55, y: box.y + box.height * 0.60 };

  // Two-click rectangle (Deck editable layer handler is wired to onClick)
  // Use page.mouse so we always use absolute coords (works for overlay or canvas)
  await page.mouse.click(A.x, A.y);
  await page.mouse.click(B.x, B.y);

  // Assert lastBbox exists & has sane bounds
  const twoClickBox = await page.evaluate(() => (window as any).useUIStore.getState().lastBbox);
  expect(twoClickBox, `[${name}] two-click lastBbox`).toBeTruthy();
  expect(twoClickBox.west).toBeLessThan(twoClickBox.east);
  expect(twoClickBox.south).toBeLessThan(twoClickBox.north);

  // SHIFT-drag live red box is only implemented on MapLibre
  if (!isMapbox) {
    const C = { x: box.x + box.width * 0.40, y: box.y + box.height * 0.40 };
    const D = { x: box.x + box.width * 0.50, y: box.y + box.height * 0.50 };
    await page.keyboard.down('Shift');
    await page.mouse.move(C.x, C.y);
    await page.mouse.down();
    await page.mouse.move(D.x, D.y);
    await page.mouse.up();
    await page.keyboard.up('Shift');

    const dragBox = await page.evaluate(() => (window as any).useUIStore.getState().lastBbox);
    expect(dragBox, `[${name}] shift-drag lastBbox`).toBeTruthy();
    expect(dragBox.west).toBeLessThan(dragBox.east);
    expect(dragBox.south).toBeLessThan(dragBox.north);
  }
}

if (runMaplibre) {
  test.describe('BBox tools (maplibre)', () => {
    test('two-click + drag-to-draw update lastBbox', async ({ page }) => {
      await runBBoxTest(page, { name: 'maplibre', url: '/map/maplibre', isMapbox: false });
    });
  });
}

if (runMapbox) {
  test.describe('BBox tools (mapbox)', () => {
    test('two-click + drag-to-draw update lastBbox', async ({ page }) => {
      await runBBoxTest(page, { name: 'mapbox', url: '/map/mapbox', isMapbox: true });
    });
  });
}
