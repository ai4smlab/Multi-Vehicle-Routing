// src/utils/vrpMatrixFixes.js
import { deriveDurationsFromDistances } from '@/utils/euclideanMatrix';

// tiny haversine in meters
function haversineMeters([lon1, lat1], [lon2, lat2]) {
  const toRad = d => d * Math.PI / 180;
  const R = 6371000;
  const dLat = toRad(lat2 - lat1), dLon = toRad(lon2 - lon1);
  const a = Math.sin(dLat / 2) ** 2 +
            Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) *
            Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(a));
}

/**
 * Ensure matrix distances are in **meters** and durations in **seconds**.
 * Optionally uses coords (lon,lat) to detect km-vs-m scaling.
 */
export function fixMatrixUnitsAndDurations(matrix, coordsLL, opts = {}) {
  if (!matrix || !Array.isArray(matrix.distances)) return;

  // --- Detect unit scale by sampling against haversine ---
  let scale = 1;
  try {
    const n = matrix.distances.length;
    const steps = Math.max(1, Math.floor(n / 10));
    const ratios = [];
    for (let i = 0; i < n; i += steps) {
      for (let j = i + 1; j < n; j += steps) {
        const dij = Number(matrix.distances[i]?.[j] || 0);
        const a = coordsLL?.[i], b = coordsLL?.[j];
        if (!dij || !Array.isArray(a) || !Array.isArray(b)) continue;
        const hm = haversineMeters(a, b); // meters
        if (hm > 0) ratios.push(dij / hm);
        if (ratios.length >= 24) break;
      }
      if (ratios.length >= 24) break;
    }
    if (ratios.length) {
      ratios.sort((x, y) => x - y);
      const med = ratios[Math.floor(ratios.length / 2)];
      // meters → med ~ 1; kilometers → med ~ 0.001
      if (med > 0 && med < 0.01) scale = 1000;       // likely km → meters
      else scale = 1;                                 // assume meters
    }
  } catch { /* keep scale=1 */ }

  if (scale !== 1) {
    matrix.distances = matrix.distances.map((row, i) =>
      row.map((v, j) => (i === j ? 0 : Number(v || 0) * scale))
    );
  }

  // --- Ensure durations (SECONDS); derive if missing ---
  if (!Array.isArray(matrix.durations)) {
    matrix.durations = deriveDurationsFromDistances(matrix.distances, {
      speedKph: opts.speedKph ?? 50,
      as: 'seconds',
    });
  }

  // --- Clamp off-diagonal durations to >= 1s, keep diag 0 ---
  matrix.durations = matrix.durations.map((row, i) =>
    row.map((v, j) => (i === j ? 0 : Math.max(1, Math.round(Number(v) || 0))))
  );
}

/** Optional helper if you need to convert [a,b] arrays to VROOM dicts. */
export function normalizeTimeWindowsForVroom(arr) {
  if (!Array.isArray(arr)) return undefined;
  return arr.map((tw, i) => {
    let [a, b] = Array.isArray(tw) ? tw.map(Number) : [0, 1e9];
    if (!Number.isFinite(a)) a = 0;
    if (!Number.isFinite(b)) b = 1e9;
    if (b < a) b = a;
    // Heuristic: small values look like HOURS
    if (a >= 0 && b >= 0 && b <= 48) { a *= 3600; b *= 3600; }
    // Depot unconstrained if index 0
    if (i === 0) { a = 0; b = 1e9; }
    return { start: Math.round(a), end: Math.round(b) };
  });
}
