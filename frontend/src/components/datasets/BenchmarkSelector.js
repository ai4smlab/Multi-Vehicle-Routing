'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import Section from '@/components/sidebar/Section';
import { useBenchmarks, useBenchmarkFiles, useDistanceMatrix, useSolve, useCapabilities } from '@/hooks/useBackend';
import api from '@/api/api';
import useWaypointStore from '@/hooks/useWaypointStore';
import useFleetStore from '@/hooks/useFleetStore';
import useMapStore from '@/hooks/useMapStore';
import useUiStore from '@/hooks/useUIStore';
import useRouteStore from '@/hooks/useRouteStore';
import fitToFeatures from '@/components/map/fitToFeatures';
import { normalizeFleetForBackend } from '@/utils/normalizeFleetForBackend';
import { haversineMeters } from '@/utils/metrics';
import { getSolverSpec } from '@/utils/capabilityHelpers';
import { normalizeInstanceResponse } from '@/utils/normalizeInstance';
import { buildEuclideanMatrix } from '@/utils/euclideanMatrix';

const stripExt = (n) => String(n || '').replace(/\.[^.]+$/, '');
const isFiniteNum = (x) => Number.isFinite(Number(x));
const inWGS84 = (lon, lat) => isFiniteNum(lon) && isFiniteNum(lat) && lon >= -180 && lon <= 180 && lat >= -90 && lat <= 90;

const inferVrpType = (waypoints, vehiclesLike) => {
  const hasTW = waypoints.some(w => Array.isArray(w.timeWindow) && w.timeWindow.length === 2);
  const hasPD = waypoints.some(w => w?.pairId != null);
  const hasDemand = waypoints.some(w => (w?.demand ?? 0) > 0);
  const hasCap = (Array.isArray(vehiclesLike) ? vehiclesLike : []).some(v => Array.isArray(v?.capacity) && v.capacity.some(c => c > 0));

  if (hasPD && hasTW) return 'PDPTW';
  if (hasPD) return 'PD';
  if (hasTW) return 'VRPTW';
  if (hasDemand && hasCap) return 'CVRP';
  return 'TSP';
};

function median(a) {
  const b = (a || []).map(Number).filter(Number.isFinite).sort((x, y) => x - y);
  return b.length ? (b.length % 2 ? b[(b.length - 1) / 2] : (b[b.length / 2 - 1] + b[b.length / 2]) / 2) : 0;
}
function estimateSecsPerDist(distances, durations) {
  const ds = [];
  const ts = [];
  if (Array.isArray(distances) && Array.isArray(durations) && distances.length && durations.length) {
    for (let i = 0; i < Math.min(distances.length, durations.length); i++) {
      for (let j = 0; j < Math.min(distances[i]?.length || 0, durations[i]?.length || 0); j++) {
        if (i === j) continue;
        const d = Number(distances[i][j]), t = Number(durations[i][j]);
        if (Number.isFinite(d) && Number.isFinite(t) && d > 0 && t > 0) { ds.push(d); ts.push(t); }
      }
    }
  }
  const md = median(ds), mt = median(ts);
  return md > 0 ? Math.max(1, Math.round(mt / md)) : 60; // fallback 60 s/unit
}
function normalizeServiceTimes(node_service_times, secsPerUnit) {
  let st = (node_service_times || []).slice();
  const before = median(st);
  let action = 'none';

  // If clearly “minutes mistaken as seconds” (e.g., 5400), divide by 60
  if (before > secsPerUnit * 20) {
    st = st.map(s => Math.max(0, Math.round(Number(s || 0) / 60)));
    action = 'divide_by_60';
  }

  // If uniform >0 value and not close to canonical Solomon 10 units, snap to 10*secsPerUnit
  const uniq = Array.from(new Set(st.filter(x => x > 0)));
  if (uniq.length === 1) {
    const v = uniq[0];
    const target = 10 * secsPerUnit;
    if (Math.abs(v - target) > secsPerUnit * 2) {
      st = st.map(s => (s > 0 ? target : 0));
      action += (action === 'none' ? '' : '+') + 'snap_to_10u';
    }
  }
  return { st, action, before, after: median(st) };
}



/** project arbitrary XY to a ~1.2° box around (0,0) for display */
function projectXYToLonLat(pointsXY /* [{X,Y}] */) {
  if (!Array.isArray(pointsXY) || !pointsXY.length) return [];
  const xs = pointsXY.map(p => p.X), ys = pointsXY.map(p => p.Y);
  const minX = Math.min(...xs), maxX = Math.max(...xs);
  const minY = Math.min(...ys), maxY = Math.max(...ys);
  const w = Math.max(1e-9, maxX - minX), h = Math.max(1e-9, maxY - minY);
  const cx = (minX + maxX) / 2, cy = (minY + maxY) / 2;
  const sx = 1.2 / w, sy = 1.2 / h;
  return pointsXY.map(p => ({ lon: (p.X - cx) * sx, lat: (p.Y - cy) * sy }));
}

/** detect planar/EUCLIDEAN using meta and XY presence (NOT suppressed by display_lon/lat) */
function detectPlanar(meta, waypoints) {
  const fmt = String(meta?.format || '').toLowerCase();
  if (/solomon|euc_2d|euclidean|vrplib/.test(fmt)) return true;
  const xyCount = (waypoints || []).filter(w => isFiniteNum(w?.x) && isFiniteNum(w?.y)).length;
  const n = (waypoints || []).length;
  return n > 0 && xyCount >= Math.ceil(n * 0.6);
}

/** choose map display coords and report planar flag */
function buildDisplayWaypoints(dataWaypoints, fileId, meta) {
  const n = (dataWaypoints || []).length;
  const planar = detectPlanar(meta, dataWaypoints);

  const raw = (dataWaypoints || []).map((w, i) => {
    const dispLon = Number(w.display_lon);
    const dispLat = Number(w.display_lat);
    const lon = Number(w.lon);
    const lat = Number(w.lat);
    const X = isFiniteNum(w.x) ? Number(w.x) : (isFiniteNum(w.lat) ? Number(w.lat) : NaN);
    const Y = isFiniteNum(w.y) ? Number(w.y) : (isFiniteNum(w.lon) ? Number(w.lon) : NaN);
    return {
      id: w.id ?? String(i),
      depot: !!w.depot,
      demand: Number(w.demand ?? 0),
      service: Number(w.service_time ?? w.serviceTime ?? 0),
      tw: Array.isArray(w.time_window) ? w.time_window : (w.timeWindow ?? null),
      dispLon, dispLat, lon, lat, X, Y
    };
  });

  let mapCoords = new Array(n);
  if (planar) {
    // always project XY for planar datasets (even if display_lon/lat are present)
    const xy = raw.map(r => ({ X: r.X, Y: r.Y }));
    mapCoords = projectXYToLonLat(xy);
  } else {
    // prefer display lon/lat, else native lon/lat
    const haveGoodDisplay = raw.every(r => inWGS84(r.dispLon, r.dispLat));
    const haveGoodLonLat = raw.every(r => inWGS84(r.lon, r.lat));
    if (haveGoodDisplay) mapCoords = raw.map(r => ({ lon: r.dispLon, lat: r.dispLat }));
    else if (haveGoodLonLat) mapCoords = raw.map(r => ({ lon: r.lon, lat: r.lat }));
    else mapCoords = raw.map(() => ({ lon: 0, lat: 0 }));
  }

  const wp = raw.map((r, i) => ({
    id: String(r.id),
    coordinates: [mapCoords[i].lon, mapCoords[i].lat],
    x: isFiniteNum(r.X) ? Number(r.X) : undefined,
    y: isFiniteNum(r.Y) ? Number(r.Y) : undefined,
    fileId,
    type: r.depot ? 'Depot' : 'Delivery',
    demand: r.demand,
    capacity: null,
    serviceTime: r.service,
    timeWindow: r.tw,
    pairId: null
  }));

  return { wp, planar };
}

/* ---------------------- NEW: Debug helpers (copy-paste friendly) ---------------------- */
function offDiagStats(mat) {
  if (!Array.isArray(mat) || !mat.length) return null;
  const vals = [];
  for (let i = 0; i < mat.length; i++) {
    const row = mat[i] || [];
    for (let j = 0; j < row.length; j++) {
      if (i === j) continue;
      const v = Number(row[j]);
      if (Number.isFinite(v)) vals.push(v);
    }
  }
  if (!vals.length) return null;
  vals.sort((a, b) => a - b);
  const sum = vals.reduce((s, v) => s + v, 0);
  const mean = sum / vals.length;
  const mid = Math.floor(vals.length / 2);
  const median = vals.length % 2 ? vals[mid] : (vals[mid - 1] + vals[mid]) / 2;
  return {
    count: vals.length,
    min: vals[0],
    max: vals[vals.length - 1],
    mean,
    median
  };
}
function tl(mat, k = 10) {
  if (!Array.isArray(mat)) return null;
  const n = Math.min(k, mat.length);
  return Array.from({ length: n }, (_, i) =>
    Array.from({ length: n }, (_, j) => Number(mat[i]?.[j] ?? 0))
  );
}
function checksum2D(mat) {
  if (!Array.isArray(mat) || !mat.length) return 0;
  let s = 0;
  for (let i = 0; i < mat.length; i++) {
    const row = mat[i] || [];
    for (let j = 0; j < row.length; j++) {
      const v = Number(row[j]);
      if (Number.isFinite(v)) s += v;
    }
  }
  return Number(s.toFixed(3));
}
function guessDurationUnits(dur) {
  const s = offDiagStats(dur);
  if (!s) return 'unknown';
  // crude heuristic: typical Solomon sec-medians are in the 1000s
  if (s.median >= 300) return 'seconds?';
  if (s.median >= 10) return 'minutes?';
  return 'small-units?';
}
function buildDebugBundle({
  dataset, name, solver, adapter, vrpType,
  depotIndex, planarDetected, matrixSource,
  waypoints, vehicles, matrix,
  demands, node_service_times, node_time_windows, vehicle_time_windows
}) {
  const n = matrix?.distances?.length || matrix?.durations?.length || 0;
  const distancesStats = offDiagStats(matrix?.distances);
  const durationsStats = offDiagStats(matrix?.durations);
  const durationUnitsGuess = guessDurationUnits(matrix?.durations);

  const coords_sample = (waypoints || []).slice(0, 5).map(w => w.coordinates);
  const xy_present = (waypoints || []).filter(w => Number.isFinite(w?.x) && Number.isFinite(w?.y)).length;

  const vehicleSummary = (vehicles || []).map(v => ({
    id: v.id, start: v.start, end: v.end,
    capacity: Array.isArray(v.capacity) ? v.capacity : []
  }));

  const bundle = {
    meta: {
      dataset, name, solver, adapter, vrpType,
      depot_index: depotIndex,
      planar_detected: planarDetected,
      matrix_source: matrixSource
    },
    sizes: {
      nodes: n,
      vehicles: (vehicles || []).length,
      xy_present
    },
    coords_sample,
    vehicles: vehicleSummary,
    constraints: {
      demands,
      node_service_times,
      node_time_windows,
      vehicle_time_windows
    },
    matrix: {
      has_distances: Array.isArray(matrix?.distances),
      has_durations: Array.isArray(matrix?.durations),
      distances_checksum: Array.isArray(matrix?.distances) ? checksum2D(matrix.distances) : null,
      durations_checksum: Array.isArray(matrix?.durations) ? checksum2D(matrix.durations) : null,
      distances_stats_offdiag: distancesStats,
      durations_stats_offdiag: durationsStats,
      durations_units_guess: durationUnitsGuess,
      distances_top_left_10: tl(matrix?.distances, 10),
      durations_top_left_10: tl(matrix?.durations, 10)
    }
  };
  return bundle;
}
/* ------------------------------------------------------------------------------------ */

export default function BenchmarkSelector() {
  // ---- stores / helpers ----
  const addWaypoint = useWaypointStore(s => s.addWaypoint);
  const removeWaypointsByFileId = useWaypointStore(s => s.removeWaypointsByFileId);
  const setViewState = useMapStore(s => s.setViewState);

  const setSolverEngine = useUiStore(s => s.setSolverEngine);
  const setRoutingAdapter = useUiStore(s => s.setRoutingAdapter);
  const setVrpType = useUiStore(s => s.setVrpType);

  const dm = useDistanceMatrix();
  const solve = useSolve();
  const addSolution = useRouteStore.getState().addSolutionFromSolver;

  // local UI state
  const [availableSolvers, setAvailableSolvers] = useState([]);
  const [solver, setSolver] = useState('ortools');
  const [adapter, setAdapter] = useState('haversine');
  const [busy, setBusy] = useState(false);
  const [loadedMeta, setLoadedMeta] = useState(null);
  const [planarDetected, setPlanarDetected] = useState(false);

  const loadedRef = useRef(null);       // { dataset, name, bestKnown, matrix, depotIndex, format, planar }
  const lastMiniRef = useRef(null);     // mini box values

  // NEW: Keep last debug JSON for quick copy
  const [lastDebugBundleText, setLastDebugBundleText] = useState('');

  // ---- fetch caps for dropdowns ----
  const capsQ = useCapabilities();
  const solverOptions = useMemo(() => {
    const list = capsQ.data?.solvers || [];
    const names = Array.isArray(list) ? list.map(s => s.name) : Object.keys(list || {});
    return names?.length ? names : ['ortools', 'pyomo', 'vroom', 'mapbox_optimizer'];
  }, [capsQ.data]);

  const adapterOptions = useMemo(() => {
    if (planarDetected) return ['euclidean (local)'];
    const names = capsQ.data?.adapters?.map(a => a.name);
    return names?.length ? names : ['haversine', 'osm_graph', 'openrouteservice', 'google', 'mapbox'];
  }, [capsQ.data, planarDetected]);

  // ---- datasets ----
  const benchmarksQ = useBenchmarks();
  const datasetOptions = benchmarksQ.data?.datasets?.map(d => d.name) ?? [];

  const [dataset, setDataset] = useState('');
  useEffect(() => { if (!dataset && datasetOptions.length) setDataset(datasetOptions[0]); }, [dataset, datasetOptions]);

  // ---- file search / paging ----
  const [search, setSearch] = useState('');
  const [limit, setLimit] = useState(50);
  const [offset, setOffset] = useState(0);

  const filesParams = useMemo(() => dataset ? ({ dataset, q: search || undefined, limit, offset }) : null, [dataset, search, limit, offset]);
  const filesQ = useBenchmarkFiles(filesParams);
  const items = filesQ.data?.items ?? [];
  const total = filesQ.data?.total ?? 0;
  const page = Math.floor(offset / limit) + 1;
  const pages = Math.max(1, Math.ceil(total / limit));

  // ---- load instance ----
  const [currentFileId, setCurrentFileId] = useState(null);

  // keep global UI store updated when local controls change
  useEffect(() => { setSolverEngine?.(solver); }, [solver, setSolverEngine]);
  useEffect(() => { setRoutingAdapter?.(adapter); }, [adapter, setRoutingAdapter]);

  const handleLoad = async (name) => {
    if (!dataset || !name) return;
    const stem = stripExt(name);
    try {
      console.debug('[Benchmark] /benchmarks/load', { dataset, name: stem });
      const payload = await api.get('/benchmarks/load', { params: { dataset, name: stem, compute_matrix: true } }).then(r => r.data);
      const data = normalizeInstanceResponse(payload);

      if (!data?.waypoints?.length) throw new Error('Empty instance');

      if (currentFileId) removeWaypointsByFileId?.(currentFileId);
      const fileId = `bench:${dataset}:${stem}:${Date.now()}`;

      // display coords & planar detection
      const { wp, planar } = buildDisplayWaypoints(data.waypoints, fileId, data?.meta);
      wp.forEach(addWaypoint);
      setPlanarDetected(planar);
      if (planar) setAdapter('euclidean (local)'); // force

      // fleet
      const vehicles =
        Array.isArray(data.fleet) ? data.fleet
          : Array.isArray(data.fleet?.vehicles) ? data.fleet.vehicles
            : [];
      const stFleet = useFleetStore.getState();
      if (typeof stFleet.setVehicles === 'function') stFleet.setVehicles(vehicles);
      else if (typeof stFleet.replaceAll === 'function') stFleet.replaceAll(vehicles);
      else if (typeof stFleet.addVehicle === 'function') vehicles.forEach(v => stFleet.addVehicle(v));

      // auto VRP type
      const inferred = inferVrpType(wp, vehicles);
      setVrpType(inferred);

      // zoom
      const fc = {
        type: 'FeatureCollection',
        features: wp.map(w => ({
          type: 'Feature',
          geometry: { type: 'Point', coordinates: w.coordinates },
          properties: { type: w.type }
        }))
      };
      fitToFeatures(fc.features, { setViewState });

      setCurrentFileId(fileId);

      // solver options filtered by VRP type
      const caps = capsQ.data;
      const raw = (caps?.solvers);
      let allSolverNames = [];
      if (Array.isArray(raw)) allSolverNames = raw.map((s) => s?.name ?? String(s));
      else if (raw && typeof raw === 'object') allSolverNames = Object.keys(raw);
      else allSolverNames = ['ortools', 'pyomo', 'vroom', 'mapbox_optimizer'];

      const filtered = allSolverNames.filter((nm) => {
        const spec = getSolverSpec(caps, nm);
        const vrps = Object.keys(spec?.vrp_types || {});
        return vrps.length ? vrps.some(v => v.toUpperCase() === inferred) : true;
      });

      if (filtered.length) {
        setAvailableSolvers(filtered);
        setSolver(filtered.includes('ortools') ? 'ortools' : filtered[0]);
      } else {
        setAvailableSolvers(allSolverNames);
      }

      // mini-summary meta
      const bestKm = data?.best_known_km ?? data?.meta?.best_known_km ?? null;
      setLoadedMeta({ dataset, name: stem, vrpType: inferred, bestKm, format: data?.meta?.format || null, planar });

      // remember loader info
      const maybeBest =
        Number(data?.meta?.best_known ?? data?.meta?.bks ?? data?.meta?.opt ?? data?.meta?.objective) ||
        Number(payload?.solution?.objective ?? payload?.solution?.obj) || null;

      loadedRef.current = {
        dataset, name: stem,
        bestKnown: Number.isFinite(maybeBest) && maybeBest > 0 ? Number(maybeBest) : null,
        matrix: data?.matrix || null, // may be dataset-provided (TRUST AS-IS)
        depotIndex: Number.isFinite(data?.depot_index) ? Number(data.depot_index) : 0,
        format: data?.meta?.format || null,
        planar
      };

      // fetch pair for best-known in meters
      try {
        const pair = await api.get('/benchmarks/find', { params: { dataset, name: stem } }).then(r => r.data);
        const b = Number(
          pair?.solution?.objective ??
          pair?.solution?.obj ??
          pair?.solution?.best ??
          NaN
        );
        if (Number.isFinite(b) && b > 0) {
          loadedRef.current.bestKnown = b;
          setLoadedMeta(prev => ({ ...(prev || {}), bestKm: b / 1000 }));
        }
      } catch { /* ignore */ }
    } catch (e) {
      console.error('[Benchmark] Failed to load benchmark instance', e);
      alert(e?.message || 'Load failed');
    }
  };

  const clearLoaded = () => {
    if (currentFileId) {
      removeWaypointsByFileId?.(currentFileId);
      setCurrentFileId(null);
    }
    loadedRef.current = null;
    lastMiniRef.current = null;
    setPlanarDetected(false);
    setLastDebugBundleText('');
  };

  const onSolveLoaded = async () => {
    try {
      setBusy(true);
      const st = useWaypointStore.getState();
      const waypoints = st.waypoints || [];
      if (waypoints.length < 2) throw new Error('Add or load at least 2 waypoints');

      const coordsLL = waypoints.map(w => w.coordinates);
      const depotIndex = Number.isFinite(loadedRef.current?.depotIndex) ? loadedRef.current.depotIndex : 0;

      // vehicles → ensure >=10 for Solomon-like data
      const { vehicles: backendVehicles } = normalizeFleetForBackend(
        useFleetStore.getState().vehicles,
        { defaultStart: depotIndex, defaultEnd: depotIndex }
      );
      let vehiclesArr = backendVehicles?.length ? backendVehicles : [];
      if (vehiclesArr.length < 2) {
        const k = Math.min(25, Math.max(10, Math.ceil((waypoints.length - 1) / 10)));
        const base = vehiclesArr[0] || { id: 'veh-1', capacity: [200], start: depotIndex, end: depotIndex };
        vehiclesArr = Array.from({ length: k }, (_, i) => ({
          ...base,
          id: `veh-${i + 1}`,
          start: depotIndex,
          end: depotIndex,
          capacity: Array.isArray(base.capacity) && base.capacity.length ? base.capacity : [200],
        }));
      }
      const inferred = inferVrpType(waypoints, vehiclesArr);
      setVrpType(inferred);

      const selectedSolver = (solver || 'ortools').toLowerCase();
      const selectedAdapter = (adapter || 'haversine').toLowerCase();
      const selectedVrpType = inferred;

      // --- MATRIX (keep units CONSISTENT: SECONDS for durations, METERS for distances) ---
      let matrix = loadedRef.current?.matrix || null;
      let matrixSource = matrix ? 'dataset' : null;

      if (!matrix) {
        const isPlanar = (loadedRef.current?.planar === true) || planarDetected;
        if (isPlanar || selectedAdapter === 'euclidean (local)') {
          const xy = waypoints.map(w => (Number.isFinite(w.x) && Number.isFinite(w.y)) ? [w.x, w.y] : w.coordinates);
          matrix = buildEuclideanMatrix(xy, { durationsAs: 'seconds', speedKph: 60 }); // ← seconds!
          matrixSource = 'euclideanMatrix';
        } else {
          // adapter call (fallback when not planar)
          let dmPayload =
            selectedAdapter === 'osm_graph'
              ? {
                adapter: selectedAdapter,
                mode: 'driving',
                parameters: { metrics: ['distance', 'duration'], units: 'm' },
                coordinates: coordsLL.map(([lon, lat]) => ({ lon, lat }))
              }
              : {
                adapter: selectedAdapter,
                mode: 'driving',
                parameters: { metrics: ['distance', 'duration'], units: 'm' },
                origins: coordsLL.map(([lon, lat]) => ({ lon, lat })),
                destinations: coordsLL.map(([lon, lat]) => ({ lon, lat }))
              };
          console.debug('[Benchmark][MatrixSource] Payload', dmPayload);
          let dmRes;
          try {
            dmRes = await dm.mutateAsync(dmPayload);
          } catch (err) {
            const msg = String(err?.message || '');
            if (msg.includes('6004') || /openrouteservice/i.test(msg)) {
              dmPayload = { ...dmPayload, adapter: 'haversine' };
              dmRes = await dm.mutateAsync(dmPayload);
            } else {
              throw err;
            }
          }
          matrix = dmRes?.data?.matrix || dmRes?.matrix;
          if (!matrix) throw new Error('Matrix failed');
          matrixSource = dmPayload.adapter || 'adapter';
        }
      }
      console.debug('[MatrixSource] source =', matrixSource);

      // Demands (default 1 if none present, except depot)
      const isDepot = (i) => i === depotIndex;
      const defaultDemandIfMissing = waypoints.some(w => Number(w?.demand) > 0) ? 0 : 1;
      const demands = waypoints.map((w, i) =>
        isDepot(i) ? 0 : Number.isFinite(w?.demand) ? Number(w.demand) : defaultDemandIfMissing
      );

      // Node fields (assume SECONDS end-to-end)
      let node_service_times = waypoints.map(w => Math.max(0, Math.round(Number(w?.serviceTime || 0))));
      let node_time_windows = waypoints.map(w =>
        Array.isArray(w?.timeWindow) ? w.timeWindow.map(Number) : [0, 24 * 3600]
      );

      // 👉 NEW: normalize Solomon service times using matrix scale
      const secsPerUnit = estimateSecsPerDist(matrix?.distances, matrix?.durations); // ~60 for your data
      const norm = normalizeServiceTimes(node_service_times, secsPerUnit);
      node_service_times = norm.st;
      if (norm.action !== 'none') {
        console.warn(`[Benchmark] normalized service times (${norm.action}); median ${norm.before} -> ${norm.after}; secsPerUnit=${secsPerUnit}`);
      }

      // Clamp TWs, ensure start <= end, widen depot window
      const INF = 10 ** 9;
      node_time_windows = node_time_windows.map((tw, i) => {
        let [a, b] = Array.isArray(tw) ? tw.map(Number) : [0, INF];
        if (!Number.isFinite(a)) a = 0;
        if (!Number.isFinite(b)) b = INF;
        if (b < a) b = a;
        if (i === depotIndex) { a = 0; b = INF; }
        return [Math.max(0, Math.round(a)), Math.max(0, Math.round(b))];
      });


      // Make the matrix safe (no negatives; durations at least 1 on off-diagonal)
      const n = matrix?.distances?.length || matrix?.durations?.length || 0;
      if (!n) throw new Error('Matrix empty');
      if (Array.isArray(matrix.distances)) {
        matrix.distances = matrix.distances.map((row, i) =>
          row.map((v, j) => (i === j ? 0 : Math.max(0, Number(v) || 0)))
        );
      }
      if (Array.isArray(matrix.durations)) {
        matrix.durations = matrix.durations.map((row, i) =>
          row.map((v, j) => (i === j ? 0 : Math.max(1, Math.round(Number(v) || 0))))
        );
      }

      // Ensure vehicles have capacity; default to big-enough if missing
      const totalDemand = demands.reduce((s, d) => s + (Number.isFinite(d) ? d : 0), 0);
      vehiclesArr = vehiclesArr.map(v => {
        const cap = Array.isArray(v?.capacity) ? v.capacity : [];
        const hasCap = cap.some(x => Number(x) > 0);
        return {
          ...v,
          start: (v.start ?? depotIndex),
          end: (v.end ?? depotIndex),
          capacity: hasCap ? cap : [Math.max(totalDemand, waypoints.length)]
        };
      });

      // Adapter label by matrix source
      const adapterLabel =
        matrixSource === 'euclideanMatrix' ? 'euclidean (local)' :
          matrixSource === 'dataset' ? 'dataset' :
            selectedAdapter;

      // ---------- NEW: Build + log copy-pasteable debug bundle ----------
      const debugBundle = buildDebugBundle({
        dataset: loadedRef.current?.dataset, name: loadedRef.current?.name,
        solver: selectedSolver, adapter: adapterLabel, vrpType: selectedVrpType,
        depotIndex, planarDetected: (loadedRef.current?.planar === true) || planarDetected,
        matrixSource,
        waypoints,
        vehicles: vehiclesArr,
        matrix,
        demands,
        node_service_times,
        node_time_windows,
        vehicle_time_windows: Array.from({ length: vehiclesArr.length }, () => [0, 1e9]),
      });
      const debugJSON = JSON.stringify(debugBundle, null, 2);
      setLastDebugBundleText(debugJSON);
      console.log('===== BEGIN BENCH_DEBUG =====\n' + debugJSON + '\n===== END BENCH_DEBUG =====');
      console.debug('[Benchmark][DEBUG_BUNDLE_OBJECT]', debugBundle);
      // ------------------------------------------------------------------

      // Build solver payload (SECONDS)
      const payload = {
        solver: selectedSolver,
        depot_index: depotIndex,
        fleet: vehiclesArr,
        weights: { distance: 1, time: 0 },
        matrix
      };
      if (demands.some(d => d > 0)) payload.demands = demands;
      if (selectedVrpType === 'VRPTW' || selectedVrpType === 'PDPTW') {
        payload.node_service_times = node_service_times;
        payload.node_time_windows = node_time_windows;
      }
      if (selectedVrpType === 'PDPTW') payload.demands = demands;

      // vehicle time windows: keep wide by default
      if (!payload.vehicle_time_windows) {
        payload.vehicle_time_windows = Array.from({ length: vehiclesArr.length }, () => [0, 1e9]);
      }

      console.debug('[Benchmark][Units] payload uses SECONDS time; METERS distance');
      console.debug('[Benchmark] Solver Payload', payload);
      const solveRes = await solve.mutateAsync(payload);

      // compute simple total meters from route IDs
      const ids =
        solveRes?.data?.routes?.[0]?.waypoint_ids ||
        solveRes?.routes?.[0]?.waypoint_ids || [];
      let ourMeters = 0;
      if (Array.isArray(ids) && ids.length >= 2) {
        for (let i = 1; i < ids.length; i++) {
          const a = coordsLL[Number(ids[i - 1])], b = coordsLL[Number(ids[i])];
          if (a && b) ourMeters += haversineMeters(a, b);
        }
      }

      const bench = loadedRef.current || {};
      const best = bench.bestKnown;
      const comparison = (Number.isFinite(best) && best > 0)
        ? { best, ours: ourMeters, gap: ((ourMeters - best) / best) * 100 }
        : undefined;

      addSolution(solveRes, waypoints, {
        solver: selectedSolver,
        adapter: adapterLabel,
        vrpType: selectedVrpType,
        benchmark: bench.dataset && bench.name ? { dataset: bench.dataset, name: bench.name } : undefined,
        comparison,
        bestKnownKm: Number.isFinite(bench?.bestKnown) ? (bench.bestKnown / 1000) : (loadedMeta?.bestKm ?? null),
        vehicles: vehiclesArr,
        id: `bench-${Date.now()}`,
      });

      // mini box cache
      lastMiniRef.current = {
        dataset: bench.dataset, name: bench.name,
        solver: selectedSolver, adapter: adapterLabel, vrpType: selectedVrpType,
        bestKnown: best ?? null,
        ourKm: (ourMeters / 1000),
        gap: comparison ? comparison.gap : null,
      };
    } catch (e) {
      console.error('[Benchmark] solve failed', e);
      alert(e?.message || 'Solve failed');
    } finally {
      setBusy(false);
    }
  };

  // ---- UI ----
  return (
    <Section title="🧪 Benchmark Selector">
      {/* Dataset */}
      <label className="block text-sm font-medium mb-1">Dataset</label>
      <select
        className="w-full p-1 border rounded mb-2 text-sm"
        value={dataset}
        onChange={(e) => { setDataset(e.target.value); setOffset(0); }}
      >
        {datasetOptions.map(n => <option key={n} value={n}>{n}</option>)}
      </select>

      {/* Search + paging */}
      <div className=" flex gap-2 mb-2">
        <input
          className="flex-1 p-1 border rounded text-sm"
          placeholder="🔍 Search (e.g. c101, R1, 100)"
          value={search}
          onChange={(e) => { setSearch(e.target.value); setOffset(0); }}
        />
        <select
          className="w-15 p-1 border rounded text-sm"
          value={limit}
          onChange={(e) => { setLimit(Number(e.target.value) || 50); setOffset(0); }}
        >
          {[25, 50, 100, 250].map(v => <option key={v} value={v}>{v}/pg</option>)}
        </select>
      </div>

      {/* Files list */}
      <div className="max-h-56 overflow-y-auto border rounded p-2 text-sm space-y-1">
        {filesQ.isFetching && <div className="text-xs text-gray-500">Loading…</div>}
        {filesQ.isError && <div className="text-xs text-red-600">Error: {String(filesQ.error?.message || 'failed')}</div>}
        {!filesQ.isFetching && items.length === 0 && (
          <div className="text-xs text-gray-400 italic">No matching instances</div>
        )}
        {items.map(it => (
          <div key={it.name} className="flex items-center justify-between gap-2">
            <div className="truncate">
              <span className="font-mono">{it.name}</span>
              {it.solution_path && (
                <span className="ml-2 text-[11px] px-1.5 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-200">
                  has solution
                </span>
              )}
            </div>
            <button
              onClick={() => handleLoad(it.name)}
              className="text-xs px-2 py-0.5 bg-blue-600 text-white rounded hover:bg-blue-700"
            >
              Load
            </button>
          </div>
        ))}
      </div>

      {/* Pager */}
      <div className="flex items-center justify-between mt-2 text-xs">
        <div>Page {page} / {pages} ({total} items)</div>
        <div className="flex gap-1">
          <button className="px-2 py-0.5 border rounded disabled:opacity-50" disabled={offset <= 0} onClick={() => setOffset(Math.max(0, offset - limit))}>⬅ Prev</button>
          <button className="px-2 py-0.5 border rounded disabled:opacity-50" disabled={offset + limit >= total} onClick={() => setOffset(offset + limit)}>Next ➡</button>
        </div>
      </div>

      {/* Loaded/Solve row */}
      <div className="mt-3 flex items-center justify-between">
        <div className="text-xs text-gray-100">
          {currentFileId ? 'Instance loaded.' : 'No instance loaded.'}
        </div>
        <div className="flex gap-2">
          {currentFileId && (
            <button
              onClick={onSolveLoaded}
              disabled={busy}
              className="text-xs px-2 py-0.5 bg-indigo-600 text-white rounded disabled:opacity-60"
            >
              {busy ? 'Solving…' : 'Solve loaded & compare'}
            </button>
          )}
          {currentFileId && (
            <button onClick={clearLoaded} className="text-xs px-2 py-0.5 bg-gray-600 text-white rounded">
              Clear loaded
            </button>
          )}
          {/* NEW: Copy last debug bundle */}
          {lastDebugBundleText && (
            <button
              onClick={async () => {
                try {
                  await navigator.clipboard.writeText(lastDebugBundleText);
                  alert('Debug bundle copied to clipboard ✅');
                } catch {
                  // Fallback: open a prompt for manual copy
                  window.prompt('Copy debug bundle:', lastDebugBundleText);
                }
              }}
              className="text-xs px-2 py-0.5 bg-emerald-700 text-white rounded"
              title="Copy the most recent BENCH_DEBUG JSON"
            >
              📋 Copy debug bundle
            </button>
          )}
        </div>
      </div>

      {/* Solver/Adapter */}
      <div className="mt-2 grid grid-cols-2 gap-2">
        <div>
          <label className="block text-xs font-medium mb-1">Solver</label>
          <select
            className="w-full p-1 border rounded text-sm"
            value={solver}
            onChange={e => setSolver(e.target.value)}
          >
            {(availableSolvers.length ? availableSolvers : solverOptions).map(s => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-xs font-medium mb-1">Adapter</label>
          <select
            className="w-full p-1 border rounded text-sm"
            value={adapter}
            onChange={e => setAdapter(e.target.value)}
            disabled={planarDetected}
          >
            {(adapterOptions?.length ? adapterOptions : ['haversine', 'openrouteservice', 'osm_graph', 'mapbox']).map(a => (
              <option key={a} value={a}>{a}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Mini summary */}
      {loadedMeta && (
        <div className="mt-2 text-xs p-2 rounded border bg-gray-800">
          <div><strong>Benchmark:</strong> {loadedMeta.dataset}/{loadedMeta.name}</div>
          <div><strong>Type:</strong> {loadedMeta.vrpType}</div>
          {loadedMeta.planar && <div><strong>Coords:</strong> planar (euclidean)</div>}
          {Number.isFinite(loadedMeta.bestKm) && <div><strong>Best-known:</strong> {loadedMeta.bestKm.toFixed(2)} km</div>}
        </div>
      )}
    </Section>
  );
}
