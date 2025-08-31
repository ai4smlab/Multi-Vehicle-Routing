import { EditableGeoJsonLayer, DrawPolygonMode } from '@deck.gl-community/editable-layers';
import bboxPolygon from '@turf/bbox-polygon';
import booleanPointInPolygon from '@turf/boolean-point-in-polygon';

export function createLassoLayer({ waypoints, onSelect, setLastBbox }) {
  return new EditableGeoJsonLayer({
    id: 'lasso-select',
    data: { type:'FeatureCollection', features: [] },
    mode: DrawPolygonMode,
    selectedFeatureIndexes: [],
    getLineColor: [120, 120, 255],
    getFillColor: [120, 120, 255, 60],
    lineWidthMinPixels: 2,
    onEdit: ({ updatedData, editType }) => {
      const poly = updatedData?.features?.slice(-1)[0];
      if (!poly) return;
      const selected = [];
      waypoints.forEach(w => {
        const pt = { type:'Feature', geometry:{ type:'Point', coordinates:w.coordinates } };
        if (booleanPointInPolygon(pt, poly)) selected.push(w.id);
      });
      onSelect?.(selected);

      // (optional) also set lastBbox from polygon bbox so the rest of your app can reuse it
      const ring = poly.geometry.coordinates[0];
      const lons = ring.map(p => p[0]), lats = ring.map(p => p[1]);
      setLastBbox?.({ west: Math.min(...lons), south: Math.min(...lats), east: Math.max(...lons), north: Math.max(...lats) });
    }
  });
}
