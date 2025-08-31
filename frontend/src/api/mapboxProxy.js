// src/api/mapboxProxy.js
import api from '@/api/api';

// Small helper to unwrap data and throw friendly errors (api.js already normalizes errors)
async function unwrap(promise) {
  const res = await promise;
  return res.data;
}

// ---------- Geocoding family ----------
export function suggest(params) {
  // GET /mapbox/suggest?q=...&limit=...&proximity=...&bbox=...
  return unwrap(api.get('/mapbox/suggest', { params }));
}

export function forward(body) {
  // POST /mapbox/forward { q, limit, language, proximity, bbox, country, ... }
  return unwrap(api.post('/mapbox/forward', body));
}

export function retrieve(body) {
  // POST /mapbox/retrieve { id, session_token, ... }
  return unwrap(api.post('/mapbox/retrieve', body));
}

export function reverse(body) {
  // POST /mapbox/reverse { longitude, latitude, ... }
  return unwrap(api.post('/mapbox/reverse', body));
}

export function categorySearch(body) {
  // POST /mapbox/category { category, proximity, bbox, ... }
  return unwrap(api.post('/mapbox/category', body));
}

// ---------- Routing family ----------
export function matrix(body) {
  // POST /mapbox/matrix { coordinates:[{lon,lat},...], profile?, ... }
  return unwrap(api.post('/mapbox/matrix', body));
}

export function optimize(body) {
  // POST /mapbox/optimize { coordinates:[...], profile?, ... }
  return unwrap(api.post('/mapbox/optimize', body));
}

export function match(body) {
  // POST /mapbox/match { coordinates:[...], profile?, geometries?, tidy?, ... }
  return unwrap(api.post('/mapbox/match', body));
}
