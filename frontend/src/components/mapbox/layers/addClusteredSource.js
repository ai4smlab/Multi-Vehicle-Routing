// components/mapbox/layers/addClusteredSource.js

/* Idempotent clustered source + 3 layers controller.
 * Reuses the source/layers, supports hide/show, and debounces setData.
 */
export function addClusteredSource(
  map,
  { id, data, clusterRadius = 40, beforeId } = {}
) {
  if (!map) return noop();

  const SRC = id;
  const L_CLUSTERS = `${id}-clusters`;
  const L_COUNT = `${id}-cluster-count`;
  const L_UNCL = `${id}-unclustered`;

  let raf = 0;
  let pending = null;

  const ensure = () => {
    // 1) source
    if (!map.getSource(SRC)) {
      map.addSource(SRC, {
        type: 'geojson',
        // promoteId helps diffing when properties.id exists
        // (not required for clustering, but harmless)
        promoteId: 'id',
        data: data || emptyFC(),
        cluster: true,
        clusterRadius,
        // keep defaults (clusterMaxZoom etc.)
      });
    } else if (data) {
      // initial data for first call if source existed
      try { map.getSource(SRC).setData(data); } catch { }
    }

    // 2) layers (add once)
    if (!map.getLayer(L_CLUSTERS)) {
      map.addLayer({
        id: L_CLUSTERS,
        type: 'circle',
        source: SRC,
        filter: ['has', 'point_count'],
        paint: {
          'circle-radius': ['step', ['get', 'point_count'], 16, 50, 22, 200, 30],
          'circle-color': ['step', ['get', 'point_count'], '#9ecae1', 50, '#6baed6', 200, '#2171b5'],
          'circle-stroke-color': '#fff',
          'circle-stroke-width': 1
        }
      }, beforeId || undefined);
    }

    if (!map.getLayer(L_COUNT)) {
      map.addLayer({
        id: L_COUNT,
        type: 'symbol',
        source: SRC,
        filter: ['has', 'point_count'],
        layout: { 'text-field': ['get', 'point_count_abbreviated'], 'text-size': 12 },
        paint: { 'text-color': '#073b4c' }
      }, beforeId || undefined);
    }

    if (!map.getLayer(L_UNCL)) {
      map.addLayer({
        id: L_UNCL,
        type: 'circle',
        source: SRC,
        filter: ['!', ['has', 'point_count']],
        paint: {
          'circle-radius': 6,
          'circle-color': '#34d399',
          'circle-stroke-color': '#fff',
          'circle-stroke-width': 1
        }
      }, beforeId || undefined);
    }
  };

  const setVisibility = (visible) => {
    const v = visible ? 'visible' : 'none';
    [L_CLUSTERS, L_COUNT, L_UNCL].forEach((lid) => {
      if (map.getLayer(lid)) map.setLayoutProperty(lid, 'visibility', v);
    });
  };

  const setData = (nextData) => {
    pending = nextData || emptyFC();
    if (raf) return; // collapse multiple calls into one frame
    raf = requestAnimationFrame(() => {
      raf = 0;
      try {
        const src = map.getSource(SRC);
        if (src) src.setData(pending);
      } catch (e) {
        // if the style reloaded, re-ensure and retry once
        try { ensure(); map.getSource(SRC)?.setData(pending); } catch { }
      }
      pending = null;
    });
  };

  const remove = () => {
    try { if (raf) cancelAnimationFrame(raf); } catch { }
    [L_CLUSTERS, L_COUNT, L_UNCL].forEach((lid) => {
      try { if (map.getLayer(lid)) map.removeLayer(lid); } catch { }
    });
    try { if (map.getSource(SRC)) map.removeSource(SRC); } catch { }
  };

  const diagnostics = () => ({
    src: !!map.getSource(SRC),
    layers: [L_CLUSTERS, L_COUNT, L_UNCL].filter((l) => !!map.getLayer(l)),
    featuresQueued: pending?.features?.length || 0
  });

  // Ensure immediately (idempotent)
  ensure();

  // Initial data push if provided
  if (data) setData(data);

  // Back-compat: expose `update` as an alias of `setData`
  return { setData, update: setData, setVisibility, remove, diagnostics };
}

function emptyFC() { return { type: 'FeatureCollection', features: [] }; }
function noop() { return { setData() { }, setVisibility() { }, remove() { }, diagnostics() { return {}; } }; }
