'use client';

import { useState, useMemo, useEffect } from 'react';
import Section from '@/components/sidebar/Section';
import useRouteStore from '@/hooks/useRouteStore';
import useWaypointStore from '@/hooks/useWaypointStore';
import useUiStore from '@/hooks/useUIStore';
import { computeETAsFromMatrix } from '@/utils/eta';
import useRenderSettingsStore from '@/hooks/useRenderSettingsStore';
import { useRouteGeometry } from '@/hooks/useRouteGeometry';

// tiny haversine (km)
const toRad = d => d * Math.PI / 180;
function haversineKm([lon1, lat1], [lon2, lat2]) {
  const R = 6371;
  const dLat = toRad(lat2 - lat1);
  const dLon = toRad(lon2 - lon1);
  const a = Math.sin(dLat / 2) ** 2 + Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(a));
}
function openPath(coords = []) {
  if (!coords?.length) return [];
  const A = coords[0], B = coords[coords.length - 1];
  const closed = Array.isArray(A) && Array.isArray(B) && A.length >= 2 && B.length >= 2 && A[0] === B[0] && A[1] === B[1];
  return closed ? coords.slice(0, -1) : coords;
}

const stripEta = (obj) => {
  if (!obj) return obj;
  const n = { ...obj };
  delete n.etaEpoch;
  delete n.etaIndices;
  delete n.etaRelative;
  delete n.etaTimestamps;
  delete n.etaStartEpoch;
  return n;
};

const clearRunEtas = (run) => {
  if (!run) return run;
  const base = stripEta(run);
  if (Array.isArray(base.routes)) {
    return { ...base, routes: base.routes.map(stripEta) };
  }
  return base;
};

function toLonLat(w) {
  if (!w) return null;
  if (Array.isArray(w.coordinates) && w.coordinates.length >= 2) {
    const [lon, lat] = w.coordinates; return [Number(lon), Number(lat)];
  }
  if (Array.isArray(w.location) && w.location.length >= 2) {
    const [lon, lat] = w.location; return [Number(lon), Number(lat)];
  }
  if (Number.isFinite(w.lon) && Number.isFinite(w.lat)) return [Number(w.lon), Number(w.lat)];
  if (w.location && Number.isFinite(w.location.lon) && Number.isFinite(w.location.lat)) {
    return [Number(w.location.lon), Number(w.location.lat)];
  }
  return null;
}
function extractRouteLeg(run) {
  return (run?.data?.routes && run.data.routes[0]) || (run?.routes && run.routes[0]) || null;
}
function extractCoords(run, globalWaypoints) {
  if (!run) return [];
  if (Array.isArray(run?.geometry?.coordinates)) return run.geometry.coordinates;
  const r0 = extractRouteLeg(run);
  if (Array.isArray(r0?.geometry?.coordinates)) return r0.geometry.coordinates;

  const ids = Array.isArray(r0?.waypoint_ids) ? r0.waypoint_ids.map(Number) : null;
  if (ids && ids.length) {
    const w =
      (Array.isArray(run?.waypoints) && run.waypoints) ||
      (Array.isArray(run?.meta?.waypoints) && run.meta.waypoints) ||
      (Array.isArray(run?.input?.waypoints) && run.input.waypoints) ||
      (Array.isArray(run?.ctx?.waypoints) && run.ctx.waypoints) ||
      (Array.isArray(globalWaypoints) && globalWaypoints) ||
      [];
    const ll = w.map(toLonLat).filter(Array.isArray);
    const coords = ids.map(i => ll[i]).filter(Array.isArray);
    if (coords.length >= 2) return coords;
  }

  const fallback = (globalWaypoints || []).map(toLonLat).filter(Array.isArray);
  return fallback.length >= 2 ? fallback : [];
}
function buildFallbackEtas(coords, speedKmh = 50) {
  const speedMps = (speedKmh * 1000) / 3600;
  const rel = [0];
  for (let i = 1; i < coords.length; i++) {
    rel.push(rel[i - 1] + (haversineKm(coords[i - 1], coords[i]) * 1000) / speedMps);
  }
  const t0 = Math.floor(Date.now() / 1000);
  const epoch = rel.map(s => t0 + Math.round(s));
  const indices = coords.map((_, i) => i);
  return { relSeconds: rel, epochSeconds: epoch, indices };
}

export default function RouteToolsPanel() {
  const runsOrRoutes = useRouteStore(s =>
  (Array.isArray(s.routes) && s.routes.length ? s.routes :
    (Array.isArray(s.runs) ? s.runs : []))
  );
  const currentIndex = useRouteStore(s => Number.isInteger(s.currentIndex) ? s.currentIndex : 0);
  const setIndexFn = useRouteStore(s => s.setIndex);
  const safeSetIndex = (i) => {
    if (typeof setIndexFn === 'function') return setIndexFn(i);
    useRouteStore.setState({ currentIndex: i });
  };

  const globalWaypoints = useWaypointStore(s => s.waypoints || []);

  const showETAs = useUiStore(s => s.etasEnabled) ?? false;
  const setShowETAs = useUiStore(s => s.setEtasEnabled) || (() => { });

  const uiGeom = useUiStore(s => s.geometrySource);
  const setUiGeom = useUiStore(s => s.setGeometrySource) || null;
  const geom = useRenderSettingsStore(s => s.geometrySource) || 'auto';
  const setGeom = useRenderSettingsStore(s => s.setGeometrySource);

  useEffect(() => {
    if (typeof uiGeom === 'string' && uiGeom !== geom) {
      setGeom(uiGeom);
      console.debug('[RouteGeom] ui geometrySource changed →', uiGeom);
    }
  }, [uiGeom]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (setUiGeom) setUiGeom(geom);
    try { localStorage.setItem('geometrySource', geom); } catch { }
  }, [geom, setUiGeom]);

  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const n = runsOrRoutes?.length ?? 0;
    if (!n) return;
    if (!Number.isInteger(currentIndex) || currentIndex < 0 || currentIndex >= n) {
      safeSetIndex(0);
    }
  }, [runsOrRoutes, currentIndex]);

  const active = useMemo(() => {
    const run = runsOrRoutes?.[currentIndex] ?? null;
    if (!run) return null;
    const coords = openPath(extractCoords(run, globalWaypoints));
    console.debug('[RouteGeom] active route extracted coords', {
      count: coords?.length || 0,
      first: coords?.[0],
      last: coords?.[coords.length - 1],
      from: run?.solver || run?.meta?.solver,
    });
    // keep any snapped/display coords that may have been persisted by hooks
    return { ...run, coords, displayCoords: run?.displayCoords };
  }, [runsOrRoutes, currentIndex, globalWaypoints]);

  // 🔌 Wire the geometry fetcher; it writes displayCoords into the store.
  const geoState = useRouteGeometry(active, { source: geom, profile: 'driving' });
  console.debug('[RTools] fetch geometry: ', geoState)

  const handleComputeETAs = async () => {
    // Prefer the *display* geometry (snapped) so ETAs line up with what you draw
    const coords =
      (Array.isArray(active?.displayCoords) && active.displayCoords.length > 1)
        ? active.displayCoords
        : active?.coords;
    if (!coords || coords.length < 2) return;
    setBusy(true);
    try {
      let times = [];
      let indices = [];
      try {
        const res = await computeETAsFromMatrix(coords, { profile: 'driving' });
        times = res?.times || [];
        indices = res?.indices || [];
        console.debug('[RouteGeom] ETA via backend matrix', { n: times.length });
      } catch (e) {
        console.warn('[RouteGeom] ETA backend failed, fallback', e?.message || e);
      }

      if (!Array.isArray(times) || times.length === 0) {
        const fb = buildFallbackEtas(coords, 50);
        times = fb.epochSeconds;
        indices = fb.indices;
        console.debug('[RouteGeom] ETA fallback haversine', { n: times.length });
      }

      useRouteStore.setState((s) => {
        const list = Array.isArray(s.routes) ? [...s.routes] : (Array.isArray(s.runs) ? [...s.runs] : []);
        const key = Array.isArray(s.routes) ? 'routes' : (Array.isArray(s.runs) ? 'runs' : 'routes');
        const idx = Number.isInteger(s.currentIndex) ? s.currentIndex : 0;
        const r0 = { ...(list[idx] || {}) };
        r0.etaEpoch = times;
        r0.etaIndices = indices;
        const t0 = times[0] ?? Math.floor(Date.now() / 1000);
        r0.etaRelative = times.map(t => (typeof t === 'number' ? t - t0 : 0));
        r0.etaTimestamps = times;
        r0.etaStartEpoch = t0;
        list[idx] = r0;
        return { [key]: list };
      });

      setShowETAs(true); // flips useUiStore().etasEnabled
      console.debug('[RouteGeom] ETA set (final)', { count: times.length });
    } finally {
      setBusy(false);
    }
  };

  const handleClearETAs = () => {
    // hide native glyph overlay immediately
    useUiStore.getState().setEtasEnabled(false);

    useRouteStore.setState((s) => {
      const idx = Number.isInteger(s.currentIndex) ? s.currentIndex : 0;

      // both arrays exist; keep them consistent
      const runs = Array.isArray(s.runs) ? [...s.runs] : [];
      const routes = Array.isArray(s.routes) ? [...s.routes] : runs;

      if (routes[idx]) routes[idx] = clearRunEtas(routes[idx]);
      if (runs[idx]) runs[idx] = clearRunEtas(runs[idx]);

      return { runs, routes };
    });
  };

  const hasRuns = Array.isArray(runsOrRoutes) && runsOrRoutes.length > 0;

  return (
    <Section title="🛠 Route Tools">
      {!hasRuns ? (
        <div className="text-xs text-gray-500">No active route.</div>
      ) : (
        <>
          <div className="mb-3">
            <label className="block text-xs font-semibold mb-1">Geometry source</label>
            <select
              value={geom}
              onChange={(e) => setGeom(e.target.value)}
              className="w-full text-xs px-2 py-1 bg-slate-800 text-white rounded"
            >
              <option value="auto">Auto (Backend → Mapbox → OSRM → Original)</option>
              <option value="backend">Backend (matrix returns geometry)</option>
              <option value="mapbox">Mapbox Match (via backend)</option>
              <option value="osrm">OSRM Match (public)</option>
              <option value="none">Original (straight segments)</option>
            </select>
          </div>

          <div className="text-xs mb-2">
            Points: {active?.coords?.length ?? 0}{' '}
            {active?.etaEpoch ? `• ETAs: ${active.etaEpoch.length}` : ''}
          </div>

          <div className="flex gap-2">
            <button
              disabled={busy || !((active?.coords?.length ?? 0) > 1)}
              onClick={handleComputeETAs}
              className="px-2 py-1 text-xs rounded bg-blue-600 text-white disabled:bg-gray-400"
            >
              {busy ? 'Computing…' : 'Compute ETAs'}
            </button>

            <button
              onClick={() => setShowETAs(!showETAs)}
              className="px-2 py-1 text-xs rounded bg-slate-700 text-white"
            >
              {showETAs ? 'Hide ETAs' : 'Show ETAs'}
            </button>

            <button
              onClick={handleClearETAs}
              className="px-2 py-1 text-xs rounded bg-gray-400"
            >
              Clear ETAs
            </button>
          </div>
        </>
      )}
    </Section>
  );
}
