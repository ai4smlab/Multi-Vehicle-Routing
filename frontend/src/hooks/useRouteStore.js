// hooks/useRouteStore.js
import { create } from 'zustand';
import { sumRouteTotals, computeGapPct } from '@/utils/metrics';

// Coords sanity (detect and fix [lat,lon] mistakenly stored instead of [lon,lat])
function fixLonLatPair(p) {
  if (!Array.isArray(p) || p.length < 2) return null;
  let [a, b] = p.map(Number);
  if (!Number.isFinite(a) || !Number.isFinite(b)) return null;
  // Heuristic: lat ∈ [-90,90], lon ∈ [-180,180]. If looks swapped, swap.
  const looksLikeLat = Math.abs(a) <= 90 && Math.abs(b) <= 180;
  const looksLikeLon = Math.abs(a) <= 180 && Math.abs(b) <= 90;
  // If first looks like lat and second like lon, we probably have [lat,lon] → swap.
  if (looksLikeLat && looksLikeLon && Math.abs(a) <= 90 && Math.abs(b) <= 180) {
    return [b, a];
  }
  return [a, b];
}
function fixLineString(line = []) {
  return (line || []).map(fixLonLatPair).filter(Boolean);
}

function enrichRoutesWithMeta(routes = [], meta = {}) {
  const costPerKm = Number(meta?.costPerKm ?? NaN);
  const vehMap =
    Array.isArray(meta?.vehicles)
      ? Object.fromEntries(meta.vehicles.map(v => [String(v.id), v]))
      : {};

  return routes.map(r => {
    // NOTE: total_distance is **meters** for our backends; do not convert here.
    const distMeters = Number(r?.total_distance ?? 0);
    const distKm = distMeters / 1000;

    const veh = vehMap[String(r?.vehicle_id)] || null;

    // emissions: prefer solver value; else vehicle.emissions_per_km * distance(km)
    let emissions = Number(r?.emissions);
    if (!Number.isFinite(emissions) && veh && Number.isFinite(veh.emissions_per_km)) {
      emissions = distKm * Number(veh.emissions_per_km);
    }

    // cost: prefer solver metadata.cost; else costPerKm or veh.cost_per_km (× km)
    let cost = Number(r?.metadata?.cost);
    const vCost = Number(veh?.cost_per_km);
    if (!Number.isFinite(cost)) {
      const use = Number.isFinite(costPerKm) ? costPerKm : (Number.isFinite(vCost) ? vCost : NaN);
      if (Number.isFinite(use)) cost = distKm * use;
    }

    // reliability: prefer solver metadata; else veh.reliability (0..1)
    let reliability = Number(r?.metadata?.reliability);
    if (!Number.isFinite(reliability) && Number.isFinite(veh?.reliability)) {
      reliability = Number(veh.reliability);
    }

    // normalize any baked geometry if present (guards against [lat,lon])
    const geom = Array.isArray(r?.geometry?.coordinates) ? { ...r.geometry, coordinates: fixLineString(r.geometry.coordinates) } : r?.geometry;

    return {
      ...r,
      geometry: geom,
      emissions: Number.isFinite(emissions) ? emissions : (r?.emissions ?? null),
      metadata: {
        ...(r?.metadata || {}),
        ...(Number.isFinite(cost) ? { cost } : {}),
        ...(Number.isFinite(reliability) ? { reliability } : {}),
      },
    };
  });
}

const useRouteStore = create((set, get) => ({
  // ── New model (source of truth)
  runs: [],               // [{ id, routes:[{...}], totals:{distanceKm,...}, ... }]
  activeRunId: null,

  // ── Back-compat surface (what older components expect)
  routes: [],             // mirror of runs (list of runs)
  currentIndex: 0,
  setIndex: (i) => {
    const n = get().runs.length;
    const idx = Math.max(0, Math.min((n || 1) - 1, Number(i) || 0));
    const run = get().runs[idx] || null;
    set({ currentIndex: idx, activeRunId: run ? run.id : null });
  },

  setActiveRunId: (id) => {
    const { runs } = get();
    const idx = Math.max(0, runs.findIndex(r => r.id === id));
    set({ activeRunId: id, currentIndex: idx < 0 ? 0 : idx });
  },

  getActiveRun: () => {
    const { runs, activeRunId } = get();
    return runs.find(r => r.id === activeRunId) || runs[0] || null;
  },

  bestDistanceRun: () => {
    const { runs } = get();
    if (!runs.length) return null;
    return runs.reduce((best, r) =>
      (r?.totals?.distanceKm ?? Infinity) < (best?.totals?.distanceKm ?? Infinity) ? r : best
    , runs[0]);
  },

  bestEcoRun: () => {
    const { runs } = get();
    const candidates = runs.filter(r => Number.isFinite(r?.totals?.emissions));
    if (!candidates.length) return null;
    return candidates.reduce((best, r) =>
      (r.totals.emissions) < (best.totals.emissions) ? r : best
    , candidates[0]);
  },

  // ── Actions used by panels (removed earlier)
  removeRouteAt: (idx) => {
    const { runs } = get();
    const i = Math.max(0, Math.min(runs.length - 1, Number(idx) || 0));
    const next = runs.slice(0, i).concat(runs.slice(i + 1));
    const newIdx = Math.max(0, Math.min(next.length - 1, i));
    const newActive = next[newIdx]?.id ?? null;
    set({
      runs: next,
      routes: next,            // mirror
      currentIndex: newIdx,
      activeRunId: newActive,
    });
  },

  clearAllRoutes: () => {
    set({ runs: [], routes: [], activeRunId: null, currentIndex: 0 });
  },

  // ── Main entry point
  addSolutionFromSolver: (solverResponse, waypoints, meta = {}) => {
    // 1) normalize legs
    const routesIn = solverResponse?.data?.routes || solverResponse?.routes || [];
    const enriched = enrichRoutesWithMeta(routesIn, meta);

    // 2) totals expect **meters/seconds** inside legs
    const totals = sumRouteTotals(enriched); // { distanceKm, durationMin, emissions, vehiclesUsed }

    // 3) best-known (km) + gap
    let bestKnownKm = null;
    if (Number.isFinite(meta?.bestKnownKm)) bestKnownKm = Number(meta.bestKnownKm);
    else if (Number.isFinite(meta?.comparison?.best)) bestKnownKm = Number(meta.comparison.best) / 1000;

    const ourKm = totals.distanceKm;
    const gapPct = computeGapPct(bestKnownKm, ourKm);

    const ts = Date.now();
    const run = {
      id: meta?.id || `run-${ts}`,
      createdAt: ts,
      solver: String(meta?.solver || 'unknown'),
      adapter: String(meta?.adapter || 'unknown'),
      type: String(meta?.vrpType || 'VRP'),
      routes: enriched,
      waypoints, // keep a copy for reconstruction/ETAs
      totals, // { distanceKm, durationMin, emissions, vehiclesUsed }
      benchmark: {
        dataset: meta?.benchmark?.dataset || null,
        name: meta?.benchmark?.name || null,
        bestKnownKm: Number.isFinite(bestKnownKm) ? bestKnownKm : null,
      },
      comparison: {
        bestKm: Number.isFinite(bestKnownKm) ? bestKnownKm : null,
        ourKm,
        gapPct,
      },
      status: solverResponse?.status || solverResponse?.data?.status || 'success',
      meta,
    };

    // 4) store (put newest first) + keep mirror, index and id in sync
    set((state) => {
      const next = [run, ...state.runs.filter(r => r.id !== run.id)];
      return {
        runs: next,
        routes: next,         // mirror for legacy readers
        activeRunId: run.id,
        currentIndex: 0,
      };
    });

    return run.id;
  },
}));

export default useRouteStore;
