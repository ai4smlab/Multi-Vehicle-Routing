import { UI_WAYPOINTS_FILEID, UI_VEHICLES_FILEID } from '@/constants/fileIds';

// Waypoints -> GeoJSON Features
export function waypointsToFeatures(waypoints) {
  return (waypoints ?? []).map(wp => ({
    type: 'Feature',
    geometry: { type: 'Point', coordinates: wp.coordinates },
    properties: {
      id: wp.id,
      type: wp.type,
      demand: wp.demand,
      capacity: wp.capacity,
      serviceTime: wp.serviceTime,
      timeWindow: wp.timeWindow,
      pairId: wp.pairId,
      _fileId: wp.fileId ?? UI_WAYPOINTS_FILEID,
      _featureType: 'waypoint',
    },
  }));
}

// Vehicles -> GeoJSON Features (optionally place at depot point or leave geometry null)
export function vehiclesToFeatures(vehicles, depotLngLat = null) {
  return (vehicles ?? []).map(v => ({
    type: 'Feature',
    geometry: depotLngLat ? { type: 'Point', coordinates: depotLngLat } : null,
    properties: {
      id: v.id,
      name: v.name,
      capacity: v.capacity,
      speed: v.speed,
      startTime: v.startTime,
      endTime: v.endTime,
      costPerDistance: v.costPerDistance,
      costPerTime: v.costPerTime,
      _fileId: UI_VEHICLES_FILEID,
      _featureType: 'vehicle',
    },
  }));
}

// Merge imported + UI features in one place
export function collectAllFeatures({
  importedFiles = [],
  waypointFeatures = [],
  vehicleFeatures = [],
}) {
  const imported = importedFiles.flatMap(f => f?.data?.features ?? []);
  return [...imported, ...waypointFeatures, ...vehicleFeatures];
}

// Utility to download a FeatureCollection
export function downloadAsGeoJSON(filename, features) {
  const blob = new Blob(
    [JSON.stringify({ type: 'FeatureCollection', features }, null, 2)],
    { type: 'application/json' }
  );
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
