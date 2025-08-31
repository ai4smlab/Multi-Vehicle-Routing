// src/utils/routeGeometry.js
// Polyline decoder (precision 5/6) → [[lon,lat], ...]
export function decodePolyline(str, precision = 5) {
  let index = 0, lat = 0, lng = 0, coords = [];
  const factor = Math.pow(10, precision);
  while (index < str.length) {
    let b, shift = 0, result = 0;
    do { b = str.charCodeAt(index++) - 63; result |= (b & 0x1f) << shift; shift += 5; } while (b >= 0x20);
    const dlat = (result & 1) ? ~(result >> 1) : (result >> 1); lat += dlat;
    shift = 0; result = 0;
    do { b = str.charCodeAt(index++) - 63; result |= (b & 0x1f) << shift; shift += 5; } while (b >= 0x20);
    const dlng = (result & 1) ? ~(result >> 1) : (result >> 1); lng += dlng;
    coords.push([lng / factor, lat / factor]);
  }
  return coords;
}

function isLngLat(x) {
  return Array.isArray(x) && x.length >= 2 &&
    Number.isFinite(x[0]) && Number.isFinite(x[1]) &&
    x[0] >= -180 && x[0] <= 180 && x[1] >= -90 && x[1] <= 90;
}
function looksLikeCoords(arr) { return Array.isArray(arr) && arr.length >= 2 && isLngLat(arr[0]) && isLngLat(arr.at(-1)); }

export function tryDecodePolyline(str) {
  if (typeof str !== 'string' || !str.length) return null;
  const p6 = decodePolyline(str, 6); if (looksLikeCoords(p6)) return p6;
  const p5 = decodePolyline(str, 5); if (looksLikeCoords(p5)) return p5;
  return null;
}

// --- Simple LRU-ish cache + in-flight de-dupe for route geometry ---
const LRU_MAX = 40;
const _geomCache = new Map();    // key -> { ts, data }
const _inflight = new Map();     // key -> { promise, abort }

const norm = (n) => Number.isFinite(n) ? +n.toFixed(5) : n;
const sigOfCoords = (coords=[]) => coords.map(([x,y]) => `${norm(x)},${norm(y)}`).join('|');

export function makeGeomKey({ source, profile='driving', adapter='auto', coords=[] }) {
  return `${source}|${profile}|${adapter}|${sigOfCoords(coords)}`;
}

function pruneLRU() {
  if (_geomCache.size <= LRU_MAX) return;
  // delete oldest
  let oldestK=null, oldestT=Infinity;
  for (const [k, v] of _geomCache) {
    if (v.ts < oldestT) { oldestT = v.ts; oldestK = k; }
  }
  if (oldestK) _geomCache.delete(oldestK);
}

export function abortAllGeometry() {
  for (const ent of _inflight.values()) { try { ent.abort?.(); } catch {} }
  _inflight.clear();
}

/**
 * getGeometryWithCache(fetcher, opts)
 * - fetcher: async ({signal}) => coords[]  ← you already decide provider (backend/mapbox/osrm/none) in your hook
 * - opts: { source, profile, adapter, coords }
 */
export async function getGeometryWithCache(fetcher, opts) {
  const key = makeGeomKey(opts);
  if (_geomCache.has(key)) return _geomCache.get(key).data;
  if (_inflight.has(key)) return _inflight.get(key).promise;

  const ac = new AbortController();
  const promise = (async () => {
    try {
      const coords = await fetcher({ signal: ac.signal });
      _geomCache.set(key, { ts: Date.now(), data: coords || [] });
      pruneLRU();
      return coords || [];
    } finally {
      _inflight.delete(key);
    }
  })();

  _inflight.set(key, { promise, abort: () => ac.abort() });
  return promise;
}

// Try to extract coordinates from a variety of Mapbox/OSRM/ORS shapes
export function coordsFromAnyGeometry(raw) {
  if (!raw) return null;

  // GeoJSON Feature/FC
  if (raw.type === 'Feature' && raw.geometry?.coordinates) {
    const c = raw.geometry.coordinates;
    return looksLikeCoords(c) ? c : null;
  }
  if (raw.type === 'FeatureCollection' && Array.isArray(raw.features) && raw.features[0]?.geometry?.coordinates) {
    const c = raw.features[0].geometry.coordinates;
    return looksLikeCoords(c) ? c : null;
  }

  // Mapbox/OSRM responses
  if (Array.isArray(raw.routes) && raw.routes[0]) {
    const g = raw.routes[0].geometry;
    if (Array.isArray(g?.coordinates) && looksLikeCoords(g.coordinates)) return g.coordinates;
    if (typeof g === 'string') {
      const d = tryDecodePolyline(g); if (d) return d;
    }
  }

  // Generic .geometry
  if (raw.geometry) {
    if (Array.isArray(raw.geometry.coordinates) && looksLikeCoords(raw.geometry.coordinates)) return raw.geometry.coordinates;
    if (typeof raw.geometry === 'string') {
      const d = tryDecodePolyline(raw.geometry); if (d) return d;
    }
  }

  // Maybe direct coordinates
  if (Array.isArray(raw.coordinates) && looksLikeCoords(raw.coordinates)) return raw.coordinates;

  return null;
}
