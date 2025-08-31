// utils/metrics.ts
export function haversineMeters(a: number[], b: number[]) {
  const R = 6371000;
  const toRad = (d: number) => d * Math.PI / 180;
  const [lon1, lat1] = a; const [lon2, lat2] = b;
  const dLat = toRad(lat2 - lat1), dLon = toRad(lon2 - lon1);
  const u = Math.sin(dLat/2), v = Math.sin(dLon/2);
  const x = u*u + Math.cos(toRad(lat1))*Math.cos(toRad(lat2))*v*v;
  return 2*R*Math.asin(Math.sqrt(Math.max(0, x)));
}

export function polylineDistanceMeters(coords: number[][] | null | undefined) {
  if (!Array.isArray(coords) || coords.length < 2) return 0;
  let s = 0;
  for (let i=1;i<coords.length;i++) s += haversineMeters(coords[i-1], coords[i]);
  return s;
}

// Prefer solver-provided meters; otherwise recompute from geometry
export function safeDistanceMeters(r: any): number {
  const d = Number(r?.total_distance);
  if (Number.isFinite(d) && d > 100) return d; // clearly meters (>=100m)
  const coords =
    r?.geometry?.coordinates ??
    r?.displayCoords ??
    r?.coords ??
    null;
  const s = polylineDistanceMeters(coords);
  // If solver gave something tiny (e.g., degrees or km), prefer geometry sum when available
  if (s > 0) return s;
  // Last resort: treat small numeric values as km (common mistake) and convert
  if (Number.isFinite(d) && d > 0 && d < 100) return d * 1000;
  return 0;
}

export function sumRouteTotals(routes: any[]) {
  let distM = 0, durS = 0, emissions = 0, eHas = false;
  const vehicles = new Set<string>();
  for (const r of routes || []) {
    distM += safeDistanceMeters(r);
    const dur = Number(r?.total_duration);
    if (Number.isFinite(dur)) durS += dur;
    const e = Number(r?.emissions);
    if (Number.isFinite(e)) { emissions += e; eHas = true; }
    if (r?.vehicle_id != null) vehicles.add(String(r.vehicle_id));
  }
  return {
    distanceKm: distM / 1000,
    durationMin: durS / 60,
    emissions: eHas ? emissions : null,
    vehiclesUsed: vehicles.size,
  };
}

export function computeGapPct(bestKm: number | null, ourKm: number | null) {
  if (!Number.isFinite(bestKm as number) || !Number.isFinite(ourKm as number)) return null;
  if (!bestKm || bestKm <= 0) return null;
  return ((ourKm! - bestKm!) / bestKm!) * 100;
}
