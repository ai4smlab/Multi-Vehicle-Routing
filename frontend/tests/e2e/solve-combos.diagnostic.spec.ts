// tests/e2e/solve-combos.diagnostic.spec.ts
import { test, expect } from '@playwright/test';
import * as fs from 'node:fs';
import * as path from 'node:path';

const PAGE = process.env.MAP_PAGE ?? '/map/maplibre';

/* ──────────────────────────────
   Small helpers
   ────────────────────────────── */

async function ensureMapReady(page: any) {
  const canvas = page.locator('canvas.mapboxgl-canvas, canvas.maplibregl-canvas').first();
  await canvas.waitFor({ timeout: 20_000 }).catch(() => {});
  await page.waitForTimeout(300);
}

async function clickIfExists(page: any, locator: any) {
  if (await locator.count()) {
    try { await locator.first().click(); } catch {}
    await page.waitForTimeout(120);
  }
}

async function openRoutePlanner(page: any) {
  await clickIfExists(page, page.getByRole('button', { name: /route planner/i }));
  await clickIfExists(page, page.getByRole('button', { name: /🧠\s*solver/i }));
}

async function nudgeUIPanels(page: any) {
  const names = [
    /route planner/i, /vrp factor weights/i, /vrp result summary/i,
    /benchmark selector/i, /data manager/i, /real-?world dataset/i, /custom datasets/i,
  ];
  for (const rx of names) await clickIfExists(page, page.getByRole('button', { name: rx }));
}

// Wait until the three zustand stores are ready (wp + fleet are required; UI is nice-to-have)
async function ensureStores(page: any) {
  const until = Date.now() + 25_000;
  while (Date.now() < until) {
    const status = await page.evaluate(() => {
      const wps = (window as any).useWaypointStore;
      const fls = (window as any).useFleetStore;
      const uis = (window as any).useUIStore;
      return {
        wpReady: Boolean(wps?.setState && wps?.getState),
        flReady: Boolean(fls?.setState && fls?.getState),
        uiReady: Boolean(uis?.setState && uis?.getState),
      };
    });
    if (status.wpReady && status.flReady) return status;
    await nudgeUIPanels(page);
    await page.waitForTimeout(250);
  }
  return await page.evaluate(() => ({
    wpReady: Boolean((window as any).useWaypointStore?.setState),
    flReady: Boolean((window as any).useFleetStore?.setState),
    uiReady: Boolean((window as any).useUIStore?.setState),
  }));
}

async function seedFleet(page: any) {
  await page.evaluate(() => {
    const F = (window as any).useFleetStore;
    if (!F?.setState) throw new Error('Fleet store not present');
    F.setState({ vehicles: [{ id: 'veh-1', capacity: [999], start: 0, end: 0 }] }, false);
  });
}

async function waypointCount(page: any) {
  return page.evaluate(() => (window as any).useWaypointStore?.getState?.().waypoints?.length ?? 0);
}

// Enable click-to-add + disable bbox
async function enableClickToAdd(page: any) {
  await page.evaluate(() => {
    const ui = (window as any).useUIStore?.getState?.();
    ui?.setDrawBBoxEnabled?.(false);
    ui?.setAddOnClickEnabled?.(true);
    ui?.setClickToAddEnabled?.(true);
    (window as any).useUIStore?.setState?.({
      drawBBoxEnabled: false,
      addOnClickEnabled: true,
      clickToAdd: true,
      mode: 'add',
      interactionMode: 'add',
    }, false);
  });
}

// Robust click-through overlay until the canvas gets the click
async function smartClickCanvas(page: any, rx = 0.55, ry = 0.55) {
  const isMapbox = (await page.locator('canvas.mapboxgl-canvas').count()) > 0;
  const sel = isMapbox ? 'canvas.mapboxgl-canvas' : 'canvas.maplibregl-canvas';
  const canvas = page.locator(sel).first();
  await canvas.waitFor();

  const box = await canvas.boundingBox();
  if (!box) throw new Error('no canvas box');
  const x = Math.round(box.x + box.width * rx);
  const y = Math.round(box.y + box.height * ry);

  for (let i = 0; i < 5; i++) {
    await page.mouse.click(x, y);
    const hit = await page.evaluate(({ x, y }) => {
      const el = document.elementFromPoint(x, y) as HTMLElement | null;
      if (!el) return null;
      const cls = (el.className && typeof el.className === 'string') ? el.className : '';
      return { tag: el.tagName, id: el.id || '', className: cls };
    }, { x, y });

    if (hit && hit.tag === 'CANVAS') return; // success

    // peel the intercepting layer and retry
    if (hit) {
      await page.evaluate(({ id, className }) => {
        const setNone = (el: Element | null) => {
          if (el && el instanceof HTMLElement) el.style.setProperty('pointer-events', 'none', 'important');
        };
        const esc = (s: string) => (window as any).CSS?.escape?.(s) ?? s.replace(/[^a-zA-Z0-9_-]/g, '\\$&');
        if (id) setNone(document.getElementById(id));
        const firstClass = (className || '').split(/\s+/).filter(Boolean)[0];
        if (firstClass) document.querySelectorAll('.' + esc(firstClass)).forEach(setNone);
      }, hit);
    }
    await page.waitForTimeout(50);
  }
}

async function locateSolveButton(page: any) {
  const byId = page.getByTestId('solve-btn');
  if (await byId.count()) return byId.first();
  const byRoleExact = page.getByRole('button', { name: 'Solve', exact: true });
  if (await byRoleExact.count()) return byRoleExact.first();
  return page.locator('button').filter({ hasText: /^Solve$/ }).first();
}

function outPath(info: any, solver: string, vrpType: string, adapter: string, filename: string) {
  const dir = path.join(info.outputDir, 'solve-combos', `${solver}_${vrpType}_${adapter}`);
  fs.mkdirSync(dir, { recursive: true });
  return path.join(dir, filename);
}

function safeParse(s?: string | null) {
  if (!s) return null;
  try { return JSON.parse(s); } catch { return s; }
}

/* ──────────────────────────────
   Backend /capabilities probe
   ────────────────────────────── */

function normName(s: unknown) {
  return String(s ?? '')
    .trim()
    .toLowerCase()
    .replace(/[\s-]+/g, '_');
}

async function backendProbe(page: any, solver: string, adapter: string): Promise<{ known: boolean; supported: boolean; reason?: string }> {
  try {
    return await page.evaluate(async ({ solver, adapter }) => {
      const norm = (x: any) => String(x ?? '').trim().toLowerCase().replace(/[\s-]+/g, '_');
      try {
        const res = await fetch('/capabilities');
        if (!res.ok) return { known: false, supported: true };
        const caps = await res.json().catch(() => ({}));
        const rawSolvers = (caps?.data?.solvers ?? caps?.solvers ?? []) as any[];
        const rawAdapters = (caps?.data?.adapters ?? caps?.adapters ?? []) as any[];

        const solverNames = rawSolvers.map(s => (s?.name ?? s)).map(norm).filter(Boolean);
        const adapterNames = rawAdapters.map(a => (a?.name ?? a)).map(norm).filter(Boolean);

        const sOK = solverNames.length ? solverNames.includes(norm(solver)) : false;
        const aKnown = adapterNames.length > 0;
        const aOK = aKnown ? adapterNames.includes(norm(adapter)) : true;

        const reportedAnything = solverNames.length > 0 || adapterNames.length > 0;
        if (!reportedAnything) return { known: false, supported: true };

        const supported = sOK && aOK;
        return {
          known: true,
          supported,
          reason: supported ? undefined : `backend does not expose ${solver} / ${adapter} (solvers: ${solverNames.join(', ') || 'none'}, adapters: ${adapterNames.join(', ') || 'none'})`,
        };
      } catch {
        return { known: false, supported: true };
      }
    }, { solver, adapter });
  } catch {
    return { known: false, supported: true };
  }
}

/* ──────────────────────────────
   Capability matrix (match backend)
   ────────────────────────────── */

const SOLVERS: Record<string, Record<string, { required: string[] }>> = {
  mapbox_optimizer: {
    TSP: { required: ['waypoints', 'fleet==1'] },
    PD:  { required: ['waypoints', 'fleet==1', 'pickup_delivery_pairs'] },
  },
  ortools: {
    TSP:   { required: ['matrix.distances', 'fleet>=1', 'depot_index'] },
    CVRP:  { required: ['matrix.distances', 'fleet>=1', 'demands', 'depot_index'] },
    VRPTW: { required: ['matrix.durations', 'node_time_windows', 'fleet>=1', 'depot_index'] },
    PDPTW: { required: ['matrix.durations', 'node_time_windows', 'pickup_delivery_pairs', 'demands', 'fleet>=1', 'depot_index'] },
  },
  pyomo: {
    TSP:   { required: ['matrix.distances', 'fleet>=1', 'depot_index'] },
    CVRP:  { required: ['matrix.distances', 'fleet>=1', 'demands', 'depot_index'] },
    VRPTW: { required: ['matrix.durations', 'node_time_windows', 'fleet>=1', 'depot_index'] },
  },
  vroom: {
    TSP:   { required: ['waypoints|matrix', 'fleet==1', 'depot_index'] },
  },
};

const ADAPTERS = ['google', 'haversine', 'mapbox', 'openrouteservice', 'osm_graph'];

const COMBOS = Object.entries(SOLVERS).flatMap(([solver, types]) =>
  Object.keys(types).flatMap(vrpType =>
    ADAPTERS.map(adapter => ({ solver, vrpType, adapter }))
  )
);

/* ──────────────────────────────
   The tests
   ────────────────────────────── */

test.describe.configure({ mode: 'parallel', timeout: 60_000 });

test.describe('SolveButton diagnostic sweep (real UI, per-combo artifacts)', () => {
  for (const { solver, vrpType, adapter } of COMBOS) {
    test(`${solver} / ${vrpType} with ${adapter}`, async ({ page }, testInfo) => {
      // capture console + /distance-matrix & /solver network
      const consoleLines: string[] = [];
      page.on('console', (msg) => consoleLines.push(`[${msg.type()}] ${msg.text()}`));
      page.on('pageerror', (err) => consoleLines.push(`[pageerror] ${err?.message}`));
      page.on('dialog', async (dlg) => { consoleLines.push(`[dialog:${dlg.type()}] ${dlg.message()}`); await dlg.dismiss().catch(() => {}); });

      const net: any = { requests: [], responses: [] };
      page.on('request', (req) => {
        if (/(distance-matrix|solver)/.test(req.url())) {
          net.requests.push({ url: req.url(), method: req.method(), postData: safeParse(req.postData()) });
        }
      });
      page.on('response', async (res) => {
        if (/(distance-matrix|solver)/.test(res.url())) {
          let body: any = null; try { body = await res.json(); } catch {}
          net.responses.push({ url: res.url(), status: res.status(), body });
        }
      });

      // Flag for frontend to expose last payload if helpful
      await page.addInitScript(() => { (window as any).__E2E__ = true; });

      await page.goto(PAGE);
      await ensureMapReady(page);

      // Probe backend capabilities to skip truly unsupported combos
      const probe = await backendProbe(page, solver, adapter);
      test.skip(probe.known && !probe.supported, probe.reason);

      // Ensure stores, push UI selection if available, ensure a vehicle
      const storeStatus = await ensureStores(page);
      if (storeStatus.uiReady) {
        await page.evaluate(({ solver, adapter, vrpType }) => {
          const uis = (window as any).useUIStore;
          uis?.setState?.({ solverEngine: solver, routingAdapter: adapter, vrpType }, false);
        }, { solver, adapter, vrpType });
      } else {
        consoleLines.push(`[diag] UI store not available; requested: ${solver}/${vrpType}/${adapter}`);
      }
      if (storeStatus.flReady) await seedFleet(page);

      // route planner & add waypoints via real clicks
      await openRoutePlanner(page);
      await enableClickToAdd(page);

      const before = await waypointCount(page);
      await smartClickCanvas(page, 0.55, 0.55);
      await page.waitForTimeout(50);
      await smartClickCanvas(page, 0.65, 0.65);
      await expect.poll(() => waypointCount(page), { timeout: 8000 }).toBeGreaterThanOrEqual(before + 2);

      const solveBtn = await locateSolveButton(page);
      await solveBtn.waitFor({ state: 'attached', timeout: 10_000 });
      await expect(solveBtn, 'solve button should become enabled with >=2 waypoints').toBeEnabled();

      // Fire solve and wait for /solver response (or log if none)
      const solverPromise = page.waitForResponse(r => /\/solver\b/.test(r.url()), { timeout: 15_000 }).catch(() => null);
      await solveBtn.click();
      const solverRes = await solverPromise;
      if (!solverRes) {
        const dmSeen = net.responses.filter((r: any) => /distance-matrix/.test(r.url));
        consoleLines.push(`[diag] No /solver response observed. distance-matrix responses seen: ${dmSeen.length}`);
      }

      await page.waitForTimeout(700);

      // ── Tiny test tweak: verify adapter actually used on the wire ──
      const dmReq = net.requests.find((r: any) => /\/distance-matrix\b/.test(r.url));
      if (['ortools', 'pyomo'].includes(solver)) {
        expect.soft(!!dmReq, 'distance-matrix request should exist').toBe(true);
        const usedAdapter = dmReq?.postData?.adapter;
        expect.soft(usedAdapter, 'adapter sent to backend').toBe(adapter);
      } else {
        // vroom / mapbox_optimizer should not call /distance-matrix
        expect.soft(net.requests.some((r: any) => /\/distance-matrix\b/.test(r.url))).toBe(false);
      }

      // Additional soft checks to catch payload drift:
      const lastSolverReq = net.requests.filter((r: any) => /\/solver\b/.test(r.url)).slice(-1)[0];
      if (['ortools', 'pyomo'].includes(solver)) {
        expect.soft(lastSolverReq?.postData?.matrix, 'matrix must be present for ortools/pyomo').toBeTruthy();
        expect.soft(lastSolverReq?.postData?.vrp_type, 'vrp_type must NOT be present for ortools/pyomo').toBeFalsy();
      }
      if (solver === 'mapbox_optimizer') {
        expect.soft(lastSolverReq?.postData?.waypoints, 'mapbox_optimizer requires waypoints[]').toBeTruthy();
        expect.soft(lastSolverReq?.postData?.matrix, 'mapbox_optimizer must NOT send matrix').toBeFalsy();
      }

      // Read route store to judge success
      const state = await page.evaluate(() => {
        const S = (window as any).useRouteStore?.getState?.();
        return {
          routeCount: S?.routes?.length ?? 0,
          summary: S?.summary ?? null,
          routes: (S?.routes ?? []).map((r: any) => ({
            vehicleId: r.vehicleId, totalDistance: r.totalDistance, totalDuration: r.totalDuration,
            waypointIds: r.waypointIds
          })),
        };
      });

      // Persist artifacts
      const debug = { combo: { solver, vrpType, adapter }, storeStatus, state, net, console: consoleLines };
      const json = JSON.stringify(debug, null, 2);
      await testInfo.attach('debug.json', { body: json, contentType: 'application/json' });
      fs.writeFileSync(outPath(testInfo, solver, vrpType, adapter, 'debug.json'), json);

      // On failure, attach screenshot + friendly console summary
      if ((state.routeCount ?? 0) === 0) {
        const lastSolverRes = net.responses.filter((r: any) => /\/solver\b/.test(r.url)).slice(-1)[0];
        // eslint-disable-next-line no-console
        console.log('[DIAG SUMMARY]', JSON.stringify({
          combo: { solver, vrpType, adapter },
          requests: net.requests.map((r: any) => ({ url: r.url, method: r.method })),
          responses: net.responses.map((r: any) => ({ url: r.url, status: r.status, ok: r.status >= 200 && r.status < 300 })),
          solverRequestBody: lastSolverReq?.postData ?? null,
          solverResponseBody: lastSolverRes?.body ?? null,
          lastConsoleLines: consoleLines.slice(-5),
        }, null, 2));

        const shot = await page.screenshot();
        await testInfo.attach('failure.png', { body: shot, contentType: 'image/png' });
        fs.writeFileSync(outPath(testInfo, solver, vrpType, adapter, 'failure.png'), shot);

        test.info().annotations.push({ type: 'diag', description: 'No route stored' });
        expect.soft(state.routeCount, 'route count').toBeGreaterThan(0);
      }
    });
  }
});
