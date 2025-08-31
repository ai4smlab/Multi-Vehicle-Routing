'use client';
import { useCallback, useState, memo } from 'react';
import useMapStore from '@/hooks/useMapStore';
import { parseInBatches } from '@loaders.gl/core';
import fitToFeatures from '@/components/map/fitToFeatures';
import { GeoJSONLoader } from '@loaders.gl/gis';
import { CSVLoader } from '@loaders.gl/csv';
import { WKTLoader } from '@loaders.gl/wkt';
import useVrpStore from '@/hooks/useVRPStore';
import useWaypointStore from '@/hooks/useWaypointStore';
import detectFeatureTypes from '@/components/data/detectFeatureTypes';

export default memo(FileUpload);

function FileUpload({ importOptions = {} }) {
  const [errors, setErrors] = useState([]);
  const addGeojsonFile = useVrpStore((s) => s.addGeojsonFile);
  const setViewState = useMapStore((s) => s.setViewState);
  const { autodetect, skipDuplicates, tagUntagged } = importOptions;

  const handleFiles = useCallback(async (event) => {
    setErrors([]);
    const files = Array.from(event.target.files);
    const GeojsonFiles = useVrpStore.getState().GeojsonFiles;
    const existingNames = new Set(GeojsonFiles.map(f => f.name));

    for (const file of files) {
      const fileId = Date.now() + Math.floor(Math.random() * 1000);
      if (skipDuplicates && existingNames.has(file.name)) {
        setErrors(prev => [...prev, `Skipped duplicate: ${file.name}`]);
        continue;
      }

      const ext = file.name.split('.').pop().toLowerCase();
      const mime = file.type;

      try {
        let allFeatures = [];

        if (ext === 'geojson' || ext === 'json' || mime.includes('geo+json')) {
          // --- GEOJSON ---
          const batches = await parseInBatches(file, GeoJSONLoader);
          for await (const batch of batches) {
            if (batch?.data) {
              const features = batch.data.features || batch.data || [];
              allFeatures.push(...features);
            }
          }
        } 
        else if (ext === 'csv' || mime.includes('csv')) {
          // --- CSV ---
          const batches = await parseInBatches(file, CSVLoader, {
            csv: { header: true }
          });
          for await (const batch of batches) {
            if (Array.isArray(batch?.data)) {
              const features = batch.data.map((row, idx) => {
                // Try WKT column first
                const wktValue = row.wkt || row.WKT || row.geometry;
                if (wktValue && typeof wktValue === 'string') {
                  try {
                    const geom = WKTLoader.parseTextSync(wktValue); // Parse WKT to GeoJSON
                    return {
                      type: 'Feature',
                      geometry: geom,
                      properties: { ...row, id: row.id ?? idx }
                    };
                  } catch {
                    return null;
                  }
                }

                // Fallback: Point from lat/lon
                const lat = parseFloat(row.lat ?? row.latitude);
                const lon = parseFloat(row.lon ?? row.longitude);
                if (isNaN(lat) || isNaN(lon)) return null;
                return {
                  type: 'Feature',
                  geometry: { type: 'Point', coordinates: [lon, lat] },
                  properties: { ...row, id: row.id ?? idx }
                };
              }).filter(Boolean);

              allFeatures.push(...features);
            }
          }
        } 
        else {
          setErrors(prev => [...prev, `Unsupported format: ${file.name}`]);
          continue;
        }

        if (!allFeatures.length) {
          setErrors(prev => [...prev, `No valid features found in ${file.name}`]);
          continue;
        }

        const { enrichedFeatures, fileTypes, detectedFeatures } =
          detectFeatureTypes(allFeatures, { ...importOptions, fileId });

        if (enrichedFeatures.length) {
          const fileData = {
            id: fileId,
            name: file.name,
            visible: true,
            fileTypes: fileTypes.length ? fileTypes : ['unknown'],
            data: { type: 'FeatureCollection', features: enrichedFeatures }
          };
          addGeojsonFile(fileData);
          fitToFeatures(enrichedFeatures, { setViewState });

          const addWaypoint = useWaypointStore.getState().addWaypoint;
          detectedFeatures.waypoints.forEach(f => {
            const coords = f.geometry.coordinates;
            const props = f.properties || {};
            addWaypoint({
              id: props.id ?? Date.now(),
              coordinates: coords,
              fileId,
              type: props.type ?? 'customer',
              demand: props.demand ?? 1,
              capacity: props.capacity ?? null,
              serviceTime: props.serviceTime ?? null,
              timeWindow: Array.isArray(props.timeWindow) ? props.timeWindow : null,
              pairId: props.pairId ?? null,
            });
          });
        }

      } catch (err) {
        setErrors(prev => [...prev, `Failed to load ${file.name}: ${err.message}`]);
      }
    }
  }, [addGeojsonFile, setViewState, importOptions, skipDuplicates]);

  return (
    <div className="p-2">
      <input
        type="file"
        accept=".geojson,.json,.csv,.kml,.gpx"
        multiple
        onChange={handleFiles}
        className="text-sm"
      />
      {errors.length > 0 && (
        <div className="text-red-600 mt-2 text-xs">
          {errors.map((e, i) => <div key={i}>{e}</div>)}
        </div>
      )}
    </div>
  );
}
