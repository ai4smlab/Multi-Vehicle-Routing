// utils/buildPayloadFromCaps.js
import { getVrpSpec } from './capabilityHelpers';

// local haversine in meters
const R = 6371000;
const toRad = d => (d * Math.PI) / 180;
function haversineMeters(a, b) {
  const [lon1, lat1] = a, [lon2, lat2] = b;
  const dLat = toRad(lat2 - lat1), dLon = toRad(lon2 - lon1);
  const x = Math.sin(dLat/2)**2 + Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon/2)**2;
  return 2 * R * Math.asin(Math.sqrt(x));
}

function durationsFromDistances(dist, speedKph = 40) {
  if (!Array.isArray(dist)) return null;
  const mps = (speedKph * 1000) / 3600;
  return dist.map(row => row.map(d => Math.round(Number(d || 0) / mps)));
}

// --- NEW: if typical off-diagonal distance < 1, assume kilometers → convert to meters ---
function scaleSmallDistancesToMeters(payload) {
  const M = payload?.matrix?.distances;
  if (!Array.isArray(M) || !M.length) return;

  const off = [];
  for (let i = 0; i < M.length; i++) {
    for (let j = 0; j < M.length; j++) {
      if (i === j) continue;
      const v = Number(M[i][j]);
      if (Number.isFinite(v) && v > 0) off.push(v);
    }
  }
  if (!off.length) return;

  off.sort((a, b) => a - b);
  const median = off[Math.floor(off.length / 2)];
  if (median < 1) {
    // looks like kilometers; convert to meters
    for (let i = 0; i < M.length; i++) {
      for (let j = 0; j < M.length; j++) {
        M[i][j] = Number(M[i][j]) * 1000;
      }
    }
  }
}

function fixSuspiciousMatrix(payload, ctx) {
  const M = payload?.matrix?.distances;
  if (!Array.isArray(M) || !M.length) return;

  const n = M.length;
  const offDiagAllZero =
    n <= 2 &&
    M.every((row, i) => row.every((v, j) => (i === j ? v === 0 : Number(v) === 0)));

  if (offDiagAllZero) {
    // recompute off-diagonals from waypoints coords
    const coords = (ctx?.waypoints || []).map(w => w?.coordinates).filter(Array.isArray);
    if (coords.length === n) {
      for (let i = 0; i < n; i++) {
        for (let j = 0; j < n; j++) {
          if (i === j) { M[i][j] = 0; continue; }
          const meters = haversineMeters(coords[i], coords[j]);
          M[i][j] = meters;
        }
      }
    }
  }

  // --- NEW: prevent int-cast-to-zero for tiny values ---
  scaleSmallDistancesToMeters(payload);

  // fill durations if missing (now distances are meters)
  if (!payload?.matrix?.durations) {
    const dur = durationsFromDistances(payload.matrix.distances, 40);
    if (dur) payload.matrix.durations = dur;
  }
}

// Convert TW for vroom (expects {start,end}) or remove if absent
function normalizeTimeWindowsForVroom(payload, ctx) {
  const solver = String(ctx?.solver || '').toLowerCase();
  if (solver !== 'vroom') return;

  const tw = payload?.node_time_windows;
  if (!Array.isArray(tw) || tw.every(x => !x)) {
    if (payload?.node_time_windows) delete payload.node_time_windows;
    return;
  }
  payload.node_time_windows = tw.map(t =>
    (Array.isArray(t) && t.length === 2)
      ? ({ start: Number(t[0]), end: Number(t[1]) })
      : null
  );
}

/**
 * Build a /solver payload strictly from the capabilities spec (required + optional present).
 */
export function buildPayloadFromCaps(caps, ctx) {
  const { solver, vrpType } = ctx;
  const spec = getVrpSpec(caps, solver, vrpType);
  if (!spec) throw new Error(`Solver ${solver} does not support ${vrpType}`);

  const ensureFleet = () => {
    if (Array.isArray(ctx.fleet?.vehicles)) {
      if (ctx.fleet.vehicles.length >= 1) return { vehicles: ctx.fleet.vehicles };
    } else if (Array.isArray(ctx.fleet)) {
      if (ctx.fleet.length >= 1) return { vehicles: ctx.fleet };
    }
    const totalDemand = (ctx.demands || []).reduce((a,b)=>a+(b||0),0);
    return { vehicles: [{ id: 'veh-1', capacity: [Math.max(1,totalDemand)], start: ctx.depotIndex, end: ctx.depotIndex }] };
  };

  const payload = { solver, depot_index: ctx.depotIndex };
  const add = (k, v) => { if (v != null) payload[k] = v; };

  const putMatrix = (part) => {
    const curr = payload.matrix || {};
    payload.matrix = { ...curr, ...part };
  };

  const includeToken = (tok) => {
    if (tok.includes('|')) {
      const [a, b] = tok.split('|').map(s => s.trim());
      if (a === 'waypoints' && Array.isArray(ctx.waypoints) && ctx.waypoints.length) {
        includeToken('waypoints');
      } else if (b === 'matrix' && ctx.matrix) {
        if (ctx.matrix?.distances) putMatrix({ distances: ctx.matrix.distances });
        if (ctx.matrix?.durations) putMatrix({ durations: ctx.matrix.durations });
      }
      return;
    }
    switch (tok) {
      case 'matrix.distances':
        if (ctx.matrix?.distances) putMatrix({ distances: ctx.matrix.distances });
        break;
      case 'matrix.durations':
        if (ctx.matrix?.durations) putMatrix({ durations: ctx.matrix.durations });
        break;
      case 'matrix':
        if (ctx.matrix?.distances || ctx.matrix?.durations) {
          putMatrix({
            ...(ctx.matrix?.distances ? { distances: ctx.matrix.distances } : {}),
            ...(ctx.matrix?.durations ? { durations: ctx.matrix.durations } : {})
          });
        }
        break;
      case 'waypoints':
        if (Array.isArray(ctx.waypoints)) add('waypoints', ctx.waypoints);
        break;
      case 'fleet>=1':
      case 'fleet==1':
        add('fleet', ensureFleet());
        break;
      case 'demands':
        add('demands', ctx.demands);
        break;
      case 'node_time_windows':
        add('node_time_windows', ctx.node_time_windows);
        break;
      case 'node_service_times':
        add('node_service_times', ctx.node_service_times);
        break;
      case 'pickup_delivery_pairs':
        add('pickup_delivery_pairs', ctx.pickup_delivery_pairs);
        break;
      case 'weights':
        add('weights', ctx.weights);
        break;
      default:
        break;
    }
  };

  (spec.required || []).forEach(includeToken);
  (spec.optional || []).forEach(includeToken);

  // Repair/normalize after merging tokens
  fixSuspiciousMatrix(payload, ctx);
  normalizeTimeWindowsForVroom(payload, ctx);

  return payload;
}
