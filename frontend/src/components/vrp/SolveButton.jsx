// src/components/SolveButton.js
'use client';
import { useMemo } from 'react';
import useWaypointStore from '@/hooks/useWaypointStore';
import useFleetStore from '@/hooks/useFleetStore';
import useRouteStore from '@/hooks/useRouteStore';
import useUiStore from '@/hooks/useUIStore';
import { normalizeFleetForBackend } from '@/utils/normalizeFleetForBackend';
import { useDistanceMatrix, useSolve } from '@/hooks/useBackend';
import api from '@/api/api';
import { optimize as mbxOptimize } from '@/api/mapboxProxy';
import { compareAgainstBenchmark } from '@/utils/vrpCompare';
import { fixMatrixUnitsAndDurations, normalizeTimeWindowsForVroom } from '@/utils/vrpMatrixFixes';

/** Build pickup/delivery pairs from waypoints (indices into matrix order). */
function buildPickupDeliveryPairs(waypoints, depotIndex = 0) {
  const byId = new Map();
  waypoints.forEach((w, idx) => {
    if (idx === depotIndex) return;
    const pid = w.pairId ?? w.pair_id;
    if (pid == null) return;
    const role = String(w.type ?? '').toLowerCase();
    const rec = byId.get(pid) || {};
    if (role === 'pickup') rec.pickup = idx;
    if (role === 'delivery') rec.delivery = idx;
    byId.set(pid, rec);
  });
  return [...byId.values()]
    .filter(p => Number.isInteger(p.pickup) && Number.isInteger(p.delivery))
    .map(p => ({ pickup: p.pickup, delivery: p.delivery, quantity: 1 }));
}

/** Ensure durations exist if backend needs them (derive from distance @ ~50km/h). */
function ensureDurations(matrix) {
  if (matrix?.durations) return matrix;
  const distances = matrix?.distances || [];
  const avgMps = 13.9; // ~50 km/h
  const durations = distances.map(row => row.map(d => Math.round(Number(d || 0) / avgMps)));
  return { ...matrix, durations };
}

/** VROOM expects a dict time_window {start,end} (seconds).
 *  Accepts: [a,b] (hours or seconds) or {start,end} already.
 *  Heuristic: if both ends <= 48, treat as HOURS; else assume seconds.
 */
function toVroomTimeWindow(tw) {
  if (!tw) return undefined;
  if (Array.isArray(tw) && tw.length === 2) {
    let [a, b] = tw.map(Number);
    if (Number.isFinite(a) && Number.isFinite(b)) {
      if (a <= 48 && b <= 48 && a >= 0 && b >= 0) { // looks like hours
        a *= 3600;
        b *= 3600;
      }
      return { start: Math.max(0, Math.round(a)), end: Math.max(0, Math.round(b)) };
    }
    return undefined;
  }
  if (typeof tw === 'object' && tw.start != null && tw.end != null) {
    // Normalize to ints
    let a = Number(tw.start), b = Number(tw.end);
    if (a <= 48 && b <= 48 && a >= 0 && b >= 0) { a *= 3600; b *= 3600; }
    return { start: Math.max(0, Math.round(a)), end: Math.max(0, Math.round(b)) };
  }
  return undefined;
}

/** VROOM wants "service" in seconds (some backends also accept service_time).
 *  If the waypoint has serviceTime in minutes/hours, convert as needed here.
 *  We’ll assume `serviceTime` is **seconds** already unless it’s very small (< 60),
 *  in which case treat it as MINUTES and convert to seconds for safety.
 */
function toVroomServiceSeconds(svc) {
  const x = Number(svc || 0);
  if (!Number.isFinite(x) || x <= 0) return 0;
  // Heuristic: values < 60 are probably minutes from UI; convert to seconds.
  return x < 60 ? Math.round(x * 60) : Math.round(x);
}

export default function SolveButton({ solver, adapter, vrpType }) {
  const waypoints = useWaypointStore(s => s.waypoints);
  const vehicles = useFleetStore(s => s.vehicles);

  const dm = useDistanceMatrix(); // POST /distance-matrix
  const solve = useSolve();       // POST /solver (ortools/pyomo/vroom)

  // Read selections (props override UI store)
  const selectedSolver = (solver ?? useUiStore.getState().solverEngine ?? 'ortools').toLowerCase();
  const selectedAdapter = (adapter ?? useUiStore.getState().routingAdapter ?? 'haversine').toLowerCase();
  const selectedVrpType = (vrpType ?? useUiStore.getState().vrpType ?? 'TSP').toUpperCase();

  // Coordinates in matrix order
  const coords = useMemo(
    () =>
      (waypoints || [])
        .map(w => {
          const [lng, lat] = w.coordinates || [];
          return { lat: Number(lat), lon: Number(lng) };
        })
        .filter(p => Number.isFinite(p.lat) && Number.isFinite(p.lon)),
    [waypoints]
  );

  const n = coords.length;
  const depotIndex = Math.max(0, waypoints.findIndex(w => (w.type || '').toLowerCase() === 'depot'));

  // Per-node defaults (kept simple)
  const demands = Array.from({ length: n }, (_, i) => (i === depotIndex ? 0 : 1));
  const node_service_times = Array.from({ length: n }, () => 10);
  const node_time_windows = Array.from({ length: n }, () => [0, 24 * 3600]);

  // Vehicles → backend shape
  const { vehicles: backendVehicles } = normalizeFleetForBackend(vehicles, {
    defaultStart: depotIndex,
    defaultEnd: depotIndex,
  });
  const totalDemand = demands.reduce((a, b) => a + b, 0);
  const vehiclesArr =
    backendVehicles?.length
      ? backendVehicles
      : [{ id: 'veh-1', capacity: [Math.max(1, totalDemand)], start: depotIndex, end: depotIndex }];

  // ─────────────────────────────────────────────────────────────────────────────
  // Mapbox optimize helper with 404 fallback (older backends)
  // ─────────────────────────────────────────────────────────────────────────────
  // Mapbox optimize goes through our proxy which already hits the backend baseURL (8000)
  async function callMapboxOptimize(payload) {
    return await mbxOptimize(payload); // throws normalized Error from api interceptor on 4xx/5xx
  }

  const onSolve = async () => {
    try {
      if (coords.length < 2) throw new Error('Add at least 2 waypoints');

      /* ──────────────────────────────────────────
         MAPBOX OPTIMIZER → /mapbox/optimize (proxy) → /route/geometry
         - Call optimize to get order/distance/duration
         - Call route/geometry to get a GeoJSON LineString
         - Normalize to solver-style result so map/summary/index work
         ────────────────────────────────────────── */
      if (selectedSolver === 'mapbox_optimizer') {
        const coordinates = coords.map(c => ({ lon: c.lon, lat: c.lat }));
        const mbxPayload = {
          profile: 'driving',
          coordinates,
          roundtrip: true,
          source: 'first',
          destination: 'last',
        };

        if (typeof window !== 'undefined' && window.__E2E__) {
          window.__lastSolvePayload = { endpoint: '/mapbox/optimize', payload: mbxPayload };
        }
        console.debug('[Solver] MAPBOX OPTIMIZER Payload: ', mbxPayload)
        // 1) optimize
        const optRes = await callMapboxOptimize(mbxPayload);
        const trip = optRes?.trips?.[0];
        console.debug('[Solver] MAPBOX OPTIMIZER Response: ', optRes)

        // derive order
        const order = Array.isArray(trip?.waypoint_order)
          ? trip.waypoint_order.slice()
          : (Array.isArray(optRes?.waypoints)
            ? optRes.waypoints
              .map((w, i) => ({ i, k: w?.waypoint_index }))
              .filter(x => Number.isInteger(x.k))
              .sort((a, b) => a.k - b.k)
              .map(x => x.i)
            : [...coordinates.keys()]);

        const orderedCoords = order.map(i => coordinates[i]);

        // 2) geometry
        const geomResp = await api.post('/route/geometry', {
          coordinates: orderedCoords,
          profile: 'driving',
          provider: 'mapbox',
          geometries: 'geojson',
          tidy: true,
        });
        const geometry = geomResp?.data?.data?.geometry || geomResp?.data?.geometry;

        // 3) normalize to solver-like envelope
        const normalized = {
          status: 'success',
          data: {
            routes: [
              {
                id: `mbx-${Date.now()}`,
                vehicle_id: String(vehiclesArr?.[0]?.id ?? 'veh-1'),
                total_distance: Math.round(Number(trip?.distance ?? 0)),
                total_duration: Math.round(Number(trip?.duration ?? 0)),
                geometry,           // GeoJSON LineString
                waypoint_ids: order // indices in original list
              }
            ]
          }
        };

        const addSolution = useRouteStore.getState().addSolutionFromSolver;
        const currentWaypoints = useWaypointStore.getState().waypoints;
        const bench = useRouteStore.getState().benchmarkRef || null;

        // comparison uses geometry if available, else waypoint coords
        const coordsForCompare =
          (geometry?.coordinates && Array.isArray(geometry.coordinates) && geometry.coordinates) ||
          (currentWaypoints || []).map(w => w.coordinates);

        const comparison = compareAgainstBenchmark(normalized, coordsForCompare, bench);

        addSolution(normalized, currentWaypoints, {
          solver: selectedSolver,
          adapter: selectedAdapter,
          vrpType: selectedVrpType,
          id: `run-${Date.now()}`,
          benchmark: bench,
          comparison
        });
        return;
      }


      /* ──────────────────────────────────────────
         VROOM → /solver (coordinate mode; demand must be a LIST)
         ────────────────────────────────────────── */
      if (selectedSolver === 'vroom') {
        const vroomWp = (waypoints || []).map((w, i) => ({
          id: String(w.id ?? i),
          location: {
            lat: Number(w.coordinates?.[1]),
            lon: Number(w.coordinates?.[0]),
          },
          demand: Number.isFinite(w?.demand) ? [Number(w.demand)] : undefined, // VROOM wants list
          service: toVroomServiceSeconds(w?.serviceTime), // <-- use "service" in seconds
          time_window: toVroomTimeWindow(w?.timeWindow),  // <-- dict {start,end} in seconds
        }));

        const vroomPayload = {
          solver: 'vroom',
          depot_index: depotIndex,
          waypoints: vroomWp,
          fleet: { vehicles: vehiclesArr },
          weights: { distance: 1, time: 0 },
        };
        if (typeof window !== 'undefined' && window.__E2E__) {
          window.__lastSolvePayload = { endpoint: '/solver', payload: vroomPayload };
        }
        console.debug('[Solver] VROOM Payload: ', vroomPayload)

        let solveRes;
        try {
          solveRes = await solve.mutateAsync(vroomPayload);
        } catch (err) {
          const msg = String(err?.message || '');
          // Friendlier diagnosis for time windows / service fields
          if (/time_window.*valid dictionary|time_window.*object/i.test(msg)) {
            throw new Error(
              "VROOM expects time_window as an object {start,end} in seconds. " +
              "We now convert [h1,h2] → {start:h1*3600, end:h2*3600}. " +
              "If your waypoints carry different units, please ensure they’re seconds."
            );
          }
          if (/service/i.test(msg) && /seconds/i.test(msg)) {
            throw new Error(
              "VROOM expects 'service' in seconds per job. " +
              "We convert small values (<60) from minutes → seconds."
            );
          }
          throw err;
        }
        console.debug('[Solver] VROOM Response: ', solveRes)

        const currentWaypoints = useWaypointStore.getState().waypoints;
        const addSolution = useRouteStore.getState().addSolutionFromSolver;
        const bench = useRouteStore.getState().benchmarkRef || null;

        const r0 =
          (solveRes?.data?.routes && solveRes.data.routes[0]) ||
          (solveRes?.routes && solveRes.routes[0]) || null;

        const shape =
          (Array.isArray(r0?.shape) && r0.shape) ||
          (Array.isArray(solveRes?.shape) && solveRes.shape) ||
          null;

        const coordsForCompare =
          shape ||
          (Array.isArray(solveRes?.coords) && solveRes.coords) ||
          (currentWaypoints || []).map(w => w.coordinates);

        const comparison = compareAgainstBenchmark(solveRes, coordsForCompare, bench);

        addSolution(solveRes, currentWaypoints, {
          solver: selectedSolver,
          adapter: selectedAdapter,
          vrpType: selectedVrpType,
          id: `run-${Date.now()}`,
          benchmark: bench,
          comparison
        });
        return;
      }


      /* ──────────────────────────────────────────
         ORTOOLS / PYOMO → /distance-matrix then /solver
         Adapter-aware payload:
         - osm_graph   → {coordinates:[{lon,lat},...]}
         - everything else (mapbox/ors/google/haversine) → {origins, destinations}
         ────────────────────────────────────────── */
      const makeDmPayload = (adapterName) => {
        const base = {
          adapter: adapterName,
          mode: 'driving',
          parameters: { metrics: ['distance', 'duration'], units: 'm' },
        };
        if (adapterName === 'osm_graph') {
          return { ...base, coordinates: coords };
        }
        return { ...base, origins: coords, destinations: coords };
      };

      let dmPayload = makeDmPayload(selectedAdapter);
      console.debug('[Solver] (ORTOOLS / PYOMO) Matrix Payload: ', dmPayload);
      let dmRes;
      try {
        dmRes = await dm.mutateAsync(dmPayload);
      } catch (err) {
        const msg = String(err?.message || '');
        // ORS limit / server errors → fall back to haversine
        if (msg.includes('6004') || /openrouteservice/i.test(msg)) {
          dmPayload = makeDmPayload('haversine');
          alert('OpenRouteService limit hit or failed; falling back to Haversine.');
          dmRes = await dm.mutateAsync(dmPayload);
        } else {
          throw err;
        }
      }
      console.debug('[Solver] (ORTOOLS / PYOMO) Matrix Response: ', dmRes);
      let matrixRaw = dmRes?.data?.matrix || dmRes?.matrix;
      if (!matrixRaw?.distances && !matrixRaw?.durations) {
        throw new Error('Distance matrix missing distances/durations');
      }

      // 1) copy as floats (NO rounding yet)
      const matrix = {
        ...(Array.isArray(matrixRaw?.distances)
          ? { distances: matrixRaw.distances.map(r => r.map(v => Number(v || 0))) }
          : {}),
        ...(Array.isArray(matrixRaw?.durations)
          ? { durations: matrixRaw.durations.map(r => r.map(v => Number(v || 0))) }
          : {}),
      };

      const demands = waypoints.map((w, i) => i === depotIndex ? 0 : Number(w?.demand || 0));
      const node_service_times = waypoints.map(w => Number(w?.serviceTime || 0));
      const node_time_windows = waypoints.map(w =>
        Array.isArray(w?.timeWindow) ? w.timeWindow : [0, 24 * 3600]
      );

      // OPTIONAL coords list aligned to matrix rows (if you have waypoints)
      const coordsLL = (waypoints || []).map(w => w.coordinates).filter(Array.isArray);

      // 🔧 Repair tiny km → meters and fill durations (BEFORE any rounding)
      fixMatrixUnitsAndDurations(matrix, coordsLL);

      // Make sure durations exist and are never zero for off-diagonals
      if (!Array.isArray(matrix.durations)) {
        // safeguard if some adapter didn’t return durations even after fix
        const avgMps = 40_000 / 3600; // 40 km/h
        matrix.durations = matrix.distances.map(row => row.map(d => d > 0 ? Math.round(d / avgMps) : 0));
      }
      // Clamp tiny off-diagonal durations to >=1s so OR-Tools doesn’t see zero time
      for (let i = 0; i < matrix.durations.length; i++) {
        for (let j = 0; j < matrix.durations[i].length; j++) {
          if (i !== j && matrix.durations[i][j] < 1) matrix.durations[i][j] = 1;
        }
      }

      const solvePayload = {
        solver: selectedSolver, // 'ortools' | 'pyomo'
        depot_index: depotIndex,
        fleet: vehiclesArr,
        weights: { distance: 1, time: 0 },
        matrix,
      };

      // If using VROOM AND you’re passing time windows as arrays, convert them:
      if (selectedSolver.toLowerCase() === 'vroom' && Array.isArray(node_time_windows)) {
        const vroomTW = normalizeTimeWindowsForVroom(node_time_windows);
        if (vroomTW) solvePayload.node_time_windows = vroomTW;
      }

      if (selectedVrpType === 'CVRP') {
        solvePayload.demands = demands;
      } else if (selectedVrpType === 'VRPTW') {
        solvePayload.node_time_windows = node_time_windows;
        solvePayload.node_service_times = node_service_times;
      } else if (selectedVrpType === 'PDPTW') {
        solvePayload.node_time_windows = node_time_windows;
        solvePayload.node_service_times = node_service_times;
        solvePayload.pickup_delivery_pairs = buildPickupDeliveryPairs(waypoints, depotIndex);
        solvePayload.demands = demands;
      }

      if (typeof window !== 'undefined' && window.__E2E__) {
        window.__lastSolvePayload = { endpoint: '/solver', payload: solvePayload };
      }
      console.debug('[Solver] (ORTOOLS / PYOMO) Payload: ', solvePayload);
      const solveRes = await solve.mutateAsync(solvePayload);
      console.debug('[Solver] (ORTOOLS / PYOMO) Response: ', solveRes);
      const addSolution = useRouteStore.getState().addSolutionFromSolver;
      const currentWaypoints = useWaypointStore.getState().waypoints;
      addSolution(solveRes, currentWaypoints, {
        solver: selectedSolver,
        adapter: selectedAdapter,
        vrpType: selectedVrpType,
        id: `run-${Date.now()}`,
      });
    } catch (e) {
      console.error('❌ solve failed', e);
      alert(e?.message || 'Solve failed');
    }
  };

  const disabled = dm.isPending || solve.isPending || waypoints.length < 2;

  return (
    <button
      data-testid="solve-btn"
      className="text-xs px-3 py-1 bg-indigo-600 text-white rounded hover:bg-indigo-700 disabled:opacity-50"
      onClick={onSolve}
      disabled={disabled}
      title={waypoints.length < 2 ? 'Add at least 2 waypoints' : 'Solve VRP'}
    >
      {dm.isPending || solve.isPending ? 'Solving…' : 'Solve'}
    </button>
  );
}
