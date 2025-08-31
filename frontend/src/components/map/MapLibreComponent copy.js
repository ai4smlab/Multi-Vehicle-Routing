// components/map/MapLibreComponent.js
'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { DeckGL } from '@deck.gl/react';
import { ScatterplotLayer, GeoJsonLayer, PathLayer, TextLayer } from '@deck.gl/layers';
import { TripsLayer } from '@deck.gl/geo-layers';
import MapGL from 'react-map-gl/maplibre';
import maplibregl from 'maplibre-gl';
import { EditableGeoJsonLayer, DrawRectangleMode } from '@deck.gl-community/editable-layers';

import useMapStore from '@/hooks/useMapStore';
import useVrpStore from '@/hooks/useVRPStore';
import useWaypointStore from '@/hooks/useWaypointStore';
import useUiStore from '@/hooks/useUIStore';
import useRouteStore from '@/hooks/useRouteStore';

import { addClusteredSource } from '@/components/mapbox/layers/addClusteredSource';
import { addTrafficLine } from '@/components/mapbox/layers/addTrafficLine';
import { createLassoLayer } from '@/components/mapbox/layers/createLassoLayer';
import { createEtaController } from '@/components/mapbox/layers/etaLayer';
import ContextMenu from '@/components/mapbox/ui/ContextMenu';
import { ensureRTLTextPlugin } from '@/utils/ensureRTLTextPlugin';
import { useRouteGeometry } from '@/hooks/useRouteGeometry';
import useRenderSettingsStore from '@/hooks/useRenderSettingsStore';
import RouteLayer from '@/components/map/RouteLayer';

// Dark basemap
const MAP_STYLE = 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json';

const EPS = 1e-6;
const PROGRAMMATIC_COOLDOWN_MS = 900;
const camEq = (a = {}, b = {}) =>
  Math.abs((a.longitude ?? 0) - (b.longitude ?? 0)) < EPS &&
  Math.abs((a.latitude ?? 0) - (b.latitude ?? 0)) < EPS &&
  Math.abs((a.zoom ?? 0) - (b.zoom ?? 0)) < EPS &&
  Math.abs((a.bearing ?? 0) - (b.bearing ?? 0)) < EPS &&
  Math.abs((a.pitch ?? 0) - (b.pitch ?? 0)) < EPS;

const camFromMap = (m) => {
  const c = m.getCenter();
  return { longitude: c.lng, latitude: c.lat, zoom: m.getZoom(), bearing: m.getBearing(), pitch: m.getPitch() };
};

function rectFC({ west, south, east, north }, props = {}) {
  return {
    type: 'FeatureCollection',
    features: [{
      type: 'Feature',
      properties: props,
      geometry: { type: 'Polygon', coordinates: [[[west, south], [east, south], [east, north], [west, north], [west, south]]] }
    }]
  };
}

// MapLibreComponent.js (top helper section)
function speedToHex(kmh) {
  if (kmh <= 10) return '#d73027';        // red
  if (kmh <= 25) return '#fc8d59';        // orange
  if (kmh <= 45) return '#fee08b';        // yellow
  if (kmh <= 70) return '#d9ef8b';        // light green
  return '#1a9850';                        // green
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
      const dt = Math.max(1e-3, relSeconds[i] - relSeconds[i - 1]); // s
      const ds = Math.max(0, cum[i] - cum[i - 1]);                  // m
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



// helpers for trips time fallback
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

// --- geometry helpers (robust)
function decodePolyline(str, precision = 5) {
  // Google polyline (5/6) decoder; returns [ [lon,lat], ... ]
  let index = 0, lat = 0, lng = 0, coords = [];
  const factor = Math.pow(10, precision);
  while (index < str.length) {
    let b, shift = 0, result = 0;
    do { b = str.charCodeAt(index++) - 63; result |= (b & 0x1f) << shift; shift += 5; } while (b >= 0x20);
    const dlat = (result & 1) ? ~(result >> 1) : (result >> 1);
    lat += dlat;
    shift = 0; result = 0;
    do { b = str.charCodeAt(index++) - 63; result |= (b & 0x1f) << shift; shift += 5; } while (b >= 0x20);
    const dlng = (result & 1) ? ~(result >> 1) : (result >> 1);
    lng += dlng;
    coords.push([lng / factor, lat / factor]);
  }
  return coords;
}

function isLngLatPair(x) {
  return Array.isArray(x) && x.length >= 2 &&
    Number.isFinite(x[0]) && Number.isFinite(x[1]) &&
    x[0] >= -180 && x[0] <= 180 &&
    x[1] >= -90 && x[1] <= 90;
}
function looksLikeCoords(arr) {
  return Array.isArray(arr) && arr.length >= 2 && isLngLatPair(arr[0]) && isLngLatPair(arr[arr.length - 1]);
}

function tryDecodePolyline(str) {
  if (typeof str !== 'string' || !str.length) return null;
  // try polyline6 first (ORS often uses this), then polyline5
  const p6 = decodePolyline(str, 6);
  if (looksLikeCoords(p6)) return p6;
  const p5 = decodePolyline(str, 5);
  if (looksLikeCoords(p5)) return p5;
  return null;
}

/** Try to extract coordinates from a variety of raw-shapes (ORS / OSRM / custom) */
function coordsFromRawGeometry(raw) {
  if (!raw) return null;

  // 1) raw.geometry as GeoJSON {coordinates: [...]}
  if (raw.geometry && Array.isArray(raw.geometry.coordinates) && looksLikeCoords(raw.geometry.coordinates)) {
    return raw.geometry.coordinates;
  }
  // 2) raw.geometry as encoded string (polyline5/6)
  if (typeof raw.geometry === 'string') {
    const d = tryDecodePolyline(raw.geometry);
    if (d) return d;
  }
  // 3) raw.routes[0].geometry as coords
  if (Array.isArray(raw.routes?.[0]?.geometry?.coordinates) &&
    looksLikeCoords(raw.routes[0].geometry.coordinates)) {
    return raw.routes[0].geometry.coordinates;
  }
  // 4) raw.routes[0].geometry as string (polyline)
  if (typeof raw.routes?.[0]?.geometry === 'string') {
    const d = tryDecodePolyline(raw.routes[0].geometry);
    if (d) return d;
  }
  // 5) FeatureCollection / Feature(paths)
  const feat = Array.isArray(raw.features) ? raw.features[0] : (raw.feature ?? null);
  const gj = feat?.geometry || raw?.geometry;
  if (gj && Array.isArray(gj.coordinates) && looksLikeCoords(gj.coordinates)) {
    return gj.coordinates;
  }
  // not found
  return null;
}


export default function MapLibreComponent() {
  // stores
  const { viewState: storeView, setViewState: setStoreView } = useMapStore();
  const { GeojsonFiles, etaEveryMeters, etaSpeedKmh } = useVrpStore();

  const [solo, setSolo] = useState(null); // 'route'|'traffic'|'trips'|'etas'|null
  const [showRoute, setShowRoute] = useState(true);

  const routes = useRouteStore(s => s.routes);
  const currentIndex = useRouteStore(s => s.currentIndex);
  const wps = useWaypointStore(s => s.waypoints);

  const {
    waypoints, waypointsVisible, hoveredWaypoint,
    setHoveredWaypoint, addWaypoint, clearHoveredWaypoint
  } = useWaypointStore();

  const {
    hoveredFeature, setHoveredFeature, clearHoveredFeature,
    addOnClickEnabled, drawBBoxEnabled, setDrawBBoxEnabled,
    lastBbox, setLastBbox, etasEnabled, trafficEnabled, setTrafficEnabled
  } = useUiStore();

  // where the display geometry should come from
  const geometrySource =
    useRenderSettingsStore?.((s) => s.geometrySource) ??
    (typeof window !== 'undefined'
      ? localStorage.getItem('geometrySource') || 'auto'
      : 'auto');

  // local UI toggles
  const [clustersOn, setClustersOn] = useState(true);
  const [lassoOn, setLassoOn] = useState(false);
  const [tripsOn, setTripsOn] = useState(false);
  const [prevTraffic, setPrevTraffic] = useState(null);

  // Ensure RTL text plugin once (client-only, HMR-safe)
  useEffect(() => {
    const res = ensureRTLTextPlugin(maplibregl);
    if (process.env.NODE_ENV !== 'production') {
      console.debug('[rtl] ensure →', res);
    }
  }, []);

  // BBox (drag + two-click)
  const [twoClickA, setTwoClickA] = useState(null);
  const [hoverCoord, setHoverCoord] = useState(null);

  useEffect(() => {
    if (!drawBBoxEnabled) {
      setTwoClickA(null);
      setDragA(null);
      setDragB(null);
    }
  }, [drawBBoxEnabled]);
  
  // mutual exclusion
  useEffect(() => { if (lassoOn && drawBBoxEnabled) setDrawBBoxEnabled(false); }, [lassoOn, drawBBoxEnabled, setDrawBBoxEnabled]);
  useEffect(() => { if (drawBBoxEnabled && lassoOn) setLassoOn(false); }, [drawBBoxEnabled, lassoOn]);

  // route accessor + version ping
  const getActiveRoute = useCallback(() => {
    const rs = useRouteStore.getState();
    return rs?.routes?.[rs.currentIndex] || null;
  }, []);
  const [routeVer, setRouteVer] = useState(0);
  useEffect(() => {
    const u = useRouteStore.subscribe(() => setRouteVer(v => v + 1));
    return () => { try { u && u(); } catch { } };
  }, []);


  // Provider-agnostic display geometry for the active route
  const activeRouteForGeom = getActiveRoute();
  const {
    status: geomStatus,
    coords: snappedCoords,
    provider: geomProvider,
  } = useRouteGeometry(activeRouteForGeom, {
    source: geometrySource,                // 'auto' | 'backend' | 'mapbox' | 'osrm' | 'none'
    profile: 'driving',
    osrmUrl: 'https://router.project-osrm.org',
    backendGeometryEndpoint: '/api/route/geometry',
    backendMapboxEndpoint: '/api/mapbox/match'
  });


  // geometry source selection (auto/backend/mapbox/osrm/none)
  // active route for geometry
  const activeForGeom = useMemo(() => {
    const r = getActiveRoute();
    if (!r?.coords || r.coords.length < 2) return null;
    return { coords: r.coords, raw: r.raw };
  }, [routeVer, getActiveRoute]);

  useRouteGeometry(activeForGeom, { source: geometrySource, profile: 'driving' });

  // handy console helper
  useEffect(() => {
    window.__geom = () => ({ provider: geomProvider, status: geomStatus, pts: (snappedCoords || []).length });
    if (process.env.NODE_ENV !== 'production') {
      console.log('[geom]', { provider: geomProvider, status: geomStatus, pts: (snappedCoords || []).length });
    }
  }, [geomProvider, geomStatus, snappedCoords]);



  // refs
  const mapRef = useRef(null);
  const deckRef = useRef(null);
  const [mapLoaded, setMapLoaded] = useState(false);

  // pause Deck RAF unless animating
  useEffect(() => {
    const deck = deckRef.current?.deck;
    if (deck) deck.setProps({ _animate: !!tripsOn });
  }, [tripsOn]);

  // camera sync
  const lastUserMoveTs = useRef(0);
  const isInteracting = useRef(false);
  const pendingViewRef = useRef(null);
  const cooldownTimerRef = useRef(null);

  const deckToStoreTimer = useRef(0);
  const onDeckViewChange = useCallback(({ viewState }) => {
    lastUserMoveTs.current = performance.now();
    if (deckToStoreTimer.current) clearTimeout(deckToStoreTimer.current);
    const vs = {
      longitude: viewState.longitude,
      latitude: viewState.latitude,
      zoom: viewState.zoom,
      bearing: viewState.bearing ?? 0,
      pitch: viewState.pitch ?? 0
    };
    deckToStoreTimer.current = setTimeout(() => { setStoreView(vs); }, 100);
  }, [setStoreView]);
  useEffect(() => () => deckToStoreTimer.current && clearTimeout(deckToStoreTimer.current), []);

  const onInteractionStateChange = useCallback((s) => {
    const active = !!(s?.isDragging || s?.isPanning || s?.isZooming || s?.isRotating || s?.inTransition);
    isInteracting.current = active;
    if (active) lastUserMoveTs.current = performance.now();
    if (active) { clearHoveredFeature(); clearHoveredWaypoint(); }
  }, [clearHoveredFeature, clearHoveredWaypoint]);

  useEffect(() => {
    const map = mapRef.current?.getMap?.(); if (!map) return;
    const start = () => { isInteracting.current = true; lastUserMoveTs.current = performance.now(); };
    const end = () => {
      isInteracting.current = false;
      lastUserMoveTs.current = performance.now();
      if (cooldownTimerRef.current) clearTimeout(cooldownTimerRef.current);
      cooldownTimerRef.current = setTimeout(() => {
        const deck = deckRef.current?.deck;
        const m = mapRef.current?.getMap?.();
        const target = pendingViewRef.current;
        if (!deck || !m || !target) return;
        pendingViewRef.current = null;
        const current = camFromMap(m);
        if (camEq(current, target)) return;
        deck.setProps({ viewState: target });
        requestAnimationFrame(() => deck.setProps({ viewState: null }));
      }, PROGRAMMATIC_COOLDOWN_MS);
    };
    map.on('movestart', start);
    map.on('moveend', end);
    return () => { map.off('movestart', start); map.off('moveend', end); clearTimeout(cooldownTimerRef.current); };
  }, [mapLoaded]);

  useEffect(() => {
    const deck = deckRef.current?.deck;
    const map = mapRef.current?.getMap?.();
    if (!deck || !map || !storeView) return;
    const since = performance.now() - lastUserMoveTs.current;
    const cooling = isInteracting.current || since < PROGRAMMATIC_COOLDOWN_MS;
    if (cooling) { pendingViewRef.current = storeView; return; }
    const current = camFromMap(map);
    if (camEq(current, storeView)) return;
    deck.setProps({ viewState: storeView });
    requestAnimationFrame(() => deck.setProps({ viewState: null }));
  }, [storeView]);

  useEffect(() => {
    if (!mapLoaded) return;
    const m = mapRef.current?.getMap?.(); if (!m) return;
    setStoreView(camFromMap(m));
  }, [mapLoaded, setStoreView]);

  // BBox pointer handling
  const [dragA, setDragA] = useState(null);
  const [dragB, setDragB] = useState(null);
  const DRAG_MIN_LL = 1e-6;
  useEffect(() => {
    const m = mapRef.current?.getMap?.();
    if (!m) return;
    try { drawBBoxEnabled ? m.boxZoom?.disable?.() : m.boxZoom?.enable?.(); } catch { }
  }, [drawBBoxEnabled]);

  const onDeckPointerDown = useCallback((evt) => {
    if (!(drawBBoxEnabled && !lassoOn)) return;
    const shift = evt?.srcEvent?.shiftKey; if (!shift) return;
    evt.stopPropagation?.(); evt.preventDefault?.();
    const coord = evt?.coordinate; if (!coord) return;
    mapRef.current?.getMap?.()?.dragPan?.disable?.();
    setDragA(coord); setDragB(coord);
  }, [drawBBoxEnabled, lassoOn]);

  const onDeckPointerMove = useCallback((evt) => {
    if (!(drawBBoxEnabled && !lassoOn)) return;
    if (!dragA) return;
    const shift = evt?.srcEvent?.shiftKey; if (!shift) return;
    evt.stopPropagation?.(); evt.preventDefault?.();
    const coord = evt?.coordinate; if (!coord) return;
    setDragB(coord);
  }, [drawBBoxEnabled, lassoOn, dragA]);

  const onDeckPointerUp = useCallback((evt) => {
    if (!(drawBBoxEnabled && !lassoOn)) return;
    const shift = evt?.srcEvent?.shiftKey; if (!shift) return;
    evt.stopPropagation?.(); evt.preventDefault?.();
    const map = mapRef.current?.getMap?.(); map?.dragPan?.enable?.();
    if (dragA && dragB) {
      const west = Math.min(dragA[0], dragB[0]);
      const east = Math.max(dragA[0], dragB[0]);
      const south = Math.min(dragA[1], dragB[1]);
      const north = Math.max(dragA[1], dragB[1]);
      if ((east - west) > DRAG_MIN_LL && (north - south) > DRAG_MIN_LL) {
        setLastBbox({ west, south, east, north });
        console.debug('[bbox] setLastBbox', { west, south, east, north });
      }
    }
    setDragA(null); setDragB(null);
  }, [drawBBoxEnabled, lassoOn, dragA, dragB, setLastBbox]);

  const dragRectFC = useMemo(() => {
    if (!(drawBBoxEnabled && dragA && dragB)) return null;
    const west = Math.min(dragA[0], dragB[0]);
    const east = Math.max(dragA[0], dragB[0]);
    const south = Math.min(dragA[1], dragB[1]);
    const north = Math.max(dragA[1], dragB[1]);
    return {
      type: 'FeatureCollection',
      features: [{
        type: 'Feature',
        properties: { _temp: true },
        geometry: { type: 'Polygon', coordinates: [[[west, south], [east, south], [east, north], [west, north], [west, south]]] }
      }]
    };
  }, [drawBBoxEnabled, dragA, dragB]);

  // Layers

  // waypoints (hidden if clusters are on)
  const waypointLayer = useMemo(() => {
    if (!waypointsVisible || waypoints.length === 0 || clustersOn) return null;

    const color = (t) => t === 'Depot' ? [80, 150, 255]
      : t === 'Delivery' ? [80, 220, 120]
        : t === 'Pickup' ? [255, 185, 60]
          : t === 'Backhaul' ? [255, 85, 85]
            : [180, 180, 180];

    return new ScatterplotLayer({
      id: 'waypoints',
      data: waypoints,
      dataComparator: (a, b) => a === b,           // only diff when array ref changes
      updateTriggers: { getFillColor: [/* no deps */] },
      getPosition: d => d.coordinates,
      getFillColor: d => color(d.type),
      radiusUnits: 'pixels',
      getRadius: 10,
      pickable: true,
      radiusMinPixels: 8,
      radiusMaxPixels: 24,
      onClick: (info) => {
        if (info.object) setHoveredWaypoint({ ...info.object, position: info.coordinate, screenX: info.x, screenY: info.y });
        else clearHoveredWaypoint();
      },
      parameters: { depthTest: false }
    });
  }, [waypoints, waypointsVisible, clustersOn, setHoveredWaypoint, clearHoveredWaypoint]);

  // geojson files
  const geoLayers = useMemo(() => {
    return GeojsonFiles
      .filter(f => f.visible && f?.data?.type === 'FeatureCollection' && Array.isArray(f?.data?.features))
      .map(file => new GeoJsonLayer({
        id: `geojson-${file.id}`,
        data: file.data,
        dataComparator: (a, b) => a === b,
        pickable: true, filled: true, stroked: true,
        getLineColor: [120, 160, 255],
        getFillColor: [80, 200, 160, 50],
        getLineWidth: 2,
        onClick: (info) => {
          if (info?.object) {
            setHoveredFeature({
              fileId: file.id,
              properties: info.object.properties,
              position: info.coordinate,
              screenX: info.x, screenY: info.y
            });
          }
        },
        parameters: { depthTest: false }
      }));
  }, [GeojsonFiles, setHoveredFeature]);

  // BBox editable
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
        console.debug('[bbox:two-click]', { west, south, east, north });
      },
      getLineColor: [0, 200, 120],
      getFillColor: [0, 200, 120, 60],
      lineWidthMinPixels: 2
    });
  }, [drawBBoxEnabled, lassoOn, setLastBbox]);

  // routes → ensure coords
  const routesForRender = useMemo(() => {
    if (!Array.isArray(routes) || routes.length === 0) return [];
    const byIdx = new (globalThis.Map)(wps.map((w, i) => [String(i), w.coordinates]));
    return routes.map((r, i) => {
      // 1) ensure solver coords from waypoint ids if missing
      let coords = Array.isArray(r.coords) && r.coords.length ? r.coords : [];
      if (!coords.length) {
        const ids = Array.isArray(r.waypointIds) ? r.waypointIds
          : Array.isArray(r.raw?.waypoint_ids) ? r.raw.waypoint_ids : [];
        coords = ids.map(id => {
          const n = Number(id);
          return Number.isFinite(n) ? byIdx.get(String(n)) : null;
        }).filter(Boolean);
      }

      // 2) base fallback: try decode/geojson from raw when available
      let displayCoords = null;
      try {
        displayCoords = coordsFromRawGeometry(r.raw) || coordsFromRawGeometry(r) || null;
      } catch { }

      // 3) active route override: prefer hook result (provider path)
      if (i === (currentIndex ?? 0) && Array.isArray(snappedCoords) && snappedCoords.length > 1) {
        displayCoords = snappedCoords;
      }

      return { ...r, coords, displayCoords };
    });
  }, [routes, wps, currentIndex, snappedCoords]);


  useEffect(() => {
    if (tripsOn) {
      setShowRoute(false);
      setPrevTraffic(trafficEnabled);
      setTrafficEnabled(false);
    } else {
      if (prevTraffic !== null) setTrafficEnabled(prevTraffic);
    }
    console.debug('[layer-policy] tripsOn=', tripsOn, {
      showRouteNext: !tripsOn,
      trafficWillBe: tripsOn ? false : (prevTraffic ?? trafficEnabled)
    });
  }, [tripsOn]); // eslint-disable-line react-hooks/exhaustive-deps

  const routeLayers = useMemo(() => {
    if (!routesForRender.length || tripsOn || !showRoute || solo === 'trips') return [];
    const dim = solo && solo !== 'route' ? 0.15 : 0.95;

    return routesForRender.map((r, idx) => {
      const path = (Array.isArray(r.displayCoords) && r.displayCoords.length)
        ? r.displayCoords
        : (Array.isArray(r.coords) ? r.coords : []);

      return new PathLayer({
        id: `route-${idx}`,
        data: [path],
        dataComparator: (a, b) => a === b,               // only diff on ref change
        updateTriggers: {
          getColor: [idx === currentIndex, dim],
          getWidth: [idx === currentIndex]
        },
        getPath: d => d,
        widthUnits: 'pixels',
        getWidth: (idx === currentIndex) ? 6 : 4,
        getColor: (idx === currentIndex)
          ? [0, 255, 255, Math.round(255 * dim)]
          : [0, 255, 255, Math.round(255 * (dim * 0.8))],
        capRounded: true, jointRounded: true,
        pickable: false,
        parameters: { depthTest: false }
      });
    });
  }, [routesForRender, currentIndex, showRoute, solo, tripsOn]);

  // DEBUG helpers (off)
  const DEBUG = false;
  const debugRouteLine = useMemo(() => {
    if (!DEBUG) return null;
    const r = getActiveRoute();
    if (!r?.coords?.length) return null;
    return new PathLayer({
      id: 'debug-route-line',
      data: [r.coords],
      getPath: d => d,
      getColor: [255, 255, 255, 160],
      widthUnits: 'pixels',
      getWidth: 2,
      parameters: { depthTest: false },
      capRounded: true,
      jointRounded: true
    });
  }, [routeVer, getActiveRoute, DEBUG]);
  const debugRouteDots = useMemo(() => {
    if (!DEBUG) return null;
    const r = getActiveRoute();
    if (!r?.coords?.length) return null;
    return new ScatterplotLayer({
      id: 'debug-route-dots',
      data: r.coords.map((c, i) => ({ coord: c, i })),
      getPosition: d => d.coord,
      getFillColor: [255, 255, 255],
      radiusUnits: 'pixels',
      getRadius: 2.5,
      parameters: { depthTest: false }
    });
  }, [routeVer, getActiveRoute, DEBUG]);

  const dragLayer = useMemo(() => {
    if (!dragRectFC) return null;
    return new GeoJsonLayer({
      id: 'bbox-drag-live',
      data: dragRectFC,
      stroked: true, filled: true,
      getLineColor: [255, 120, 120],
      getFillColor: [255, 120, 120, 60],
      lineWidthMinPixels: 2,
      pickable: false,
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

  const routeDots = useMemo(() => {
    const r = routesForRender?.[currentIndex];
    if (!r?.coords?.length) return null;
    return new ScatterplotLayer({
      id: 'route-vertex-dots',
      data: r.coords,
      getPosition: d => d,
      getFillColor: [255, 255, 255],
      radiusUnits: 'pixels',
      getRadius: 2.5,
      parameters: { depthTest: false }
    });
  }, [routesForRender, currentIndex]);

  const lassoLayer = useMemo(() => {
    if (!lassoOn) return null;
    return createLassoLayer({ waypoints, onSelect: (ids) => console.debug('[lasso] ids:', ids), setLastBbox });
  }, [lassoOn, waypoints, setLastBbox]);

  const etaTextLayer = useMemo(() => {
    const route = getActiveRoute();
    const coords = route?.coords, times = route?.etaEpoch, idxs = route?.etaIndices;
    if (!Array.isArray(coords) || !Array.isArray(times) || !Array.isArray(idxs)) return null;
    if (coords.length < 2 || times.length === 0 || idxs.length === 0) return null;
    const data = idxs.map((vi, k) => ({
      position: coords[vi],
      label: new Date((times[k + 1] ?? times[k] ?? times[0]) * 1000)
        .toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    }));
    const dim = solo && solo !== 'etas' ? 0.15 : 1;

    console.debug('[ETA Text]', {
      coords: coords?.length ?? 0, times: times?.length ?? 0, idxs: idxs?.length ?? 0, dim
    });
    return new TextLayer({
      id: 'eta-text',
      data,
      getPosition: d => d.position,
      getText: d => d.label,
      sizeUnits: 'pixels',
      getSize: 12,
      getColor: [240, 240, 240],
      background: true,
      getBackgroundColor: [0, 0, 0, 210],
      opacity: dim,
      parameters: { depthTest: false }
    });
  }, [routeVer, getActiveRoute, solo]);

  // Trips (animated)
  // robust RAF that can't double-start & stops at end
  const [currentTime, setCurrentTime] = useState(0);
  const rafRef = useRef(0);
  const runningRef = useRef(false);
  const totalDurRef = useRef(0); // set in tripsLayer memo

  useEffect(() => {
    // stop any previous loop
    runningRef.current = false;
    if (rafRef.current) cancelAnimationFrame(rafRef.current);

    if (!tripsOn) return;

    runningRef.current = true;
    const start = performance.now();

    const loop = (now) => {
      if (!runningRef.current) return;

      const t = (now - start) / 1000;
      const end = totalDurRef.current || 0;

      // stop at the true end and freeze the head there
      if (end && t >= end) {
        setCurrentTime(end);
        runningRef.current = false;
        if (rafRef.current) cancelAnimationFrame(rafRef.current);
        return;
      }

      setCurrentTime(t);
      rafRef.current = requestAnimationFrame(loop);
    };

    rafRef.current = requestAnimationFrame(loop);

    return () => {
      runningRef.current = false;
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [tripsOn]);


  // when computing renderable routes:
  console.debug('[routesForRender]', {
    count: routesForRender.length,
    currentIndex,
    currentCoords: routesForRender?.[currentIndex]?.coords?.length ?? 0
  });

  const tripsLayer = useMemo(() => {
    if (!tripsOn) return null;

    const route = getActiveRoute();
    const path = (route?.displayCoords && route.displayCoords.length)
      ? route.displayCoords
      : (route?.coords || []);
    if (!path.length) return null;

    // Prefer solver-provided per-vertex seconds ONLY if it matches the path length.
    // If we switched to displayCoords, recompute by distance so timing stays smooth.
    const useProvided = Array.isArray(route?.etaRelative)
      && route.etaRelative.length === path.length;

    const rel = useProvided ? route.etaRelative : relativeTimestampsFromCoords(path, 50);

    totalDurRef.current = Math.max(0, rel[rel.length - 1] || 0);
    const total = totalDurRef.current;
    const trail = total > 0 ? Math.min(12, Math.max(3, total * 0.5)) : 8;
    const dim = solo && solo !== 'trips' ? 0.15 : 0.95;

    console.debug('[Trips] build', {
      coords: path.length, relLen: rel.length, currentTime, total, trail, useProvided
    });

    return new TripsLayer({
      id: 'trips',
      data: [{ path, timestamps: rel, color: [190, 90, 255], width: 5 }],
      getPath: d => d.path,
      getTimestamps: d => d.timestamps,
      getColor: d => d.color,
      getWidth: d => d.width,
      currentTime,
      trailLength: trail,
      fadeTrail: true,
      widthUnits: 'pixels',
      opacity: dim,
      capRounded: true, jointRounded: true,
      parameters: { depthTest: false }
    });
  }, [tripsOn, currentTime, routeVer, getActiveRoute, solo]);

  // aggregate layers
  const layers = useMemo(() => {
    const L = [];
    if (DEBUG && debugRouteLine) L.push(debugRouteLine);
    if (DEBUG && debugRouteDots) L.push(debugRouteDots);
    if (waypointLayer) L.push(waypointLayer);
    L.push(...geoLayers);
    if (lassoLayer) L.push(lassoLayer);
    if (bboxEditableLayer) L.push(bboxEditableLayer);
    if (dragLayer) L.push(dragLayer);
    if (lastBboxLayer) L.push(lastBboxLayer);
    // Draw lines first…
    L.push(...routeLayers);     // static Deck line(s)
    if (tripsLayer) L.push(tripsLayer); // animated line (if enabled)
    // …then put labels on top
    if (etaTextLayer) L.push(etaTextLayer);
    // de-dup & log planned order
    const seen = new Set();
    const uniq = [];
    for (const lyr of L) {
      if (!lyr) continue;
      if (seen.has(lyr.id)) {
        console.warn('[layers] duplicate id skipped:', lyr.id);
        continue;
      }
      seen.add(lyr.id);
      uniq.push(lyr);
    }
    console.debug('[layers] order →', uniq.map(l => l.id));
    return uniq;
  }, [bboxEditableLayer, debugRouteLine, debugRouteDots, waypointLayer, geoLayers, lassoLayer, dragLayer, lastBboxLayer, etaTextLayer, tripsLayer, routeLayers]);

  // expose refs for debugging
  useEffect(() => {
    // deck instance
    window.__deck = () => deckRef.current?.deck;
    // list current layer IDs (from deck.gl)
    window.__layers = () =>
      deckRef.current?.deck?.props?.layers?.map(l => l.id);
    // list our computed layer IDs (pre-deck)
    window.__layersPlanned = () =>
      (layers || []).map(l => l?.id).filter(Boolean);
  }, [layers]);

  // clusters

  // fast builder (no extra allocations)
  function buildClusterFC(waypoints, visible) {
    if (!visible || !Array.isArray(waypoints) || waypoints.length === 0) {
      return { type: 'FeatureCollection', features: [] };
    }
    const features = new Array(waypoints.length);
    for (let i = 0; i < waypoints.length; i++) {
      const w = waypoints[i];
      features[i] = {
        type: 'Feature',
        geometry: { type: 'Point', coordinates: w.coordinates },
        properties: { id: w.id, type: w.type || 'Delivery' }
      };
    }
    return { type: 'FeatureCollection', features };
  }

  // memoized data blob — stable reference while inputs are unchanged
  const clusterData = useMemo(
    () => buildClusterFC(waypoints, waypointsVisible),
    [waypoints, waypointsVisible]
  );


  // Single controller; hide/show instead of destroying
  const clusterCtlRef = useRef(null);
  useEffect(() => {
    const map = mapRef.current?.getMap?.();
    if (!map || !mapLoaded) return;

    if (!clusterCtlRef.current) {
      clusterCtlRef.current = addClusteredSource(map, { id: 'wp-clusters', data: clusterData, clusterRadius: 40 });
    } else {
      clusterCtlRef.current.setData(clusterData);
    }

    clusterCtlRef.current.setVisibility(!!clustersOn);

    return () => {
      // Optional: keep clusters across page lifetime; if you prefer cleanup on unmount:
      clusterCtlRef.current?.remove();
      clusterCtlRef.current = null;
    };
  }, [mapLoaded, clustersOn, clusterData]);

  // (removed) cluster data is already driven by `clusterData` memo via setData(...)
  // map clicks
  useEffect(() => {
    const map = mapRef.current?.getMap?.();
    if (!map || !mapLoaded) return;

    const onMapClick = (ev) => {
      clearHoveredFeature(); clearHoveredWaypoint();

      if (clustersOn) {
        const feats = map.queryRenderedFeatures(ev.point);
        const f = feats?.find(ft => ft?.source === 'wp-clusters' && !ft?.properties?.cluster);
        if (f) {
          const id = f.properties.id;
          const wp = useWaypointStore.getState().waypoints.find(w => String(w.id) === String(id));
          if (wp) {
            setHoveredWaypoint({ ...wp, position: [ev.lngLat.lng, ev.lngLat.lat], screenX: ev.point.x, screenY: ev.point.y });
            return;
          }
        }
      }

      if (addOnClickEnabled && !(drawBBoxEnabled && dragA && dragB)) {
        addWaypoint({
          coordinates: [ev.lngLat.lng, ev.lngLat.lat],
          id: Date.now(), type: 'Delivery',
          demand: 1, capacity: 5, serviceTime: 10, timeWindow: [8, 17]
        });
      }
    };

    map.on('click', onMapClick);
    return () => map.off('click', onMapClick);
  }, [mapLoaded, clustersOn, addOnClickEnabled, drawBBoxEnabled, dragA, dragB, addWaypoint, clearHoveredFeature, clearHoveredWaypoint, setHoveredWaypoint]);

  // Deck click (two-click bbox & fallback add)
  const onDeckClick = useCallback((info) => {
    if (!info?.object) { clearHoveredFeature(); clearHoveredWaypoint(); }

    if (drawBBoxEnabled && !lassoOn && info?.coordinate) {
      const shift = info?.srcEvent?.shiftKey;
      if (!shift) {
        if (!twoClickA) {
          setTwoClickA(info.coordinate);
          setHoverCoord(info.coordinate);
          console.debug('[bbox] two-click: set A', info.coordinate);
        } else {
          const a = twoClickA, b = info.coordinate;
          const west = Math.min(a[0], b[0]);
          const east = Math.max(a[0], b[0]);
          const south = Math.min(a[1], b[1]);
          const north = Math.max(a[1], b[1]);
          if (Math.abs(east - west) > 1e-6 && Math.abs(north - south) > 1e-6) {
            setLastBbox({ west, south, east, north });
            console.debug('[bbox] two-click: box', { west, south, east, north });
          }
          setTwoClickA(null);
          setHoverCoord(null);
        }
        return;
      }
    }

    if (addOnClickEnabled && !drawBBoxEnabled && info?.coordinate) {
      const [lng, lat] = info.coordinate;
      addWaypoint({
        coordinates: [lng, lat],
        id: Date.now(),
        demand: 1,
        capacity: 5,
        serviceTime: 10,
        timeWindow: [8, 17],
        type: 'Delivery'
      });
    }
  }, [
    drawBBoxEnabled, lassoOn, twoClickA,
    addOnClickEnabled, addWaypoint,
    clearHoveredFeature, clearHoveredWaypoint, setLastBbox
  ]);

  // traffic
  // traffic
  const trafficCtlRef = useRef(null);
  useEffect(() => {
    const map = mapRef.current?.getMap?.();
    if (!map || !mapLoaded) return;

    const r = routesForRender?.[currentIndex] || {};
    const coords = Array.isArray(r?.displayCoords) && r.displayCoords.length
      ? r.displayCoords
      : (Array.isArray(r?.coords) ? r.coords : []);
    const opacity = solo && solo !== 'traffic' ? 0.15 : 0.6;

    if (!trafficEnabled || coords.length < 2) {
      trafficCtlRef.current?.remove();
      trafficCtlRef.current = null;
      return;
    }

    // Build gradient only if ETAs align with the chosen geometry
    let gradientStops = null;
    if (Array.isArray(r?.etaRelative) && r.etaRelative.length === coords.length) {
      gradientStops = buildGradientStops(coords, r.etaRelative, 16);
    }

    const line = {
      type: 'Feature',
      geometry: { type: 'LineString', coordinates: coords },
      properties: {},
    };

    if (!trafficCtlRef.current) {
      trafficCtlRef.current = addTrafficLine(map, {
        id: 'route-traffic',
        sourceId: 'route-traffic-src',
        routeData: line,
        width: 4,
        opacity,
        offset: 3,
        dashArray: [2, 1],
        solidColor: '#00FFFF',            // fallback
        useGradient: !!gradientStops,
        gradientStops,
      });
      trafficCtlRef.current.setOpacity(opacity);
      console.debug('[traffic] diagnostics after add:', trafficCtlRef.current.diagnostics());
    } else {
      trafficCtlRef.current.update(line, { gradientStops });
      trafficCtlRef.current.setOpacity(opacity);
      console.debug('[traffic] diagnostics after update:', trafficCtlRef.current.diagnostics());
    }

    return () => {
      trafficCtlRef.current?.remove();
      trafficCtlRef.current = null;
    };
  }, [mapLoaded, trafficEnabled, solo, routesForRender, currentIndex]);

  // native ETA glyphs
  const etaCtlRef = useRef(null);
  useEffect(() => {
    const map = mapRef.current?.getMap?.();
    if (!map || !mapLoaded) return;

    const getCoords = () => {
      const st = useRouteStore.getState();
      return st?.routes?.[st.currentIndex]?.coords || [];
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
  }, [etasEnabled, etaEveryMeters, etaSpeedKmh, mapLoaded, solo]);

  // render
  const initialView = storeView || { longitude: -73.985, latitude: 40.758, zoom: 12, bearing: 0, pitch: 0 };
  const deckController = useMemo(() => ({
    dragPan: !(drawBBoxEnabled || lassoOn),
    scrollZoom: true,
    doubleClickZoom: true,
    touchRotate: false,
    dragRotate: false,
  }), [drawBBoxEnabled, lassoOn]);

  return (
    <>
      {/* quick toggles */}
      <div className="absolute top-2 right-2 z-50 bg-black/80 text-white px-2 py-1 rounded shadow text-xs space-x-2">
        <label><input type="checkbox" checked={clustersOn} onChange={e => setClustersOn(e.target.checked)} /> Clusters</label>
        <label><input type="checkbox" checked={trafficEnabled} onChange={e => setTrafficEnabled(e.target.checked)} /> Traffic</label>
        <label><input type="checkbox" checked={lassoOn} onChange={e => setLassoOn(e.target.checked)} /> Lasso</label>
        <label>
          <input
            type="checkbox"
            checked={tripsOn}
            onChange={e => {
              const v = e.target.checked;
              console.debug('[ui] Trips toggled →', v);
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
              // If you’re focusing on Trips or Traffic, hide the static Deck route line
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

      <DeckGL
        ref={deckRef}
        initialViewState={initialView}
        controller={deckController}
        onViewStateChange={onDeckViewChange}
        onInteractionStateChange={onInteractionStateChange}
        useDevicePixels={1}
        layers={layers}
        onPointerDown={onDeckPointerDown}
        onPointerMove={onDeckPointerMove}
        onPointerUp={onDeckPointerUp}
        onClick={onDeckClick}
        style={{ position: 'absolute', inset: 0, cursor: (drawBBoxEnabled || lassoOn) ? 'crosshair' : 'grab' }}
      >
        <MapGL
          ref={mapRef}
          mapLib={maplibregl}
          mapStyle={MAP_STYLE}
          renderWorldCopies={true}
          fadeDuration={0}
          dragRotate={false}
          touchZoomRotate={false}
          style={{ position: 'absolute', inset: 0 }}
          onLoad={() => {
            setMapLoaded(true);
            const m = mapRef.current?.getMap?.();
            try { m.dragRotate?.disable(); } catch { }
            try { m.touchZoomRotate?.disableRotation(); } catch { }
          }}
        />
      </DeckGL>

      <ContextMenu
        mapRef={mapRef}
        items={[{
          label: 'Add waypoint here',
          className: 'text-blue-600',           // ← blue text
          onClick: ({ lng, lat }) => {
            try {
              const st = window?.useWaypointStore?.getState?.();
              const wp = {
                id: `ctx-${Date.now()}`,
                coordinates: [lng, lat],
                type: 'Delivery',
                demand: 1, capacity: 5, serviceTime: 10, timeWindow: [8, 17]
              };
              if (st?.setWaypointsVisible && st.waypointsVisible === false) st.setWaypointsVisible(true);
              st?.addWaypoint?.(wp);
            } catch (e) { console.error('[ctx] addWaypoint error', e); }
          }
        }]}
      />

      {/* popups */}
      {hoveredFeature?.position && (
        <div className="absolute bg-black/90 text-white p-2 rounded shadow-lg text-sm"
          style={{ left: `${hoveredFeature.screenX ?? 0}px`, top: `${hoveredFeature.screenY ?? 0}px`, transform: 'translate(10px, -100%)', pointerEvents: 'none', zIndex: 9999 }}>
          <pre className="whitespace-pre-wrap">{JSON.stringify(hoveredFeature.properties, null, 2)}</pre>
        </div>
      )}

      {hoveredWaypoint?.coordinates && (
        <div className="absolute bg-black/90 text-white p-2 rounded shadow-lg text-sm"
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
