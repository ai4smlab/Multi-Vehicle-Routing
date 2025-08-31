// src/utils/coords.ts
export type LatLon = { lat: number; lon: number };

export function toLonLatArray(points: LatLon[]): [number, number][] {
  return points.map((p) => [Number(p.lon), Number(p.lat)]);
}

export function toLonLatObjects(points: LatLon[]) {
  return points.map((p) => ({ lon: Number(p.lon), lat: Number(p.lat) }));
}

export function mirrorDestinations<T>(origins: T[], destinations?: T[]) {
  return destinations && destinations.length ? destinations : origins;
}
