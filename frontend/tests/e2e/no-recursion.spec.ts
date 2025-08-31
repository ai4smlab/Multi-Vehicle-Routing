import { test, expect } from '@playwright/test';
import 'dotenv/config';

const MODE = (process.env.E2E_MAP || 'both').trim().toLowerCase();
const runML = MODE === 'both' || MODE === 'maplibre';
const runMB = MODE === 'both' || MODE === 'mapbox';

async function run(page:any, url:string, isMapbox:boolean) {
  const errors:string[] = [];
  page.on('console', (msg) => {
    const t = msg.text();
    if (t.includes('Maximum update depth exceeded')) errors.push(t);
  });

  await page.goto(url);
  const target = isMapbox ? page.locator('canvas.mapboxgl-canvas').first()
                          : page.locator('canvas').first();
  const box = await target.boundingBox();
  if (!box) throw new Error('no canvas');

  // quick pan & zoom bursts
  for (let i=0;i<4;i++){
    await page.mouse.move(box.x + box.width/2, box.y + box.height/2);
    await page.mouse.down();
    await page.mouse.move(box.x + box.width/2 + 100, box.y + box.height/2);
    await page.mouse.up();
    await page.mouse.wheel(0, i%2===0 ? -200 : 200);
  }

  expect(errors, 'no "Maximum update depth exceeded" in console').toHaveLength(0);
}

if (runML) test('No recursion errors under stress (maplibre)', async ({ page }) => { await run(page, '/map/maplibre', false); });
if (runMB) test('No recursion errors under stress (mapbox)',   async ({ page }) => { await run(page, '/map/mapbox', true); });
