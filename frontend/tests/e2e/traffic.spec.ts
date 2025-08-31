import { test, expect } from '@playwright/test';
import 'dotenv/config';

const MODE = (process.env.E2E_MAP || 'both').trim().toLowerCase();
const runML = MODE === 'both' || MODE === 'maplibre';
const runMB = MODE === 'both' || MODE === 'mapbox';

async function solveTwoWaypoint(page:any) {
  // seed 2 waypoints and click Solve (reuses your SolveButton flow)
  await page.evaluate(() => {
    const W = (window as any).useWaypointStore.getState();
    W.setWaypoints([
      { id: '0', coordinates: [1.9, 14.3], type: 'Delivery' },
      { id: '1', coordinates: [39.5, 14.3], type: 'Delivery' }
    ]);
  });
  await page.getByRole('button', { name: /solve/i }).click();
  await page.waitForFunction(() => (window as any).useRouteStore.getState().routes.length > 0);
}

async function run(page:any, url:string) {
  await page.goto(url);
  await page.waitForFunction(() => (window as any).useRouteStore && (window as any).useUIStore);

  await solveTwoWaypoint(page);

  // turn traffic on
  await page.evaluate(() => (window as any).useUIStore.getState().setTrafficEnabled(true));

  // wait for style layer to appear (we used id 'route-traffic-line' in addTrafficLine)
  await page.waitForFunction(() => {
    const map = (window as any).__vrpMap;
    if (!map) return false;
    const layers = map.getStyle()?.layers || [];
    return !!layers.find((l:any) => l.id === 'route-traffic-line');
  });

  // turn traffic off and assert removal
  await page.evaluate(() => (window as any).useUIStore.getState().setTrafficEnabled(false));
  await page.waitForFunction(() => {
    const map = (window as any).__vrpMap;
    const layers = map.getStyle()?.layers || [];
    return !layers.find((l:any) => l.id === 'route-traffic-line');
  });
}

if (runML) test('Traffic gradient toggles layer (maplibre)', async ({ page }) => { await run(page, '/map/maplibre'); });
if (runMB) test('Traffic gradient toggles layer (mapbox)',   async ({ page }) => { await run(page, '/map/mapbox'); });
