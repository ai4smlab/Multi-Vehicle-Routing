import useWaypointStore from '@/hooks/useWaypointStore';
import { waypointsToFeatures, downloadAsGeoJSON } from '@/utils/geojsonExport';

export default function ExportGeoJSON() {
  const waypoints = useWaypointStore(s => s.waypoints);

  const exportGeoJSON = () => {
    const features = waypointsToFeatures(waypoints);
    if (!features.length) {
      alert('No waypoints to export.');
      return;
    }
    downloadAsGeoJSON('waypoints.geojson', features);
  };

  return (
    <button onClick={exportGeoJSON} className="text-xs px-3 py-1 bg-emerald-600 text-white rounded hover:bg-emerald-700 w-full mt-2">
      ⬇️ Export Waypoints (GeoJSON)
    </button>
  );
}
