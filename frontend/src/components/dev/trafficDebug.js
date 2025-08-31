// components/mapbox/debug/trafficDebug.js
/* eslint-disable no-console */

function haversineMeters([lng1, lat1], [lng2, lat2]) {
  const R = 6371000;
  const toRad = d => (d * Math.PI) / 180;
  const dLat = toRad(lat2 - lat1);
  const dLng = toRad(lng2 - lng1);
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLng / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(a));
}

function totalLengthMeters(coords = []) {
  let sum = 0;
  for (let i = 1; i < coords.length; i++) sum += haversineMeters(coords[i - 1], coords[i]);
  return sum;
}

/**
 * Attach debug helpers & a probe tooltip for a MapLibre traffic layer.
 * @param {import('maplibre-gl').Map} map
 * @param {{layerId?:string, sourceId?:string, enableProbe?:boolean}} opts
 * @returns {{detach:Function, log:Function, printPaint:Function, printSource:Function, countCoords:Function}}
 */
export function attachTrafficDebug(map, opts = {}) {
  const layerId = opts.layerId || 'route-traffic';
  let sourceId = opts.sourceId || null;
  const enableProbe = opts.enableProbe ?? true;

  const layer = map.getLayer(layerId);
  if (!layer) {
    console.warn('[trafficDebug] layer not found:', layerId);
  } else {
    sourceId = sourceId || layer.source;
  }

  const src = sourceId ? map.getSource(sourceId) : null;
  if (!src) {
    console.warn('[trafficDebug] source not found:', sourceId);
  }

  // ---- Debug utils you can call in DevTools ----
  const log = () => {
    const lyr = map.getLayer(layerId);
    const sid = lyr?.source;
    const s = sid ? map.getSource(sid) : null;
    const paint = lyr
      ? {
          'line-color': map.getPaintProperty(layerId, 'line-color'),
          'line-gradient': map.getPaintProperty(layerId, 'line-gradient'),
          'line-width': map.getPaintProperty(layerId, 'line-width'),
          'line-opacity': map.getPaintProperty(layerId, 'line-opacity'),
        }
      : null;

    // Try to get GeoJSON data (non-public but fine for debugging)
    let coordsCount = null;
    let totalM = null;
    try {
      const data = s?._data || s?.serialize?.()?.data;
      const geom = data?.geometry || data?.features?.[0]?.geometry;
      const coords = geom?.coordinates;
      if (Array.isArray(coords)) {
        const line = geom.type === 'LineString' ? coords : null;
        if (line) {
          coordsCount = line.length;
          totalM = totalLengthMeters(line);
        }
      }
    } catch {}

    console.info('[trafficDebug] layer/source:', {
      layerExists: !!lyr,
      layerId,
      sourceId: sid,
      sourceExists: !!s,
      paint,
      coordsCount,
      totalMeters: totalM != null ? Math.round(totalM) : null,
    });
  };

  const printPaint = () => {
    if (!map.getLayer(layerId)) return console.warn('[trafficDebug] no layer', layerId);
    console.log('[trafficDebug] paint', {
      'line-color': map.getPaintProperty(layerId, 'line-color'),
      'line-gradient': map.getPaintProperty(layerId, 'line-gradient'),
      'line-width': map.getPaintProperty(layerId, 'line-width'),
      'line-opacity': map.getPaintProperty(layerId, 'line-opacity'),
    });
  };

  const printSource = () => {
    const lyr = map.getLayer(layerId);
    if (!lyr) return console.warn('[trafficDebug] no layer', layerId);
    const sid = lyr.source;
    const s = map.getSource(sid);
    if (!s) return console.warn('[trafficDebug] no source', sid);
    try {
      const data = s?._data || s?.serialize?.()?.data;
      console.log('[trafficDebug] source data (first 1k chars):',
        typeof data === 'string' ? data.slice(0, 1000) : data);
    } catch (e) {
      console.warn('[trafficDebug] cannot read source data', e);
    }
  };

  const countCoords = () => {
    const lyr = map.getLayer(layerId);
    const s = lyr ? map.getSource(lyr.source) : null;
    try {
      const data = s?._data || s?.serialize?.()?.data;
      const geom = data?.geometry || data?.features?.[0]?.geometry;
      const coords = geom?.coordinates;
      const count = Array.isArray(coords) ? coords.length : 0;
      console.log('[trafficDebug] coord count =', count);
      return count;
    } catch {
      console.log('[trafficDebug] coord count = unknown');
      return null;
    }
  };

  // ---- Probe tooltip over the line layer ----
  let probeEl = null;
  let onEnter, onLeave, onMove;

  if (enableProbe && map.getLayer(layerId)) {
    // Create a small tooltip div inside the map container
    const container = map.getContainer();
    probeEl = document.createElement('div');
    probeEl.style.position = 'absolute';
    probeEl.style.pointerEvents = 'none';
    probeEl.style.background = 'rgba(0,0,0,0.8)';
    probeEl.style.color = 'white';
    probeEl.style.padding = '4px 6px';
    probeEl.style.borderRadius = '6px';
    probeEl.style.fontSize = '11px';
    probeEl.style.zIndex = '1000';
    probeEl.style.display = 'none';
    container.appendChild(probeEl);

    onEnter = () => { container.style.cursor = 'crosshair'; };
    onLeave = () => {
      container.style.cursor = '';
      if (probeEl) probeEl.style.display = 'none';
    };
    onMove = (e) => {
      if (!e?.point || !e?.lngLat) return;
      const f = e.features?.[0];
      const props = f?.properties || {};
      // If your addTrafficLine writes e.g. speed_kph into properties, show it.
      // Otherwise we show lng/lat only.
      const speed = props.speed_kph ?? props.speed ?? props.v ?? null;

      probeEl.style.left = `${e.point.x + 10}px`;
      probeEl.style.top = `${e.point.y - 10}px`;
      probeEl.style.display = 'block';
      probeEl.innerHTML = speed != null
        ? `lng: ${e.lngLat.lng.toFixed(5)}<br/>lat: ${e.lngLat.lat.toFixed(5)}<br/><b>speed:</b> ${Number(speed).toFixed(1)} kph`
        : `lng: ${e.lngLat.lng.toFixed(5)}<br/>lat: ${e.lngLat.lat.toFixed(5)}<br/><i>no speed property</i>`;
    };

    map.on('mouseenter', layerId, onEnter);
    map.on('mouseleave', layerId, onLeave);
    map.on('mousemove', layerId, onMove);
  }

  // Expose in window for quick debugging
  if (!window.trafficDebug) window.trafficDebug = {};
  window.trafficDebug[layerId] = { log, printPaint, printSource, countCoords };

  // Print an initial snapshot
  log();

  return {
    detach() {
      try {
        if (onEnter) map.off('mouseenter', layerId, onEnter);
        if (onLeave) map.off('mouseleave', layerId, onLeave);
        if (onMove) map.off('mousemove', layerId, onMove);
      } catch {}
      if (probeEl?.parentNode) probeEl.parentNode.removeChild(probeEl);
      delete window.trafficDebug?.[layerId];
    },
    log,
    printPaint,
    printSource,
    countCoords,
  };
}
