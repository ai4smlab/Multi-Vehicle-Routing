// src/utils/euclideanMatrix.js

/**
 * Compute a symmetric Euclidean distance matrix (in METERS) from planar points.
 * @param {number[][]} pointsMeters - [[x,y], ...] coordinates in *meters*
 * @returns {number[][]} distances (meters)
 */
export function euclideanMatrixMeters(pointsMeters) {
  const n = Array.isArray(pointsMeters) ? pointsMeters.length : 0;
  const D = Array.from({ length: n }, () => new Array(n).fill(0));
  for (let i = 0; i < n; i++) {
    const [xi, yi] = pointsMeters[i];
    for (let j = i + 1; j < n; j++) {
      const [xj, yj] = pointsMeters[j];
      const d = Math.hypot(xj - xi, yj - yi);
      D[i][j] = D[j][i] = d;
    }
  }
  return D;
}

/**
 * Derive travel durations from a distance matrix, using a nominal speed.
 * Defaults: 40 km/h → ~11.11 m/s. Produces integer **seconds** (off-diagonal ≥ 1).
 *
 * @param {number[][]} distancesMeters - matrix in meters (square, symmetric).
 * @param {object} [opts]
 * @param {number} [opts.speedKph=40] - Nominal cruising speed in km/h.
 * @param {'seconds'|'minutes'} [opts.as='seconds'] - Output unit for durations.
 * @returns {number[][]} durations (seconds or minutes, integer, diag=0)
 */
export function deriveDurationsFromDistances(
  distancesMeters,
  opts = {}
) {
  const as = opts.as === 'minutes' ? 'minutes' : 'seconds';
  const speedKph = Number.isFinite(opts.speedKph) ? Number(opts.speedKph) : 40;
  const mps = (speedKph * 1000) / 3600;

  const n = Array.isArray(distancesMeters) ? distancesMeters.length : 0;
  const out = Array.from({ length: n }, () => new Array(n).fill(0));

  for (let i = 0; i < n; i++) {
    const row = distancesMeters[i] || [];
    for (let j = 0; j < n; j++) {
      if (i === j) { out[i][j] = 0; continue; }
      const d = Number(row[j] || 0);
      const seconds = Math.max(1, Math.round(d / mps)); // avoid 0 for off-diagonals
      out[i][j] = as === 'minutes' ? Math.max(1, Math.round(seconds / 60)) : seconds;
    }
  }
  return out;
}

/**
 * Convenience builder that returns both distances (meters) and durations
 * computed from Euclidean geometry on planar **meter** coordinates.
 *
 * @param {number[][]} pointsMeters - [[x,y], ...] in meters
 * @param {object} [opts]
 * @param {number} [opts.speedKph=40]
 * @param {'seconds'|'minutes'} [opts.durationsAs='seconds']
 * @returns {{ distances:number[][], durations:number[][] }}
 */
export function buildEuclideanMatrix(pointsMeters, opts = {}) {
  const durationsAs = opts.durationsAs === 'minutes' ? 'minutes' : 'seconds';
  const distances = euclideanMatrixMeters(pointsMeters);
  const durations = deriveDurationsFromDistances(distances, {
    speedKph: opts.speedKph ?? 40,
    as: durationsAs,
  });
  if (process?.env?.NODE_ENV !== 'production') {
    // Helpful once per call in dev builds
    // eslint-disable-next-line no-console
    console.debug('[Units] Euclidean matrix built', {
      n: distances.length,
      speedKph: opts.speedKph ?? 40,
      durationsAs,
    });
  }
  return { distances, durations };
}
