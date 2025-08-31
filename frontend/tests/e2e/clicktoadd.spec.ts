// tests/e2e/clicktoadd.spec.ts
import { test, expect } from '@playwright/test';
import 'dotenv/config';

const MODE = (process.env.E2E_MAP || 'both').trim().toLowerCase();
const runML = MODE === 'both' || MODE === 'maplibre';
const runMB = MODE === 'both' || MODE === 'mapbox';

async function waypointCount(page: any) {
  return page.evaluate(() => (window as any).useWaypointStore.getState().waypoints.length);
}

async function ensureMapReady(page: any, isMapbox: boolean) {
  const sel = isMapbox ? 'canvas.mapboxgl-canvas' : 'canvas.maplibregl-canvas';
  await page.locator(sel).first().waitFor({ timeout: 10_000 });
  // brief idle to let handlers attach
  await page.waitForTimeout(250);
}

async function enableClickToAddViaUI(page: any): Promise<boolean> {
  // Open Route Planner → Waypoints if present
  const open = async (rx: RegExp) => {
    const btn = page.getByRole('button', { name: rx }).first();
    if (await btn.count()) {
      await btn.click().catch(() => {});
      return true;
    }
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
      try {
        await t.first().check({ force: true });
      } catch {
        await t.first().click({ force: true });
      }
      return true;
    }
  }
  return false;
}

async function enableClickToAdd(page: any) {
  // Turn bbox off first
  await page.evaluate(() => (window as any).useUIStore?.getState?.().setDrawBBoxEnabled?.(false));
  // Try UI; if not found, patch the store directly
  const toggled = await enableClickToAddViaUI(page);
  if (!toggled) {
    await page.evaluate(() => {
      const ui = (window as any).useUIStore?.getState?.();
      ui?.setAddOnClickEnabled?.(true);
      ui?.setClickToAddEnabled?.(true);
      (window as any).useUIStore?.setState?.(
        {
          drawBBoxEnabled: false,
          addOnClickEnabled: true,
          clickToAdd: true,
          mode: 'add',
          interactionMode: 'add',
        },
        false
      );
    });
  }
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
          if (!settled && s.waypoints.length > from) {
            settled = true;
            unsub();
            resolve(true);
          }
        });
        setTimeout(() => {
          if (!settled) {
            settled = true;
            unsub();
            resolve(false);
          }
        }, timeout);
      }),
    { from, timeout }
  );
}

// Returns basic info about the element under (x,y)
async function elementAt(page: any, x: number, y: number) {
  return page.evaluate(({ x, y }) => {
    const el = document.elementFromPoint(x, y) as HTMLElement | null;
    if (!el) return null;
    const cls = typeof el.className === 'string' ? el.className : '';
    return { tag: el.tagName, id: el.id || '', className: cls };
  }, { x, y });
}

// Disable pointer events on an element by id or first CSS class (browser-side)
async function disablePointerEvents(page: any, hit: { id: string; className: string }) {
  await page.evaluate(({ id, className }) => {
    const setNone = (el: Element | null) => {
      if (el && el instanceof HTMLElement) el.style.setProperty('pointer-events', 'none', 'important');
    };
    const esc = (s: string) => (window as any).CSS?.escape?.(s) ?? s.replace(/[^a-zA-Z0-9_-]/g, '\\$&');

    if (id) setNone(document.getElementById(id));

    const firstClass = (className || '').split(/\s+/).filter(Boolean)[0];
    if (firstClass) {
      const sel = '.' + esc(firstClass);
      document.querySelectorAll(sel).forEach(setNone);
    }
  }, hit);
}

// Try clicking a list of targets; succeed if the waypoint count increments
async function clickUsingTargets(
  page: any,
  selectors: string[],
  rx: number,
  ry: number,
  before: number,
  timeoutPerTry = 1200
) {
  for (const sel of selectors) {
    const el = page.locator(sel).first();
    if (!(await el.count())) continue;
    const box = await el.boundingBox();
    if (!box) continue;
    const x = Math.round(box.x + box.width * rx);
    const y = Math.round(box.y + box.height * ry);
    await page.mouse.click(x, y);
    const ok = await waitForWaypointIncrement(page, before, timeoutPerTry);
    if (ok) return true;
  }
  return false;
}

// Temporarily peel Deck.gl wrappers (pointer-events: none) while executing fn
async function withDeckglPeel<T>(page: any, fn: () => Promise<T>): Promise<T> {
  await page.evaluate(() => {
    const ids = ['view-default-view', 'deckgl-overlay', 'deckgl-wrapper'];
    ids.forEach((id) => {
      const el = document.getElementById(id) as HTMLElement | null;
      if (el) {
        (el as any)._pe = el.style.pointerEvents || '';
        el.style.pointerEvents = 'none';
      }
    });
  });
  try {
    return await fn();
  } finally {
    await page.evaluate(() => {
      const ids = ['view-default-view', 'deckgl-overlay', 'deckgl-wrapper'];
      ids.forEach((id) => {
        const el = document.getElementById(id) as HTMLElement | null;
        if (el) {
          el.style.pointerEvents = (el as any)._pe || '';
          delete (el as any)._pe;
        }
      });
    });
  }
}

async function run(page: any, url: string, isMapbox: boolean) {
  await page.goto(url);
  await page.waitForFunction(() => (window as any).useWaypointStore && (window as any).useUIStore);
  await ensureMapReady(page, isMapbox);
  await enableClickToAdd(page);

  const before = await waypointCount(page);

  // 1) Click where Deck.gl would receive the event (overlay-first)
  const overlayTargets = ['#deckgl-overlay', '#deckgl-wrapper', '#view-default-view', 'div.flex-1.relative'];
  let changed = await clickUsingTargets(page, overlayTargets, 0.55, 0.55, before);

  // 2) If that didn’t work, peel and click the base map canvas
  if (!changed) {
    const canvasTargets = isMapbox ? ['canvas.mapboxgl-canvas'] : ['canvas.maplibregl-canvas'];
    changed = await withDeckglPeel(page, async () =>
      clickUsingTargets(page, canvasTargets, 0.55, 0.55, before)
    );
  }

  if (!changed) {
    const ui = await page.evaluate(() => (window as any).useUIStore?.getState?.());
    console.log('UI state (debug):', {
      drawBBoxEnabled: ui?.drawBBoxEnabled,
      addOnClickEnabled: ui?.addOnClickEnabled,
      clickToAdd: ui?.clickToAdd,
      mode: ui?.mode,
      interactionMode: ui?.interactionMode,
    });
  }
  expect(changed).toBe(true);

  // 3) Turn BBox ON and explicitly disable click-to-add
  await page.evaluate(() => {
    const ui = (window as any).useUIStore?.getState?.();
    ui?.setDrawBBoxEnabled?.(true);
    ui?.setAddOnClickEnabled?.(false);
    ui?.setClickToAddEnabled?.(false);
    (window as any).useUIStore?.setState?.({ addOnClickEnabled: false, clickToAdd: false }, false);
  });

  // Click again (no peel) — draw tool should capture it, so waypoint count must NOT increment
  await clickUsingTargets(page, overlayTargets, 0.65, 0.65, before, 400);
  const after = await waypointCount(page);
  expect(after).toBe(before + 1);
}

if (runML) {
  test('Click to add waypoint (maplibre)', async ({ page }) => {
    await run(page, '/map/maplibre', false);
  });
}

if (runMB) {
  test('Click to add waypoint (mapbox)', async ({ page }) => {
    await run(page, '/map/mapbox', true);
  });
}
