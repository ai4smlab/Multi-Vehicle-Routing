// components/sidebar/RealWorldDatasetPanel.js
'use client';

import { useMemo, useState } from 'react';
import Section from '@/components/sidebar/Section';
import { usePois, usePoisAuto } from '@/hooks/useBackend';
import useMapStore from '@/hooks/useMapStore';
import fitToFeatures from '@/components/map/fitToFeatures';
import useUiStore from '@/hooks/useUIStore';

import {
  addRwdPoints,
  updateRwdData,
  setRwdVisibility,
  removeRwd,
  removeAllRwdFrom,
} from '@/components/map/rwdManager';

/* ---------------- helpers ---------------- */

function getMap() {
  // prefer MapLibreComponent’s helper if you added it
  if (typeof window !== 'undefined' && typeof window.__getMap === 'function') {
    try { return window.__getMap(); } catch { /* noop */ }
  }
  // fallback via DeckGL debug handle
  try { return window.__deck?.()?.props?.map?.getMap?.(); } catch { /* noop */ }
  return null;
}

function makeRwdId({ place, bbox, key, value }) {
  const base = place
    ? `place-${place}-${key}-${value}`
    : bbox
      ? `bbox-${bbox.south}-${bbox.west}-${bbox.north}-${bbox.east}-${key}-${value}`
      : `rwd-${Date.now()}`;
  // keep only [A-Za-z0-9_-]
  return base.replace(/[^A-Za-z0-9_-]+/g, '-').slice(0, 80);
}

/** Accept {west,south,east,north} or {minLon,minLat,maxLon,maxLat} */
function normalizeBbox(box) {
  if (!box) return null;
  const west  = Number.isFinite(box.west)  ? box.west  : box.minLon;
  const south = Number.isFinite(box.south) ? box.south : box.minLat;
  const east  = Number.isFinite(box.east)  ? box.east  : box.maxLon;
  const north = Number.isFinite(box.north) ? box.north : box.maxLat;
  if ([west, south, east, north].every(Number.isFinite)) return { west, south, east, north };
  return null;
}

/** Keep user’s raw string; backend normalizes/quotes/regex as needed */
function normalizeOsmValueForBackend(v) { return (v ?? '').toString().trim(); }

/* ---------------- component ---------------- */

export default function RealWorldDatasetPanel() {
  const setViewState = useMapStore(s => s.setViewState);
  const {
    drawBBoxEnabled, setDrawBBoxEnabled,
    lastBbox: lastBboxRaw, clearLastBbox
  } = useUiStore();

  const lastBbox = normalizeBbox(lastBboxRaw);

  // Saved datasets managed in-panel:
  // { id, name, fc, rwdId, visible }
  const [datasets, setDatasets] = useState([]);
  // Track the current search layer’s rwdId (if loaded)
  const [currentRwdId, setCurrentRwdId] = useState(null);

  // ---- Inputs ----
  const [mode, setMode] = useState('place'); // 'place' | 'bbox'
  const [place, setPlace] = useState('Paris, France');
  const [featureKey, setFeatureKey] = useState('amenity');
  const [featureValue, setFeatureValue] = useState('restaurant|cafe');
  const [bboxInputs, setBboxInputs] = useState({ minLon: '', minLat: '', maxLon: '', maxLat: '' });
  const [limit, setLimit] = useState(500);

  // Build query only when Search pressed
  const [params, setParams] = useState(null);

  const normalizedValue = useMemo(() => normalizeOsmValueForBackend(featureValue), [featureValue]);

  // API calls (conditionally enabled)
  const autoQ = usePoisAuto(
    params?.mode === 'place'
      ? {
          place: params?.place,
          key: params?.key,
          value: params?.value,
          limit: params?.limit,
          include_ways: true,
          include_relations: true,
        }
      : null
  );

  const bboxQ = usePois(
    params?.mode === 'bbox'
      ? {
          south: params?.south, west: params?.west, north: params?.north, east: params?.east,
          key: params?.key, value: params?.value, limit: params?.limit
        }
      : null
  );

  const data = params?.mode === 'place' ? autoQ.data : bboxQ.data;
  const isFetching = params?.mode === 'place' ? autoQ.isFetching : bboxQ.isFetching;
  const isError = params?.mode === 'place' ? autoQ.isError : bboxQ.isError;
  const error = params?.mode === 'place' ? autoQ.error : bboxQ.error;

  const featureCollection = useMemo(() => {
    const d = data;
    if (!d) return null;
    if (d?.type === 'FeatureCollection') return d;
    if (d?.data?.geojson?.type === 'FeatureCollection') return d.data.geojson;
    if (d?.data?.type === 'FeatureCollection') return d.data;
    return null;
  }, [data]);

  const features = featureCollection?.features ?? [];

  // ----- Helpers -----
  const useDrawnBbox = () => {
    const bb = normalizeBbox(lastBboxRaw);
    if (!bb) return;
    setMode('bbox');
    setBboxInputs({
      minLon: String(bb.west),
      minLat: String(bb.south),
      maxLon: String(bb.east),
      maxLat: String(bb.north),
    });
    console.debug('[RWDS] useDrawnBbox → inputs', bb);
  };

  const buildBboxParams = () => {
    const bb = normalizeBbox(lastBboxRaw);
    if (bb) return { south: bb.south, west: bb.west, north: bb.north, east: bb.east };

    // fallback to manual
    const minLon = Number(bboxInputs.minLon);
    const minLat = Number(bboxInputs.minLat);
    const maxLon = Number(bboxInputs.maxLon);
    const maxLat = Number(bboxInputs.maxLat);
    if (![minLon, minLat, maxLon, maxLat].every(Number.isFinite)) return null;
    if (minLon >= maxLon || minLat >= maxLat) return null;
    return { south: minLat, west: minLon, north: maxLat, east: maxLon };
  };

  const onSearch = () => {
    const key = featureKey.trim();
    const value = normalizedValue;
    if (!key || !value) { alert('Enter key and value'); return; }

    if (mode === 'place') {
      const q = (place || '').trim();
      if (!q) { alert('Enter a place name'); return; }
      const next = { mode: 'place', place: q, key, value, limit };
      console.log('[RWDS] SEARCH place →', next);
      setParams(next);
    } else {
      const bb = buildBboxParams();
      if (!bb) { alert('Invalid bbox'); return; }
      const next = { mode: 'bbox', ...bb, key, value, limit };
      console.log('[RWDS] SEARCH bbox →', next);
      setParams(next);
    }
  };

  const clearCurrentSearch = () => {
    setParams(null);
    // If current search is loaded to map via rwdManager → remove
    if (currentRwdId) {
      const map = getMap();
      if (map) removeRwd(map, currentRwdId);
      setCurrentRwdId(null);
    }
  };

  const zoomTo = (fc) => {
    const feats = fc?.features ?? [];
    if (!feats.length) return;
    fitToFeatures(feats, { setViewState });
  };

  const onLoadCurrent = () => {
    if (!featureCollection) return;

    const map = getMap();
    if (!map) { alert('Map not ready'); return; }

    const bb = normalizeBbox(lastBboxRaw);
    const name =
      params?.mode === 'place'
        ? `OSM POIs: ${params.place} (${params.key}=${params.value})`
        : `OSM POIs BBox (${(params?.west ?? bb?.west ?? +bboxInputs.minLon).toFixed?.(3)},${(params?.south ?? bb?.south ?? +bboxInputs.minLat).toFixed?.(3)}→${(params?.east ?? bb?.east ?? +bboxInputs.maxLon).toFixed?.(3)},${(params?.north ?? bb?.north ?? +bboxInputs.maxLat).toFixed?.(3)}) ${params.key}=${params.value}`;

    const rwdId = makeRwdId({
      place: params?.mode === 'place' ? params.place : null,
      bbox: params?.mode === 'bbox' ? { south: params.south, west: params.west, north: params.north, east: params.east } : null,
      key: params?.key,
      value: params?.value
    });

    // If already added under this id → update data; else add
    try {
      if (map.getSource(`rwd-src-${rwdId}`)) {
        updateRwdData(map, rwdId, featureCollection);
      } else {
        addRwdPoints(map, rwdId, featureCollection, {
          circleColor: '#22d3ee',
          circleRadius: 4,
          textField: ['coalesce', ['get','name'], ['get','amenity'], ''],
          textSize: 11
        });
      }
      setRwdVisibility(map, rwdId, true);
      setCurrentRwdId(rwdId);
      zoomTo(featureCollection);
    } catch (e) {
      console.error('[RWDS] load current failed', e);
      alert('Could not add dataset to map.');
    }
  };

  const onRemoveCurrentLayer = () => {
    if (!currentRwdId) return;
    const map = getMap();
    if (map) removeRwd(map, currentRwdId);
    setCurrentRwdId(null);
  };

  const onSaveDataset = () => {
    if (!featureCollection) return;
    const bb = normalizeBbox(lastBboxRaw);
    const name =
      params?.mode === 'place'
        ? `OSM: ${params.place} (${params.key}=${params.value})`
        : `OSM BBox (${(params?.west ?? bb?.west ?? +bboxInputs.minLon).toFixed?.(3)},${(params?.south ?? bb?.south ?? +bboxInputs.minLat).toFixed?.(3)}→${(params?.east ?? bb?.east ?? +bboxInputs.maxLon).toFixed?.(3)},${(params?.north ?? bb?.north ?? +bboxInputs.maxLat).toFixed?.(3)}) ${params.key}=${params.value}`;

    const rwdId = makeRwdId({
      place: params?.mode === 'place' ? params.place : null,
      bbox: params?.mode === 'bbox' ? { south: params.south, west: params.west, north: params.north, east: params.east } : null,
      key: params?.key,
      value: params?.value
    });

    setDatasets(prev => [{ id: `ds-${Date.now()}`, name, fc: featureCollection, rwdId, visible: false }, ...prev]);
  };


const toggleSavedLoad = (id) => {
  const map = getMap();
  if (!map) { alert('Map not ready'); return; }

  setDatasets(prev => prev.map(item => {
    if (item.id !== id) return item;

    try {
      if (item.visible) {
        // HIDE by removing layers
        removeRwd(map, item.rwdId);
        return { ...item, visible: false };
      }

      // SHOW by (re)adding the layers
      addRwdPoints(map, item.rwdId, item.fc, {
        circleColor: '#f59e0b',
        circleRadius: 4,
        textField: ['coalesce', ['get','name'], ['get','amenity'], ''],
        textSize: 11
      });
      return { ...item, visible: true };
    } catch (e) {
      console.error('[RWDS] toggle saved failed', e);
      return item;
    }
  }));
};

  const removeDataset = (id) => {
    const map = getMap();
    setDatasets(prev => {
      const item = prev.find(d => d.id === id);
      if (map && item?.rwdId) {
        try { removeRwd(map, item.rwdId); } catch { /* noop */ }
      }
      return prev.filter(d => d.id !== id);
    });
  };

  // clear ALL RWD layers currently on the map (fixes your “doesn’t clear” case)
  const clearAllRwdLayers = () => {
    const map = getMap();
    if (map) {
      try { removeAllRwdFrom(map); } catch { /* noop */ }
    }
    setCurrentRwdId(null);
    setDatasets(ds => ds.map(d => ({ ...d, visible: false })));
    setParams(null);
  };

  const download = (fc, nameHint = 'osm-pois') => {
    if (!fc) return;
    const blob = new Blob([JSON.stringify(fc, null, 2)], { type: 'application/json' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `${nameHint.replace(/\s+/g, '_').toLowerCase()}.geojson`;
    a.click();
    URL.revokeObjectURL(a.href);
  };

  return (
    <Section title="🌍 Real-World Dataset (OSM POIs)">
      {/* Draw bbox toggle */}
      <div className="flex items-center justify-between mb-2">
        <label className="text-sm">
          <input
            type="checkbox"
            className="mr-2"
            checked={drawBBoxEnabled}
            onChange={(e) => setDrawBBoxEnabled(e.target.checked)}
          />
          Draw BBox on map (click or press&drag)
        </label>

        {lastBbox && (
          <div className="text-[13px]">
            <span className="mr-2">
              Drawn: [{lastBbox.west.toFixed(5)}, {lastBbox.south.toFixed(5)}] →
              [{lastBbox.east.toFixed(5)}, {lastBbox.north.toFixed(5)}]
            </span>
            <button className="px-2 py-0.5 bg-emerald-600 text-white rounded text-[12px]" onClick={useDrawnBbox}>
              Use drawn bbox
            </button>
            <button className="px-2 py-0.5 bg-gray-600 text-white rounded text-[12px] ml-2" onClick={clearLastBbox}>
              Clear
            </button>
          </div>
        )}
      </div>

      {/* Mode */}
      <div className="flex gap-3 text-sm mb-2">
        <label className="flex items-center gap-1">
          <input type="radio" name="mode" value="place" checked={mode === 'place'} onChange={() => setMode('place')} />
          Place
        </label>
        <label className="flex items-center gap-1">
          <input type="radio" name="mode" value="bbox" checked={mode === 'bbox'} onChange={() => setMode('bbox')} />
          BBox
        </label>
      </div>

      {/* Place mode */}
      {mode === 'place' && (
        <div className="mb-3">
          <label className="block text-sm mb-1">Place name</label>
          <input className="w-full border rounded p-1 text-sm" value={place} onChange={(e) => setPlace(e.target.value)} placeholder="Paris, France" />

          <div className="grid grid-cols-2 gap-2 mt-2">
            <div>
              <label className="block text-sm mb-1">Key</label>
              <input className="w-full border rounded p-1 text-sm" value={featureKey} onChange={(e) => setFeatureKey(e.target.value)} placeholder="amenity" />
            </div>
            <div>
              <label className="block text-sm mb-1">Value (regex ok)</label>
              <input
                className="w-full border rounded p-1 text-sm"
                value={featureValue}
                onChange={(e) => setFeatureValue(e.target.value)}
                placeholder='restaurant|cafe'
              />
              <div className="text-[11px] text-gray-500 mt-1">
                Normalized value sent: <span className="font-mono">{normalizedValue}</span>
              </div>
            </div>
          </div>

          <div className="mt-2">
            <button onClick={onSearch} className="text-xs px-3 py-1 bg-blue-600 text-white rounded hover:bg-blue-700">
              🔎 Search
            </button>
          </div>
        </div>
      )}

      {/* BBox mode */}
      {mode === 'bbox' && (
        <div className="mb-3">
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="block text-sm mb-1">minLon (west)</label>
              <input
                type="number" step="0.000001"
                className="w-full border rounded p-1 text-sm"
                value={bboxInputs.minLon}
                onChange={(e) => setBboxInputs(v => ({ ...v, minLon: e.target.value }))}
              />
            </div>
            <div>
              <label className="block text-sm mb-1">minLat (south)</label>
              <input
                type="number" step="0.000001"
                className="w-full border rounded p-1 text-sm"
                value={bboxInputs.minLat}
                onChange={(e) => setBboxInputs(v => ({ ...v, minLat: e.target.value }))}
              />
            </div>
            <div>
              <label className="block text-sm mb-1">maxLon (east)</label>
              <input
                type="number" step="0.000001"
                className="w-full border rounded p-1 text-sm"
                value={bboxInputs.maxLon}
                onChange={(e) => setBboxInputs(v => ({ ...v, maxLon: e.target.value }))}
              />
            </div>
            <div>
              <label className="block text-sm mb-1">maxLat (north)</label>
              <input
                type="number" step="0.000001"
                className="w-full border rounded p-1 text-sm"
                value={bboxInputs.maxLat}
                onChange={(e) => setBboxInputs(v => ({ ...v, maxLat: e.target.value }))}
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-2 mt-2">
            <div>
              <label className="block text-sm mb-1">Key</label>
              <input className="w-full border rounded p-1 text-sm" value={featureKey} onChange={(e) => setFeatureKey(e.target.value)} placeholder="highway" />
            </div>
            <div>
              <label className="block text-sm mb-1">Value</label>
              <input className="w-full border rounded p-1 text-sm" value={featureValue} onChange={(e) => setFeatureValue(e.target.value)} placeholder="bus_stop" />
            </div>
          </div>

          <div className="mt-2">
            <button onClick={onSearch} className="text-xs px-3 py-1 bg-blue-600 text-white rounded hover:bg-blue-700">
              🔎 Search
            </button>
          </div>
        </div>
      )}

      {/* Limit */}
      <div className="mb-3">
        <label className="block text-sm mb-1">Limit</label>
        <input
          type="number" min={1} max={10000} value={limit}
          onChange={(e) => setLimit(Math.max(1, Math.min(10000, Number(e.target.value) || 1)))}
          className="w-32 border rounded p-1 text-sm"
        />
        <div className="text-[13px] mt-1">
          Max number of features the backend will return. Higher values increase time and payload size.
        </div>
      </div>

      {/* Current result */}
      <Section title="🔎 Current result">
        {isFetching && <div className="text-[13px]">Loading…</div>}
        {isError && <div className="text-[13px] text-red-500">Error: {String(error?.message || 'failed')}</div>}
        {featureCollection && (
          <div className="text-[13px]">
            <div className="mb-1"><strong>Features:</strong> {features.length}</div>
            <div className="flex gap-2 flex-wrap">
              <button onClick={onLoadCurrent} className="text-xs px-3 py-1 bg-emerald-600 text-white rounded">➕ Load to Map</button>
              <button onClick={() => zoomTo(featureCollection)} className="text-xs px-3 py-1 bg-indigo-600 text-white rounded">🎯 Zoom to Result</button>
              <button onClick={onSaveDataset} className="text-xs px-3 py-1 bg-sky-600 text-white rounded">💾 Save to Saved datasets</button>
              <button onClick={() => download(featureCollection, 'osm-pois-current')} className="text-xs px-3 py-1 bg-purple-600 text-white rounded">⬇️ Download GeoJSON</button>
              <button onClick={clearCurrentSearch} className="text-xs px-3 py-1 bg-gray-600 text-white rounded">🧹 Remove current Search</button>
              <button onClick={clearAllRwdLayers} className="text-xs px-3 py-1 bg-rose-700 text-white rounded">
                🧹 Clear ALL RWD layers
              </button>
              {currentRwdId && (
                <button onClick={onRemoveCurrentLayer} className="text-xs px-3 py-1 bg-gray-800 text-white rounded">🗑 Remove Loaded Layer</button>
              )}
            </div>
          </div>
        )}
        {!isFetching && params && !featureCollection && (
          <div className="text-[13px]">No results (or unsupported response shape).</div>
        )}
      </Section>

      {/* Saved datasets */}
      <Section title="📚 Saved datasets">
        {datasets.length === 0 ? (
          <div className="text-[13px]">No datasets yet.</div>
        ) : (
          <ul className="space-y-2">
            {datasets.map(item => (
              <li key={item.id} className="p-2 border rounded">
                <div className="text-sm font-medium mb-1">{item.name}</div>
                <div className="text-[12px] mb-1">Features: {item.fc?.features?.length ?? 0}</div>
                <div className="flex gap-2 flex-wrap">
                  <button
                    onClick={() => toggleSavedLoad(item.id)}
                    className={`text-xs px-3 py-1 rounded text-white ${item.visible ? 'bg-rose-600' : 'bg-emerald-600'}`}
                  >
                    {item.visible ? '🗑 Unload/Hide from Map' : '➕ Load/Show on Map'}
                  </button>
                  <button onClick={() => zoomTo(item.fc)} className="text-xs px-3 py-1 bg-indigo-600 text-white rounded">🎯 Zoom</button>
                  <button onClick={() => download(item.fc, item.name)} className="text-xs px-3 py-1 bg-purple-600 text-white rounded">⬇️ Download</button>
                  <button onClick={() => removeDataset(item.id)} className="text-xs px-3 py-1 bg-gray-700 text-white rounded">🧹 Clear</button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Section>
    </Section>
  );
}
