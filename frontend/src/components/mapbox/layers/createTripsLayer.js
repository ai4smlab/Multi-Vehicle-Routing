// components/mapbox/layers/createTripsLayer.js
import { TripsLayer } from '@deck.gl/geo-layers';

export function createTripsLayer({ id, trips, currentTime, trailLength = 600 }) {
  return new TripsLayer({
    id,
    data: trips,
    // IMPORTANT: return *2D* positions here, not [lng,lat,t]
    getPath: d => d.path.map(p => [p[0], p[1]]),
    // Supply times separately:
    getTimestamps: d => d.path.map(p => p[2]),
    getColor: d => d.color || [66, 135, 245],
    widthMinPixels: 6,
    opacity: 1,
    rounded: true,
    capRounded: true,
    jointRounded: true,
    trailLength,          // seconds
    currentTime,          // seconds
    parameters: { depthTest: false }
  });
}
