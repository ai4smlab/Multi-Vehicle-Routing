// quick haversine
function haversine([lon1, lat1], [lon2, lat2]) {
  const R = 6371000, toRad = d => d * Math.PI / 180;
  const dφ = toRad(lat2 - lat1), dλ = toRad(lon2 - lon1);
  const a = Math.sin(dφ/2)**2 + Math.cos(toRad(lat1))*Math.cos(toRad(lat2))*Math.sin(dλ/2)**2;
  return 2 * R * Math.asin(Math.sqrt(a));
}
export function pathMeters(coords = []) {
  let m = 0;
  for (let i = 1; i < coords.length; i++) m += haversine(coords[i - 1], coords[i]);
  return m;
}

// derive our objective from result; fall back to meters
export function ourObjectiveMeters(solveRes, coords) {
  // common shapes you may have
  const cand = solveRes?.summary?.distance ?? solveRes?.objective ?? solveRes?.distance ?? null;
  if (Number.isFinite(cand)) return Number(cand);
  return pathMeters(coords || []);
}

export function compareAgainstBenchmark(solveRes, coords, bench) {
  if (!bench?.solution) return null;
  const best =
    bench.solution.objective ??
    bench.solution.distance ??
    bench.solution.total_distance ??
    null;
  if (!Number.isFinite(best)) return null;

  const ours = ourObjectiveMeters(solveRes, coords);
  if (!Number.isFinite(ours) || ours <= 0) return null;

  const gap = ((ours - best) / best) * 100;
  return { ours, best, gap }; // meters / meters / %
}
