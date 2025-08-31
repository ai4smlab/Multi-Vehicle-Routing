export default function detectFeatureTypes(features, { autodetect = true, tagUntagged = true, fileId = null } = {}) {
  const fileTypes = new Set();
  const detectedFeatures = {
    waypoints: [],
    vehicles: [],
    maps: [],
  };

  features.forEach((feature, i) => {
    if (!feature.properties) feature.properties = {};

    const source = feature.properties.source?.toLowerCase();

    if (['waypoint', 'vehicle', 'map'].includes(source)) {
      fileTypes.add(source);
      detectedFeatures[source + 's']?.push(feature);
    } else if (autodetect) {
      // Autodetect logic
      if (feature.geometry?.type === 'Point' && feature.properties?.demand !== undefined) {
        feature.properties.source = 'waypoint';
        fileTypes.add('waypoint');
        detectedFeatures.waypoints.push(feature);
      } else {
        feature.properties.source = 'map';
        fileTypes.add('map');
        detectedFeatures.maps.push(feature);
      }
    } else if (tagUntagged) {
      feature.properties.source = 'map';
      fileTypes.add('map');
      detectedFeatures.maps.push(feature);
    } else {
      fileTypes.add('unknown');
    }
  });

  return {
    enrichedFeatures: features,
    fileTypes: [...fileTypes],
    detectedFeatures,
  };
}
