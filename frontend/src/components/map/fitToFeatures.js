// components/map/fitToFeatures.js
'use client';

import { WebMercatorViewport } from '@math.gl/web-mercator';
import useMapStore from '@/hooks/useMapStore';

/**
 * Fit the map to given data.
 * @param {Feature[]|FeatureCollection|Feature|[number, number]} input
 * @param {{ setViewState?: Function, padding?: number, duration?: number }} opts
 */
export default function fitToFeatures(input, opts = {}) {
  const { setViewState, padding = 60, duration = 800 } = opts;

  const boundsObj = computeBounds(input);
  if (!boundsObj){
    // Debugging info
    console.debug('[fitToFeatures] no bounds from input', input);
    return;
  }

  const { west, south, east, north } = boundsObj;

  // Legacy path: caller provided setViewState → compute camera and set directly
  if (typeof setViewState === 'function') {
    // Debugging info
    console.debug('[fitToFeatures] legacy setViewState path', { west, south, east, north, padding });
    // Guard in case this gets called before window exists (SSR)
    if (typeof window === 'undefined') return;
    const width = window.innerWidth || 1280;
    const height = window.innerHeight || 720;

    const viewport = new WebMercatorViewport({ width, height });
    const { longitude, latitude, zoom } = viewport.fitBounds(
      [
        [west, south],
        [east, north],
      ],
      { padding }
    );

    setViewState({
      longitude,
      latitude,
      zoom,
      pitch: 0,
      bearing: 0,
    });
    return;
  }
  // Debugging info
  console.debug('[fitToFeatures] issuing cameraCommand: fitBounds', { west, south, east, north, padding, duration });
  // New path: emit a camera command so the map component (Mapbox/MapLibre) can run fitBounds imperatively
  try {
    useMapStore.getState().issueCameraCommand?.({
      type: 'fitBounds',
      west,
      south,
      east,
      north,
      padding,
      duration,
    });
  } catch (e) {
    // Fallback no-op if store not ready
    console.debug('fitToFeatures: issueCameraCommand unavailable, skipping.', e);
  }
}

// ------------------------ helpers ------------------------

function computeBounds(input) {
  if (!input) return null;

  // Single [lng, lat] pair
  if (Array.isArray(input) && input.length === 2 && isFinite(input[0]) && isFinite(input[1])) {
    const [lng, lat] = input;
    const delta = 0.005; // ~500m
    return {
      west: lng - delta,
      south: lat - delta,
      east: lng + delta,
      north: lat + delta,
    };
  }

  // FeatureCollection
  if (input?.type === 'FeatureCollection' && Array.isArray(input.features)) {
    return boundsFromFeatures(input.features);
  }

  // Single Feature
  if (input?.type === 'Feature' && input.geometry) {
    return boundsFromFeatures([input]);
  }

  // Array of Features
  if (Array.isArray(input)) {
    // Could be an array of Features
    if (input.length && input[0]?.type === 'Feature') {
      return boundsFromFeatures(input);
    }
    // Or an array-like of coordinates already (rare)
  }

  return null;
}

function boundsFromFeatures(features) {
  let west = Infinity,
    south = Infinity,
    east = -Infinity,
    north = -Infinity;

  const extend = (coord) => {
    if (!Array.isArray(coord) || coord.length < 2) return;
    const [lng, lat] = coord;
    if (!isFinite(lng) || !isFinite(lat)) return;
    west = Math.min(west, lng);
    east = Math.max(east, lng);
    south = Math.min(south, lat);
    north = Math.max(north, lat);
  };

  features.forEach((f) => {
    const g = f?.geometry;
    if (!g) return;

    if (g.type === 'Point') {
      extend(g.coordinates);
    } else if (g.type === 'MultiPoint' || g.type === 'LineString') {
      g.coordinates.forEach(extend);
    } else if (g.type === 'MultiLineString' || g.type === 'Polygon') {
      g.coordinates.flat().forEach(extend);
    } else if (g.type === 'MultiPolygon') {
      g.coordinates.flat(2).forEach(extend);
    }
  });

  if (![west, south, east, north].every(isFinite)) return null;
  return { west, south, east, north };
}
