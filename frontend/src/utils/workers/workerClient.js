// components/analysis/workerClient.js
let _worker;
let _reqId = 0;
const _pending = new Map();

function getWorker() {
  if (_worker) return _worker;
  _worker = new Worker(new URL('@/utils/workers/geojsonWorker.js', import.meta.url), { type: 'module' });
  _worker.onmessage = (e) => {
    const { id, ok, data, error } = e.data || {};
    const p = _pending.get(id);
    if (!p) return;
    _pending.delete(id);
    ok ? p.resolve(data) : p.reject(new Error(error || 'worker error'));
  };
  return _worker;
}

function callWorker(action, payload) {
  const w = getWorker();
  const id = ++_reqId;
  return new Promise((resolve, reject) => {
    _pending.set(id, { resolve, reject });
    w.postMessage({ id, action, payload });
  });
}

// --- helpers ---
function coordsToFC(coords) {
  return { type: 'FeatureCollection', features: [
    { type: 'Feature', properties: {}, geometry: { type: 'LineString', coordinates: coords } }
  ]};
}
function fcToLineCoords(fc) {
  const geom = fc?.features?.[0]?.geometry;
  return Array.isArray(geom?.coordinates) ? geom.coordinates : [];
}
// crude meters→degrees conversion at a given latitude
function metersToDegrees(m, lat) {
  const latRad = (lat ?? 0) * Math.PI/180;
  const metersPerDeg = 111320 * Math.cos(latRad || 0);
  return m / (metersPerDeg || 111320);
}

// --- public API used by RouteToolsPanel ---
export async function simplify(coords, toleranceMeters = 50) {
  if (!Array.isArray(coords) || coords.length < 2) return coords || [];
  const approxDeg = metersToDegrees(toleranceMeters, coords[0]?.[1]);
  const fc = coordsToFC(coords);
  const outFC = await callWorker('simplify', { fc, tolerance: approxDeg });
  return fcToLineCoords(outFC);
}

export async function bboxOfCoords(coords) {
  if (!Array.isArray(coords) || coords.length < 2) return null;
  const fc = coordsToFC(coords);
  // Returns [minX, minY, maxX, maxY]
  const b = await callWorker('bbox', { fc });
  if (!Array.isArray(b) || b.length !== 4) return null;
  return { west: b[0], south: b[1], east: b[2], north: b[3] };
}

// simple downsample in main thread (fast, avoids changing your worker)
export function downsampleEveryN(coords, step = 8) {
  if (!Array.isArray(coords) || coords.length <= step) return coords || [];
  const out = [];
  for (let i = 0; i < coords.length; i += Math.max(1, step)) out.push(coords[i]);
  if (out[out.length - 1] !== coords[coords.length - 1]) out.push(coords[coords.length - 1]);
  return out;
}
