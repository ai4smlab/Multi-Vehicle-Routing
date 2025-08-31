// Lightweight manager for Real-World Dataset (RWD) layers on MapLibre
import type { Map } from 'mapbox-gl';

export const RWD_PREFIX = 'rwd-';
export const RWD_SRC_PREFIX = 'rwd-src-';

export function rwdIds(id: string) {
  const safe = String(id).replace(/[^a-zA-Z0-9_-]/g, '_');
  return {
    src: `${RWD_SRC_PREFIX}${safe}`,
    pts: `${RWD_PREFIX}pts-${safe}`,
    labels: `${RWD_PREFIX}labels-${safe}`,
  };
}

export function addRwdPoints(map: Map, id: string, fc: any, opts?: {
  circleColor?: string; circleRadius?: number; textField?: string; textSize?: number;
}) {
  const { src, pts, labels } = rwdIds(id);
  const circleColor = opts?.circleColor ?? '#22d3ee';
  const circleRadius = Number.isFinite(opts?.circleRadius) ? Number(opts!.circleRadius) : 4;
  const textField = opts?.textField ?? ['coalesce', ['get', 'name'], ['get', 'amenity'], ''];
  const textSize = Number.isFinite(opts?.textSize) ? Number(opts!.textSize) : 11;

  // source
  if (!map.getSource(src)) {
    map.addSource(src, { type: 'geojson', data: fc });
  } else {
    (map.getSource(src) as any).setData(fc);
  }

  // circle layer
  if (!map.getLayer(pts)) {
    map.addLayer({
      id: pts,
      type: 'circle',
      source: src,
      metadata: { rwd: true },
      paint: {
        'circle-color': circleColor,
        'circle-radius': circleRadius,
        'circle-stroke-color': '#0f172a',
        'circle-stroke-width': 1
      }
    });
  }

  // labels (optional, only if any names exist)
  if (!map.getLayer(labels)) {
    map.addLayer({
      id: labels,
      type: 'symbol',
      source: src,
      metadata: { rwd: true },
      layout: {
        'text-field': textField as any,
        'text-size': textSize,
        'text-offset': [0, 0.9]
      },
      paint: {
        'text-color': '#e5e7eb',
        'text-halo-color': '#0f172a',
        'text-halo-width': 1
      }
    });
  }
}

export function updateRwdData(map: Map, id: string, fc: any) {
  const { src } = rwdIds(id);
  const s = map.getSource(src) as any;
  if (s?.setData) s.setData(fc);
}

export function setRwdVisibility(map: Map, id: string, visible: boolean) {
  const { pts, labels } = rwdIds(id);
  const v = visible ? 'visible' : 'none';
  if (map.getLayer(pts)) map.setLayoutProperty(pts, 'visibility', v);
  if (map.getLayer(labels)) map.setLayoutProperty(labels, 'visibility', v);
}

export function removeRwd(map: Map, id: string) {
  const { src, pts, labels } = rwdIds(id);
  if (map.getLayer(labels)) map.removeLayer(labels);
  if (map.getLayer(pts)) map.removeLayer(pts);
  if (map.getSource(src)) map.removeSource(src);
}

export function removeAllRwdFrom(map: Map) {
  if (!map?.getStyle) return;
  const style = map.getStyle();
  const layerIds = (style.layers ?? []).map(l => l.id);

  // Remove all RWD layers first
  for (const id of layerIds) {
    if (id.startsWith(RWD_PREFIX)) {
      try { map.removeLayer(id); } catch {}
    }
  }

  // Then remove all RWD sources
  const srcObj = style.sources ?? {};
  for (const sid of Object.keys(srcObj)) {
    if (sid.startsWith(RWD_SRC_PREFIX) || sid.startsWith(RWD_PREFIX)) {
      try { map.removeSource(sid); } catch {}
    }
  }
}
