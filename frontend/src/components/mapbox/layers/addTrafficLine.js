// src/components/mapbox/layers/addTrafficLine.js
export function addTrafficLine(
  map,
  {
    id = 'route-traffic',
    sourceId = 'route-traffic-src',
    routeData,        // { type:'Feature', geometry:{ LineString } }
    width = 4,
    opacity = 0.6,
    offset = 0,
    dashArray = null,
    solidColor = '#00FFFF',
    useGradient = false,
    gradientStops = null, // [{ t:0..1, color:'#RRGGBB' }, ...]
  }
) {
  const fc = { type: 'FeatureCollection', features: [routeData] };

  if (!map.getSource(sourceId)) {
    map.addSource(sourceId, {
      type: 'geojson',
      lineMetrics: true,            // REQUIRED for line-gradient
      data: fc,
    });
  } else {
    map.getSource(sourceId).setData(fc);
  }

  if (!map.getLayer(id)) {
    map.addLayer({
      id,
      type: 'line',
      source: sourceId,
      layout: {
        'line-cap': 'round',
        'line-join': 'round',
        'visibility': 'visible',
      },
      paint: {
        'line-width': width,
        'line-opacity': opacity,
        'line-offset': offset,
        'line-color': solidColor,   // fallback when no gradient
      },
    });
    if (dashArray) map.setPaintProperty(id, 'line-dasharray', dashArray);
  }

  const toGradientExpr = (stops) => {
    const expr = ['interpolate', ['linear'], ['line-progress']];
    for (const s of stops) {
      expr.push(Math.max(0, Math.min(1, s.t)));
      expr.push(s.color);
    }
    return expr;
  };

  const applyGradient = (stops) => {
    if (useGradient && Array.isArray(stops) && stops.length >= 2) {
      map.setPaintProperty(id, 'line-gradient', toGradientExpr(stops));
    } else {
      try { map.setPaintProperty(id, 'line-gradient', null); } catch {}
      map.setPaintProperty(id, 'line-color', solidColor);
    }
  };

  applyGradient(gradientStops);

  return {
    update(newFeature, { gradientStops: gs } = {}) {
      const s = map.getSource(sourceId);
      if (s) s.setData({ type: 'FeatureCollection', features: [newFeature] });
      if (gs !== undefined) applyGradient(gs);
    },
    setOpacity(v) { map.setPaintProperty(id, 'line-opacity', v); },
    setVisibility(v) { map.setLayoutProperty(id, 'visibility', v ? 'visible' : 'none'); },
    remove() { try { map.removeLayer(id); } catch {} try { map.removeSource(sourceId); } catch {} },
    diagnostics() {
      return {
        exists: !!map.getLayer(id),
        gradient: !!map.getPaintProperty(id, 'line-gradient'),
        color: map.getPaintProperty(id, 'line-color'),
        opacity: map.getPaintProperty(id, 'line-opacity'),
        dash: map.getPaintProperty(id, 'line-dasharray'),
        offset: map.getPaintProperty(id, 'line-offset'),
      };
    },
  };
}
