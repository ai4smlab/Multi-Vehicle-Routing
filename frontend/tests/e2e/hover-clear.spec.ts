// tests/e2e/hover-clear.spec.ts
import { test, expect } from '@playwright/test';
import 'dotenv/config';

const MODE = (process.env.E2E_MAP || 'both').trim().toLowerCase();
const runML = MODE === 'both' || MODE === 'maplibre';
const runMB = MODE === 'both' || MODE === 'mapbox';

async function ensureMapReady(page: any, isMapbox: boolean) {
  const sel = isMapbox ? 'canvas.mapboxgl-canvas' : 'canvas.maplibregl-canvas';
  await page.locator(sel).first().waitFor({ timeout: 10_000 });
  await page.waitForTimeout(250);
}

async function applyPeel(page: any, on: boolean) {
  await page.evaluate((on) => {
    const id = 'e2e-peel';
    const old = document.getElementById(id);
    if (!on) { old?.remove(); return; }
    if (old) return;
    const s = document.createElement('style');
    s.id = id;
    s.textContent = `
      /* Let clicks pass through Deck.gl/map wrappers only while adding */
      #view-default-view, #deckgl-overlay, #deckgl-wrapper { pointer-events: none !important; }
    `;
    document.head.appendChild(s);
  }, on);
}

async function enableClickToAdd(page: any) {
  await page.evaluate(() => (window as any).useUIStore?.getState?.().setDrawBBoxEnabled?.(false));
  // try UI affordance; if not available, patch store directly
  const toggled = await (async () => {
    const open = async (rx: RegExp) => {
      const btn = page.getByRole('button', { name: rx }).first();
      if (await btn.count()) { await btn.click().catch(() => {}); return true; }
      return false;
    };
    await open(/route planner/i);
    await open(/waypoints/i);
    const toggles = [
      page.getByRole('checkbox', { name: /click.*add/i }),
      page.getByRole('switch', { name: /click.*add/i }),
    ];
    for (const t of toggles) {
      if (await t.count()) {
        try { await t.first().check({ force: true }); } catch { await t.first().click({ force: true }); }
        return true;
      }
    }
    return false;
  })();
  if (!toggled) {
    await page.evaluate(() => {
      const ui = (window as any).useUIStore?.getState?.();
      ui?.setAddOnClickEnabled?.(true);
      ui?.setClickToAddEnabled?.(true);
      (window as any).useUIStore?.setState?.(
        { drawBBoxEnabled: false, addOnClickEnabled: true, clickToAdd: true, mode: 'add', interactionMode: 'add' },
        false
      );
    });
  }
}

async function disableClickToAdd(page: any) {
  await page.evaluate(() => {
    const ui = (window as any).useUIStore?.getState?.();
    ui?.setAddOnClickEnabled?.(false);
    ui?.setClickToAddEnabled?.(false);
    (window as any).useUIStore?.setState?.({ addOnClickEnabled: false, clickToAdd: false }, false);
  });
}

async function waypointCount(page: any) {
  return page.evaluate(() => (window as any).useWaypointStore.getState().waypoints.length);
}

async function waitForWaypointIncrement(page: any, from: number, timeout = 8_000) {
  return page.evaluate(
    ({ from, timeout }) =>
      new Promise<boolean>((resolve) => {
        const store = (window as any).useWaypointStore;
        if (!store) return resolve(false);
        if (store.getState().waypoints.length > from) return resolve(true);
        let settled = false;
        const unsub = store.subscribe((s: any) => {
          if (!settled && s.waypoints.length > from) { settled = true; unsub(); resolve(true); }
        });
        setTimeout(() => { if (!settled) { settled = true; unsub(); resolve(false); } }, timeout);
      }),
    { from, timeout }
  );
}

async function waitForHoverState(page: any, wantTruthy: boolean, timeout = 4_000) {
  return page.evaluate(
    ({ wantTruthy, timeout }) =>
      new Promise<boolean>((resolve) => {
        const store = (window as any).useWaypointStore;
        if (!store) return resolve(false);
        const read = () => {
          const s = store.getState();
          const v = s?.hoveredWaypoint ?? s?.hoveredWaypointId ?? s?.hovered ?? s?.hover ?? null;
          return !!v;
        };
        if (read() === wantTruthy) return resolve(true);
        let settled = false;
        const unsub = store.subscribe((_s: any) => {
          if (!settled && read() === wantTruthy) { settled = true; unsub(); resolve(true); }
        });
        setTimeout(() => { if (!settled) { settled = true; unsub(); resolve(false); } }, timeout);
      }),
    { wantTruthy, timeout }
  );
}

async function addWaypointAt(page: any, isMapbox: boolean, rx = 0.55, ry = 0.55) {
  const sel = isMapbox ? 'canvas.mapboxgl-canvas' : 'canvas.maplibregl-canvas';
  const canvas = page.locator(sel).first();
  await canvas.waitFor();

  const box = await canvas.boundingBox();
  if (!box) throw new Error('no canvas box');
  const x = Math.round(box.x + box.width * rx);
  const y = Math.round(box.y + box.height * ry);

  const before = await waypointCount(page);
  await applyPeel(page, true);               // ⬅️ let the click pass through
  await page.mouse.click(x, y);
  const added = await waitForWaypointIncrement(page, before, 1500);
  await applyPeel(page, false);              // ⬅️ restore overlay so hover can work
  return { added, x, y };
}

async function run(page: any, url: string, isMapbox: boolean) {
  await page.goto(url);
  await page.waitForFunction(() => (window as any).useWaypointStore && (window as any).useUIStore);
  await ensureMapReady(page, isMapbox);
  await enableClickToAdd(page);

  const before = await waypointCount(page);
  const { added, x, y } = await addWaypointAt(page, isMapbox, 0.55, 0.55);
  expect(added).toBe(true);

  await disableClickToAdd(page);

  // move over the waypoint (small jitter to ensure pointermove)
  await page.mouse.move(x, y);
  await page.waitForTimeout(50);
  await page.mouse.move(x + 2, y + 1);

  const hoveredOn = await waitForHoverState(page, true, 4000);
  expect(hoveredOn).toBe(true);

  // pan the map to clear hover
  const sel = isMapbox ? 'canvas.mapboxgl-canvas' : 'canvas.maplibregl-canvas';
  const canvas = page.locator(sel).first();
  const box = await canvas.boundingBox();
  if (!box) throw new Error('no canvas box');
  const cx = Math.round(box.x + box.width * 0.6);
  const cy = Math.round(box.y + box.height * 0.6);
  await page.mouse.move(cx, cy);
  await page.mouse.down();
  await page.mouse.move(cx + 80, cy + 10, { steps: 8 });
  await page.mouse.up();

  const hoveredOff = await waitForHoverState(page, false, 4000);
  expect(hoveredOff).toBe(true);

  // sanity: still exactly one waypoint
  const after = await waypointCount(page);
  expect(after).toBe(before + 1);
}

if (runML) {
  test('Hover clears on pan (maplibre)', async ({ page }) => {
    await run(page, '/map/maplibre', false);
  });
}
if (runMB) {
  test('Hover clears on pan (mapbox)', async ({ page }) => {
    await run(page, '/map/mapbox', true);
  });
}
