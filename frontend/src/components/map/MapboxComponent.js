// components/map/MapboxComponent.js
'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import MapGL from 'react-map-gl/mapbox';
import mapboxgl from 'mapbox-gl';
import 'mapbox-gl/dist/mapbox-gl.css';

import { ScatterplotLayer, GeoJsonLayer, PathLayer, TextLayer } from '@deck.gl/layers';
import { EditableGeoJsonLayer, DrawRectangleMode } from '@deck.gl-community/editable-layers';
import { MapboxOverlay } from '@deck.gl/mapbox';

import useMapStore from '@/hooks/useMapStore';
import useVrpStore from '@/hooks/useVRPStore';
import useWaypointStore from '@/hooks/useWaypointStore';
import useUiStore from '@/hooks/useUIStore';
import useRouteStore from '@/hooks/useRouteStore';
import useRenderSettingsStore from '@/hooks/useRenderSettingsStore';
import { useRouteGeometry } from '@/hooks/useRouteGeometry';

import { addClusteredSource } from '@/components/mapbox/layers/addClusteredSource';
import { addTrafficLine } from '@/components/mapbox/layers/addTrafficLine';
import { createTripsLayer } from '@/components/mapbox/layers/createTripsLayer';
import { createLassoLayer } from '@/components/mapbox/layers/createLassoLayer';
import { createEtaController } from '@/components/mapbox/layers/etaLayer';

mapboxgl.accessToken = process.env.NEXT_PUBLIC_MAPBOX_TOKEN || '';
const MAP_STYLE = 'mapbox://styles/mapbox/navigation-night-v1';

// ───────── helpers (shared with MapLibre) ─────────
function haversineMeters([lon1, lat1], [lon2, lat2]) {
  const R = 6371000;
  const toRad = (d) => (d * Math.PI) / 180;
  const dLat = toRad(lat2 - lat1);
  const dLon = toRad(lon2 - lon1);
  const a = Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(a));
}
function relativeTimestampsFromCoords(coords, speedKmh = 50) {
  const mps = (speedKmh * 1000) / 3600;
  const ts = [0];
  for (let i = 1; i < coords.length; i++) {
    const dt = haversineMeters(coords[i - 1], coords[i]) / mps;
    ts.push(ts[i - 1] + dt);
  }
  return ts;
}
function speedToHex(kmh) {
  if (kmh <= 10) return '#d73027';
  if (kmh <= 25) return '#fc8d59';
  if (kmh <= 45) return '#fee08b';
  if (kmh <= 70) return '#d9ef8b';
  return '#1a9850';
}
function buildGradientStops(coords, relSeconds, maxStops = 16) {
  if (!Array.isArray(coords) || !Array.isArray(relSeconds)) return null;
  if (coords.length < 2 || coords.length !== relSeconds.length) return null;

  const cum = new Array(coords.length).fill(0);
  let total = 0;
  for (let i = 1; i < coords.length; i++) {
    const d = haversineMeters(coords[i - 1], coords[i]);
    total += d; cum[i] = total;
  }
  if (total <= 0) return null;

  const steps = Math.min(coords.length, Math.max(2, maxStops));
  const out = [];
  for (let k = 0; k < steps; k++) {
    const i = Math.floor((k * (coords.length - 1)) / (steps - 1));
    let kmh;
    if (i > 0) {
      const dt = Math.max(1e-3, relSeconds[i] - relSeconds[i - 1]);
      const ds = Math.max(0, cum[i] - cum[i - 1]);
      kmh = (ds / dt) * 3.6;
    } else {
      const dt = Math.max(1e-3, relSeconds[1] - relSeconds[0]);
      const ds = Math.max(0, cum[1] - cum[0]);
      kmh = (ds / dt) * 3.6;
    }
    const t = (cum[i] / total);
    out.push({ t: k === 0 ? 0 : (k === steps - 1 ? 1 : t), color: speedToHex(kmh) });
  }
  return out;
}

const rectFC = ({ west, south, east, north }, props = {}) => ({
  type: 'FeatureCollection',
  features: [{
    type: 'Feature',
    properties: props,
    geometry: { type: 'Polygon', coordinates: [[[west, south], [east, south], [east, north], [west, north], [west, south]]] }
  }]
});

// Try to decode/collect coordinates from various raw shapes (optional)
function decodePolyline(str, precision = 5) {
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
const isLngLatPair = (x) =>
  Array.isArray(x) && x.length >= 2 &&
  Number.isFinite(x[0]) && Number.isFinite(x[1]) &&
  x[0] >= -180 && x[0] <= 180 && x[1] >= -90 && x[1] <= 90;
const looksLikeCoords = (arr) =>
  Array.isArray(arr) && arr.length >= 2 && isLngLatPair(arr[0]) && isLngLatPair(arr[arr.length - 1]);
function tryDecodePolyline(str) {
  if (typeof str !== 'string' || !str.length) return null;
  const p6 = decodePolyline(str, 6);
  if (looksLikeCoords(p6)) return p6;
  const p5 = decodePolyline(str, 5);
  if (looksLikeCoords(p5)) return p5;
  return null;
}
function coordsFromRawGeometry(raw) {
  if (!raw) return null;
  if (raw.geometry && Array.isArray(raw.geometry.coordinates) && looksLikeCoords(raw.geometry.coordinates)) return raw.geometry.coordinates;
  if (typeof raw.geometry === 'string') { const d = tryDecodePolyline(raw.geometry); if (d) return d; }
  if (Array.isArray(raw.routes?.[0]?.geometry?.coordinates) && looksLikeCoords(raw.routes[0].geometry.coordinates)) return raw.routes[0].geometry.coordinates;
  if (typeof raw.routes?.[0]?.geometry === 'string') { const d = tryDecodePolyline(raw.routes[0].geometry); if (d) return d; }
  const feat = Array.isArray(raw.features) ? raw.features[0] : (raw.feature ?? null);
  const gj = feat?.geometry || raw?.geometry;
  if (gj && Array.isArray(gj.coordinates) && looksLikeCoords(gj.coordinates)) return gj.coordinates;
  return null;
}

// ───────── component ─────────
export default function MapboxComponent({ mapStyle }) {
  const seedView = useMapStore(s => s.viewState);
  const { GeojsonFiles, etaEveryMeters, etaSpeedKmh } = useVrpStore();

  const {
    waypoints, waypointsVisible, hoveredWaypoint,
    setHoveredWaypoint, addWaypoint, clearHoveredWaypoint
  } = useWaypointStore();

  const {
    hoveredFeature, setHoveredFeature, clearHoveredFeature,
    addOnClickEnabled, drawBBoxEnabled, setDrawBBoxEnabled,
    lastBbox, setLastBbox, etasEnabled, trafficEnabled, setTrafficEnabled
  } = useUiStore();

  const geometrySource = useRenderSettingsStore(s => s.geometrySource || 'auto');

  const routes = useRouteStore(s => s.routes);
  const currentIndex = useRouteStore(s => s.currentIndex);

  // Local parity toggles with MapLibre
  const [clustersOn, setClustersOn] = useState(true);
  const [lassoOn, setLassoOn] = useState(false);
  const [tripsOn, setTripsOn] = useState(false);
  const [solo, setSolo] = useState(null);      // 'route'|'traffic'|'trips'|'etas'|null
  const [showRoute, setShowRoute] = useState(true);

  useEffect(() => { if (lassoOn && drawBBoxEnabled) setDrawBBoxEnabled(false); }, [lassoOn, drawBBoxEnabled, setDrawBBoxEnabled]);
  useEffect(() => { if (drawBBoxEnabled && lassoOn) setLassoOn(false); }, [drawBBoxEnabled, lassoOn]);

  const mapRef = useRef(null);
  const overlayRef = useRef(null);
  const clusterCtlRef = useRef(null);
  const trafficCtlRef = useRef(null);
  const etaCtlRef = useRef(null);

  // Active route helper
  const getActiveRoute = useCallback(() => {
    const st = useRouteStore.getState();
    return st?.routes?.[st.currentIndex ?? 0] || null;
  }, []);

  // Geometry for active run (snapping/matching)
  const activeForGeom = getActiveRoute();
  const {
    status: geomStatus,
    coords: snappedCoords,
    provider: geomProvider,
  } = useRouteGeometry(activeForGeom, {
    source: geometrySource,
    profile: 'driving',
    osrmUrl: 'https://router.project-osrm.org',
    backendGeometryEndpoint: '/route/geometry',
    backendMapboxEndpoint: '/mapbox/match',
  });

  // Persist chosen geometry (same as MapLibre)
  useEffect(() => {
    if (geomStatus !== 'ok' || !Array.isArray(snappedCoords) || snappedCoords.length < 2) return;
    useRouteStore.setState(s => {
      const next = Array.isArray(s.routes) ? [...s.routes] : [];
      const idx  = Number.isInteger(s.currentIndex) ? s.currentIndex : 0;
      if (!next[idx]) return s;
      next[idx] = { ...next[idx], displayCoords: snappedCoords, displayProvider: geomProvider };
      return { routes: next };
    });
  }, [geomStatus, snappedCoords, geomProvider]);

  // Expose for quick console checks
  useEffect(() => {
    if (typeof window !== 'undefined') {
      window.__geom = () => ({ provider: geomProvider, status: geomStatus, pts: (snappedCoords || []).length });
    }
    // eslint-disable-next-line no-console
    console.log('[geom]', { provider: geomProvider, status: geomStatus, pts: (snappedCoords || []).length });
  }, [geomProvider, geomStatus, snappedCoords]);

  // ───────── BBox state ─────────
  const [dragA, setDragA] = useState(null);
  const [dragB, setDragB] = useState(null);
  const DRAG_MIN_LL = 1e-6;
  const [twoClickA, setTwoClickA] = useState(null);
  const [hoverCoord, setHoverCoord] = useState(null);

  useEffect(() => {
    if (!drawBBoxEnabled) {
      setDragA(null); setDragB(null);
      setTwoClickA(null); setHoverCoord(null);
    }
  }, [drawBBoxEnabled]);

  const dragRectFC = useMemo(() => {
    if (!(drawBBoxEnabled && dragA && dragB)) return null;
    const west = Math.min(dragA[0], dragB[0]);
    const east = Math.max(dragA[0], dragB[0]);
    const south = Math.min(dragA[1], dragB[1]);
    const north = Math.max(dragA[1], dragB[1]);
    return rectFC({ west, south, east, north }, { _temp: true });
  }, [drawBBoxEnabled, dragA, dragB]);

  // ───────── Layers ─────────
  const waypointLayer = useMemo(() => {
    if (!waypointsVisible || waypoints.length === 0 || clustersOn) return null;
    const color = (t) =>
      t === 'Depot' ? [0, 102, 255] :
        t === 'Delivery' ? [0, 168, 84] :
          t === 'Pickup' ? [255, 165, 0] :
            t === 'Backhaul' ? [230, 57, 70] : [128, 128, 128];

    return new ScatterplotLayer({
      id: 'waypoints',
      data: waypoints,
      getPosition: d => d.coordinates,
      getFillColor: d => color(d.type),
      radiusUnits: 'pixels', getRadius: 10,
      pickable: true, radiusMinPixels: 8, radiusMaxPixels: 24,
      onClick: (info) => {
        if (info.object) {
          setHoveredWaypoint({ ...info.object, position: info.coordinate, screenX: info.x, screenY: info.y });
        } else {
          clearHoveredWaypoint();
        }
      },
      parameters: { depthTest: false }
    });
  }, [waypoints, waypointsVisible, clustersOn, setHoveredWaypoint, clearHoveredWaypoint]);

  const geoLayers = useMemo(() => {
    return GeojsonFiles
      .filter(f => f.visible && f?.data?.type === 'FeatureCollection' && Array.isArray(f?.data?.features))
      .map(file => new GeoJsonLayer({
        id: `geojson-${file.id}`,
        data: file.data, pickable: true, filled: true, stroked: true,
        getLineColor: [120, 160, 255], getFillColor: [80, 200, 160, 50], getLineWidth: 2,
        onClick: (info) => {
          if (info?.object) {
            setHoveredFeature({
              fileId: file.id, properties: info.object.properties,
              position: info.coordinate, screenX: info.x, screenY: info.y
            });
          }
        },
        parameters: { depthTest: false }
      }));
  }, [GeojsonFiles, setHoveredFeature]);

  const bboxEditableLayer = useMemo(() => {
    if (!drawBBoxEnabled || lassoOn) return null;
    return new EditableGeoJsonLayer({
      id: 'bbox-editable',
      data: { type: 'FeatureCollection', features: [] },
      mode: DrawRectangleMode,
      selectedFeatureIndexes: [],
      onEdit: ({ updatedData }) => {
        const f = updatedData?.features?.slice(-1)?.[0];
        const ring = f?.geometry?.coordinates?.[0];
        if (!Array.isArray(ring) || ring.length < 4) return;
        const lons = ring.map(([lon]) => lon);
        const lats = ring.map(([, lat]) => lat);
        const west = Math.min(...lons), east = Math.max(...lons);
        const south = Math.min(...lats), north = Math.max(...lats);
        setLastBbox({ west, south, east, north });
      },
      getLineColor: [0, 180, 80],
      getFillColor: [0, 180, 80, 60],
      lineWidthMinPixels: 2,
      parameters: { depthTest: false }
    });
  }, [drawBBoxEnabled, lassoOn, setLastBbox]);

  const dragLayer = useMemo(() => {
    if (!dragRectFC) return null;
    return new GeoJsonLayer({
      id: 'bbox-drag-live',
      data: dragRectFC,
      stroked: true, filled: true,
      getLineColor: [255, 120, 120], getFillColor: [255, 120, 120, 60],
      lineWidthMinPixels: 2, pickable: false,
      parameters: { depthTest: false }
    });
  }, [dragRectFC]);

  const lastBboxLayer = useMemo(() => {
    if (!lastBbox) return null;
    return new GeoJsonLayer({
      id: 'bbox-last',
      data: rectFC(lastBbox, { _last: true }),
      stroked: true, filled: false,
      getLineColor: [120, 180, 255],
      lineWidthMinPixels: 2,
      parameters: { depthTest: false }
    });
  }, [lastBbox]);

  // Build safe, renderable list (coords + optional displayCoords for current)
  const routesForRender = useMemo(() => {
    if (!Array.isArray(routes) || routes.length === 0) return [];
    const byIdx = new Map(waypoints.map((w, i) => [String(i), w.coordinates]));
    return routes.map((r, i) => {
      // 1) base coords from solver/ids
      let coords = Array.isArray(r.coords) && r.coords.length ? r.coords : [];
      if (!coords.length) {
        const ids = Array.isArray(r.waypointIds) ? r.waypointIds
          : Array.isArray(r.raw?.waypoint_ids) ? r.raw.waypoint_ids : [];
        coords = ids.map(id => {
          const n = Number(id);
          return Number.isFinite(n) ? byIdx.get(String(n)) : null;
        }).filter(Boolean);
      }
      // 2) optional display geometry (from raw/polyline)
      let displayCoords = null;
      try { displayCoords = coordsFromRawGeometry(r.raw) || coordsFromRawGeometry(r) || null; } catch { /* noop */ }
      // 3) current run: prefer snappedCoords
      if (i === (currentIndex ?? 0) && Array.isArray(snappedCoords) && snappedCoords.length > 1) {
        displayCoords = snappedCoords;
      }
      return { ...r, coords, displayCoords };
    });
  }, [routes, waypoints, currentIndex, snappedCoords]);

  const routeLayers = useMemo(() => {
    if (!routesForRender.length) return [];
    // hide static route when focusing on live layers
    if (!showRoute || solo === 'traffic' || solo === 'trips') return [];
    const palette = [[230, 57, 70], [42, 157, 143], [38, 70, 83], [233, 196, 106], [29, 53, 87]];
    return routesForRender.map((r, idx) => {
      const path = (idx === currentIndex && Array.isArray(r.displayCoords) && r.displayCoords.length > 1)
        ? r.displayCoords
        : (Array.isArray(r.coords) ? r.coords : []);
      return new PathLayer({
        id: `route-${idx}`,
        data: [path],
        getPath: d => d,
        widthUnits: 'pixels',
        getWidth: (idx === currentIndex) ? 5 : 3,
        getColor: (idx === currentIndex) ? palette[idx % palette.length] : [...palette[idx % palette.length], 100],
        pickable: false,
        parameters: { depthTest: false }
      });
    });
  }, [routesForRender, currentIndex, showRoute, solo]);

  const debugRouteDots = useMemo(() => {
    const r = routesForRender?.[currentIndex];
    const path = Array.isArray(r?.displayCoords) && r.displayCoords.length > 1 ? r.displayCoords : r?.coords;
    if (!Array.isArray(path) || !path.length) return null;
    return new ScatterplotLayer({
      id: 'route-vertex-dots',
      data: path, getPosition: d => d,
      getFillColor: [0, 0, 0],
      radiusUnits: 'pixels', getRadius: 2.5,
      parameters: { depthTest: false }
    });
  }, [routesForRender, currentIndex]);

  const lassoLayer = useMemo(() => {
    if (!lassoOn) return null;
    return createLassoLayer({
      waypoints,
      onSelect: (ids) => console.debug('[lasso] ids:', ids),
      setLastBbox
    });
  }, [lassoOn, waypoints, setLastBbox]);

  const etaTextLayer = useMemo(() => {
    if (!useUiStore.getState().showETAs) return null;
    const r = routesForRender?.[currentIndex];
    const coords = r?.coords, times = r?.etaEpoch, idxs = r?.etaIndices;
    if (!Array.isArray(coords) || !Array.isArray(times) || !Array.isArray(idxs)) return null;
    if (coords.length < 2 || times.length === 0 || idxs.length === 0) return null;
    const data = idxs.map((vi, k) => ({
      position: coords[vi],
      label: new Date((times[k + 1] || times[k] || times[0]) * 1000)
        .toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    }));
    const dim = solo && solo !== 'etas' ? 0.15 : 1;
    return new TextLayer({
      id: 'eta-text', data,
      getPosition: d => d.position, getText: d => d.label,
      sizeUnits: 'pixels', getSize: 12, getColor: [20, 20, 20],
      background: true, getBackgroundColor: [255, 255, 255, 210],
      opacity: dim,
      parameters: { depthTest: false }
    });
  }, [routesForRender, currentIndex, solo]);

  // Trips (Deck animated)
  const [currentTime, setCurrentTime] = useState(0);
  useEffect(() => {
    if (!tripsOn) return;
    let raf = 0, start = performance.now();
    const tick = (now) => { setCurrentTime((now - start) / 1000); raf = requestAnimationFrame(tick); };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [tripsOn]);

  const tripsLayer = useMemo(() => {
    if (!tripsOn) return null;
    const r = routesForRender?.[currentIndex];
    const path = (Array.isArray(r?.displayCoords) && r.displayCoords.length) ? r.displayCoords : (r?.coords || []);
    if (!path.length) return null;

    // prefer provided per-vertex seconds if lengths match; else derive
    const useProvided = Array.isArray(r?.etaRelative) && r.etaRelative.length === path.length;
    const rel = useProvided ? r.etaRelative : relativeTimestampsFromCoords(path, 50);
    const dim = solo && solo !== 'trips' ? 0.15 : 0.95;

    return createTripsLayer({
      id: 'trips',
      trips: [{ path: path.map(([x,y], i) => [x, y, rel[i] || 0]), color: [66, 135, 245], width: 6 }],
      currentTime, trailLength: 600, opacity: dim
    });
  }, [tripsOn, currentTime, routesForRender, currentIndex, solo]);

  const layers = useMemo(() => {
    const L = [];
    if (waypointLayer) L.push(waypointLayer);
    L.push(...geoLayers);
    if (lassoLayer) L.push(lassoLayer);
    if (bboxEditableLayer) L.push(bboxEditableLayer);
    if (dragLayer) L.push(dragLayer);
    if (lastBboxLayer) L.push(lastBboxLayer);
    if (tripsLayer) L.push(tripsLayer);
    if (etaTextLayer) L.push(etaTextLayer);
    if (debugRouteDots) L.push(debugRouteDots);
    L.push(...routeLayers);
    return L;
  }, [waypointLayer, geoLayers, lassoLayer, bboxEditableLayer, dragLayer, lastBboxLayer, tripsLayer, etaTextLayer, debugRouteDots, routeLayers]);

  // ───────── Map load & overlay ─────────
  const handleDeckClick = useCallback((info) => {
    if (!info?.object) { clearHoveredFeature(); clearHoveredWaypoint(); }

    if (drawBBoxEnabled && info?.coordinate) {
      const shift = info?.srcEvent?.shiftKey ?? info?.sourceEvent?.shiftKey ?? false;
      if (!shift) {
        if (!twoClickA) {
          setTwoClickA(info.coordinate);
          setHoverCoord(info.coordinate);
        } else {
          const a = twoClickA, b = info.coordinate;
          const west = Math.min(a[0], b[0]);
          const east = Math.max(a[0], b[0]);
          const south = Math.min(a[1], b[1]);
          const north = Math.max(a[1], b[1]);
          if ((east - west) > 1e-6 && (north - south) > 1e-6) {
            setLastBbox({ west, south, east, north });
          }
          setTwoClickA(null); setHoverCoord(null);
        }
        return;
      }
    }

    if (addOnClickEnabled && !drawBBoxEnabled && info?.coordinate) {
      const [lng, lat] = info.coordinate;
      addWaypoint({
        coordinates: [lng, lat],
        id: Date.now(),
        type: 'Delivery',
        demand: 1, capacity: 5, serviceTime: 10, timeWindow: [8, 17]
      });
    }
  }, [drawBBoxEnabled, twoClickA, addOnClickEnabled, addWaypoint, clearHoveredFeature, clearHoveredWaypoint, setLastBbox]);

  const onDeckPointerDown = useCallback((info, evt) => {
    if (!(drawBBoxEnabled && !lassoOn)) return;
    const shift = evt?.srcEvent?.shiftKey ?? info?.srcEvent?.shiftKey ?? false;
    if (!shift) return;
    const coord = info?.coordinate; if (!coord) return;
    mapRef.current?.getMap?.()?.dragPan?.disable?.();
    setDragA(coord); setDragB(coord);
    evt?.stopPropagation?.(); evt?.preventDefault?.();
  }, [drawBBoxEnabled, lassoOn]);

  const onDeckPointerMove = useCallback((info, evt) => {
    if (!(drawBBoxEnabled && !lassoOn) || !dragA) return;
    const shift = evt?.srcEvent?.shiftKey ?? info?.srcEvent?.shiftKey ?? false;
    if (!shift) return;
    const coord = info?.coordinate; if (!coord) return;
    setDragB(coord);
    evt?.stopPropagation?.(); evt?.preventDefault?.();
  }, [drawBBoxEnabled, lassoOn, dragA]);

  const onDeckPointerUp = useCallback((info, evt) => {
    if (!(drawBBoxEnabled && !lassoOn)) return;
    const shift = evt?.srcEvent?.shiftKey ?? info?.srcEvent?.shiftKey ?? false;
    if (!shift) return;
    const map = mapRef.current?.getMap?.(); map?.dragPan?.enable?.();

    if (dragA && dragB) {
      const west = Math.min(dragA[0], dragB[0]);
      const east = Math.max(dragA[0], dragB[0]);
      const south = Math.min(dragA[1], dragB[1]);
      const north = Math.max(dragA[1], dragB[1]);
      if ((east - west) > DRAG_MIN_LL && (north - south) > DRAG_MIN_LL) {
        setLastBbox({ west, south, east, north });
      }
    }
    setDragA(null); setDragB(null);
    evt?.stopPropagation?.(); evt?.preventDefault?.();
  }, [drawBBoxEnabled, lassoOn, dragA, dragB, setLastBbox]);

  const handleMapLoad = useCallback(() => {
    const map = mapRef.current?.getMap?.();
    if (!map) return;

    if (!overlayRef.current) {
      overlayRef.current = new MapboxOverlay({
        interleaved: true,
        controller: { dragRotate: false, touchRotate: false, scrollZoom: true, dragPan: !(drawBBoxEnabled || lassoOn) }
      });
      map.addControl(overlayRef.current);
    }
    overlayRef.current.setProps({
      layers,
      onClick: handleDeckClick,
      onPointerDown: onDeckPointerDown,
      onPointerMove: onDeckPointerMove,
      onPointerUp: onDeckPointerUp
    });

    // clusters mount
    if (clustersOn && !clusterCtlRef.current) {
      const fcNow = {
        type: 'FeatureCollection',
        features: (waypointsVisible ? waypoints : []).map(w => ({
          type: 'Feature', geometry: { type: 'Point', coordinates: w.coordinates }, properties: { id: w.id }
        }))
      };
      clusterCtlRef.current = addClusteredSource(map, { id: 'wp-clusters', data: fcNow, clusterRadius: 40 });
    }

    if (typeof window !== 'undefined') window.__vrpMap = map;
  }, [layers, handleDeckClick, onDeckPointerDown, onDeckPointerMove, onDeckPointerUp, clustersOn, waypoints, waypointsVisible, drawBBoxEnabled, lassoOn]);

  // Keep overlay updated
  useEffect(() => {
    if (overlayRef.current) {
      overlayRef.current.setProps({
        layers,
        onClick: handleDeckClick,
        onPointerDown: onDeckPointerDown,
        onPointerMove: onDeckPointerMove,
        onPointerUp: onDeckPointerUp,
        controller: { dragRotate: false, touchRotate: false, scrollZoom: true, dragPan: !(drawBBoxEnabled || lassoOn) }
      });
    }
  }, [layers, handleDeckClick, onDeckPointerDown, onDeckPointerMove, onDeckPointerUp, drawBBoxEnabled, lassoOn]);

  // Cleanup
  useEffect(() => {
    return () => {
      const map = mapRef.current?.getMap?.();
      if (map && overlayRef.current) {
        try { map.removeControl(overlayRef.current); } catch { }
        overlayRef.current = null;
      }
      clusterCtlRef.current?.remove(); clusterCtlRef.current = null;
      trafficCtlRef.current?.remove(); trafficCtlRef.current = null;
      etaCtlRef.current?.remove(); etaCtlRef.current = null;
    };
  }, []);

  // Cluster updates
  useEffect(() => {
    const map = mapRef.current?.getMap?.();
    if (!map) return;

    if (!clustersOn) {
      clusterCtlRef.current?.remove(); clusterCtlRef.current = null;
      return;
    }
    if (!clusterCtlRef.current) {
      clusterCtlRef.current = addClusteredSource(map, { id: 'wp-clusters', data: { type: 'FeatureCollection', features: [] }, clusterRadius: 40 });
    }
    const fc = {
      type: 'FeatureCollection',
      features: (waypointsVisible ? waypoints : []).map(w => ({
        type: 'Feature', geometry: { type: 'Point', coordinates: w.coordinates }, properties: { id: w.id }
      }))
    };
    clusterCtlRef.current.update(fc);
  }, [clustersOn, waypoints, waypointsVisible]);

  // Traffic gradient (native Mapbox line)
  useEffect(() => {
    const map = mapRef.current?.getMap?.(); if (!map) return;

    const sync = () => {
      const st = useRouteStore.getState();
      const r = st?.routes?.[st.currentIndex];
      if (!r) { trafficCtlRef.current?.remove(); trafficCtlRef.current = null; return; }

      const coords =
        (Array.isArray(r?.displayCoords) && r.displayCoords.length >= 2)
          ? r.displayCoords
          : (Array.isArray(r?.coords) ? r.coords : []);

      const dim = solo && solo !== 'traffic' ? 0.15 : 0.6;

      if (!trafficEnabled || coords.length < 2) {
        trafficCtlRef.current?.remove(); trafficCtlRef.current = null; return;
      }

      // gradient only if per-vertex ETAs align with the chosen geometry
      let gradientStops = null;
      if (Array.isArray(r?.etaRelative) && r.etaRelative.length === coords.length) {
        gradientStops = buildGradientStops(coords, r.etaRelative, 16);
      }

      const line = { type: 'Feature', geometry: { type: 'LineString', coordinates: coords }, properties: {} };
      if (!trafficCtlRef.current) {
        trafficCtlRef.current = addTrafficLine(map, {
          id: 'route-traffic',
          sourceId: 'route-traffic-src',
          routeData: line,
          width: 5,
          opacity: dim,
          offset: 3,
          dashArray: [2, 1],
          solidColor: '#00FFFF',
          useGradient: !!gradientStops,
          gradientStops,
        });
        trafficCtlRef.current.setOpacity(dim);
      } else {
        trafficCtlRef.current.update(line, { gradientStops });
        trafficCtlRef.current.setOpacity(dim);
      }
    };

    const u = useRouteStore.subscribe(sync);
    sync();
    return () => { try { u && u(); } catch { } trafficCtlRef.current?.remove(); trafficCtlRef.current = null; };
  }, [trafficEnabled, solo]);

  // ETA glyphs (native Mapbox)
  useEffect(() => {
    const map = mapRef.current?.getMap?.(); if (!map) return;

    const getCoords = () => {
      const st = useRouteStore.getState();
      const run = st?.routes?.[st.currentIndex];
      if (Array.isArray(run?.displayCoords) && run.displayCoords.length >= 2) return run.displayCoords;
      return run?.coords || [];
    };

    if (!etasEnabled) { etaCtlRef.current?.remove(); etaCtlRef.current = null; return; }

    const coords = getCoords();
    if (coords.length < 2) { etaCtlRef.current?.remove(); etaCtlRef.current = null; return; }

    if (!etaCtlRef.current) etaCtlRef.current = createEtaController(map, { id: 'route-etas', sourceId: 'route-etas-src' });
    etaCtlRef.current.update(coords, { speedKmh: etaSpeedKmh, everyMeters: etaEveryMeters, textColor: '#ffffff', halo: '#000000', haloWidth: 2 });
    etaCtlRef.current.setOpacity(solo && solo !== 'etas' ? 0.15 : 1);

    const u = useRouteStore.subscribe(() => {
      const c2 = getCoords();
      if (c2.length >= 2) {
        etaCtlRef.current?.update(c2, { speedKmh: etaSpeedKmh, everyMeters: etaEveryMeters, textColor: '#ffffff', halo: '#000000', haloWidth: 2 });
        etaCtlRef.current?.setOpacity(solo && solo !== 'etas' ? 0.15 : 1);
      } else { etaCtlRef.current?.remove(); etaCtlRef.current = null; }
    });

    return () => { try { u && u(); } catch { } etaCtlRef.current?.remove(); etaCtlRef.current = null; };
  }, [etasEnabled, etaEveryMeters, etaSpeedKmh, solo]);

  // ───────── UI ─────────
  return (
    <>
      <div className="absolute top-2 right-2 z-50 bg-black/90 text-white px-2 py-1 rounded shadow text-xs space-x-2">
        <label><input type="checkbox" checked={clustersOn} onChange={e => setClustersOn(e.target.checked)} /> Clusters</label>
        <label><input type="checkbox" checked={trafficEnabled} onChange={e => setTrafficEnabled(e.target.checked)} /> Traffic</label>
        <label><input type="checkbox" checked={lassoOn} onChange={e => setLassoOn(e.target.checked)} /> Lasso</label>
        <label>
          <input
            type="checkbox"
            checked={tripsOn}
            onChange={e => {
              const v = e.target.checked;
              setTripsOn(v);
              setShowRoute(!v);
            }}
          /> Trips
        </label>
        <label className="ml-2">
          Solo:
          <select
            className="ml-1 bg-black/20"
            value={solo ?? ''}
            onChange={e => {
              const val = e.target.value || null;
              setSolo(val);
              if (val === 'trips' || val === 'traffic') setShowRoute(false);
              else setShowRoute(true);
            }}
          >
            <option value="">(none)</option>
            <option value="route">Route</option>
            <option value="traffic">Traffic</option>
            <option value="trips">Trips</option>
            <option value="etas">ETAs</option>
          </select>
        </label>
        <label className="ml-2"><input type="checkbox" checked={showRoute} onChange={e => setShowRoute(e.target.checked)} /> Route</label>
      </div>

      <MapGL
        ref={mapRef}
        mapboxAccessToken={mapboxgl.accessToken}
        mapStyle={mapStyle || MAP_STYLE}
        initialViewState={seedView}
        onLoad={handleMapLoad}
        style={{ position: 'absolute', inset: 0 }}
      />

      {/* BBox click-capture overlay (only when BBox is ON) */}
      <div
        data-testid="bbox-click-overlay"
        onClick={(e) => {
          if (!drawBBoxEnabled) return;
          const map = mapRef.current?.getMap?.(); if (!map) return;
          const rect = e.currentTarget.getBoundingClientRect();
          const x = e.clientX - rect.left, y = e.clientY - rect.top;
          const { lng, lat } = map.unproject([x, y]);
          if (!twoClickA) { setTwoClickA([lng, lat]); setHoverCoord([lng, lat]); }
          else {
            const a = twoClickA, b = [lng, lat];
            const west = Math.min(a[0], b[0]);
            const east = Math.max(a[0], b[0]);
            const south = Math.min(a[1], b[1]);
            const north = Math.max(a[1], b[1]);
            if ((east - west) > 1e-6 && (north - south) > 1e-6) setLastBbox({ west, south, east, north });
            setTwoClickA(null); setHoverCoord(null);
          }
        }}
        style={{ position: 'absolute', inset: 0, zIndex: 40, pointerEvents: drawBBoxEnabled ? 'auto' : 'none', background: 'transparent' }}
      />

      {/* Popups */}
      {hoveredFeature?.position && (
        <div className="absolute bg-white text-black p-2 rounded shadow-lg text-sm"
             style={{ left: `${hoveredFeature.screenX ?? 0}px`, top: `${hoveredFeature.screenY ?? 0}px`, transform: 'translate(10px, -100%)', pointerEvents: 'none', zIndex: 9999 }}>
          <pre className="whitespace-pre-wrap">{JSON.stringify(hoveredFeature.properties, null, 2)}</pre>
        </div>
      )}

      {hoveredWaypoint?.coordinates && (
        <div className="absolute bg-white text-black p-2 rounded shadow-lg text-sm"
             style={{ left: `${hoveredWaypoint.screenX ?? 0}px`, top: `${hoveredWaypoint.screenY ?? 0}px`, transform: 'translate(10px, -100%)', pointerEvents: 'none', zIndex: 9999 }}>
          <div className="text-xs">
            <strong>Type:</strong> {hoveredWaypoint.type}<br />
            <strong>Demand:</strong> {hoveredWaypoint.demand}<br />
            <strong>Capacity:</strong> {hoveredWaypoint.capacity ?? '—'}<br />
            <strong>Service Time:</strong> {hoveredWaypoint.serviceTime ?? '—'}<br />
            <strong>Time Window:</strong> {Array.isArray(hoveredWaypoint.timeWindow) ? hoveredWaypoint.timeWindow.join(', ') : (hoveredWaypoint.timeWindow ?? '—')}<br />
            <strong>Pair ID:</strong> {hoveredWaypoint.pairId ?? '—'}<br />
            <strong>Coordinates:</strong> {hoveredWaypoint.coordinates.join(', ')}
          </div>
        </div>
      )}
    </>
  );
}
