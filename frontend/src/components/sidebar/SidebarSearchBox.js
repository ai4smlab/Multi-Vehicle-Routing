'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import useWaypointStore from '@/hooks/useWaypointStore';
import fitToFeatures from '@/components/map/fitToFeatures';
import useMapStore from '@/hooks/useMapStore';

// Mapbox proxy helpers (your file at components/api/mapboxProxy.js)
import { suggest as mbxSuggest, forward as mbxForward, retrieve as mbxRetrieve } from '@/api/mapboxProxy';

const SidebarSearchBox = () => {
  const [provider, setProvider] = useState('mapbox'); // 'mapbox' | 'locationiq'
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]); // list for suggest UI
  const [loading, setLoading] = useState(false);
  const [coordError, setCoordError] = useState('');
  const [error, setError] = useState('');

  const addWaypoint = useWaypointStore((s) => s.addWaypoint);
  const setViewState = useMapStore((s) => s.setViewState);
  const viewState = useMapStore((s) => s.viewState);

  const liqKey = process.env.NEXT_PUBLIC_LOCATIONIQ_API_KEY;

  // Stable session token for Mapbox retrieve/forward billing/session grouping
  const sessionTokenRef = useRef(`sess_${Math.random().toString(36).slice(2)}_${Date.now()}`);

  // --- helpers ---
  const centerProximity = useMemo(() => {
    if (!viewState) return null;
    return `${viewState.longitude?.toFixed(6)},${viewState.latitude?.toFixed(6)}`;
  }, [viewState]);

  function validateLatLon(input) {
    if (typeof input !== 'string') return { valid: false, reason: 'Input must be a string' };
    const trimmed = input.trim();
    const m = trimmed.match(/^\s*(-?\d+(\.\d+)?)\s*,\s*(-?\d+(\.\d+)?)\s*$/);
    if (!m) return { valid: false, reason: 'Not in valid lat,lon format' };
    const lat = parseFloat(m[1]); const lon = parseFloat(m[3]);
    if (!Number.isFinite(lat) || !Number.isFinite(lon)) return { valid: false, reason: 'Invalid numbers' };
    if (lat < -90 || lat > 90) return { valid: false, reason: '(Lat,Log) Latitude must be between -90 and 90' };
    if (lon < -180 || lon > 180) return { valid: false, reason: '(Lat,Log) Longitude must be between -180 and 180' };
    return { valid: true, lat, lon };
  }

  function dropWaypointAndFit(lng, lat, name) {
    addWaypoint({
      coordinates: [lng, lat],
      id: Date.now(),
      type: 'Delivery',
      demand: 1, capacity: 5, serviceTime: 10, timeWindow: [8, 17],
      label: name || undefined
    });
    fitToFeatures([lng, lat], { setViewState, padding: 100 });
  }

  // ============== SUGGEST (typeahead) ==============
  useEffect(() => {
    let cancel = false;
    setError('');
    setCoordError('');
    setResults([]);

    const q = query.trim();

    // Coordinates? -> don't suggest; wait for submit/Enter to add waypoint directly
    const asCoord = validateLatLon(q);
    if (asCoord.valid) return;

    // Too short
    if (q.length < 3) return;

    // Provider-specific suggest
    async function run() {
      setLoading(true);
      try {
        if (provider === 'mapbox') {
          const resp = await mbxSuggest({
            q,
            limit: 5,
            proximity: centerProximity || undefined,
          });
          // Expect {features:[...]} (your proxy schema)
          if (!cancel) setResults(Array.isArray(resp?.features) ? resp.features : []);
        } else {
          // LocationIQ autocomplete (fallback)
          const url = `https://locationiq.com/v1/autocomplete?key=${liqKey}&q=${encodeURIComponent(q)}&format=json&limit=5`;
          const r = await fetch(url);
          const data = await r.json();
          if (!cancel) setResults(Array.isArray(data) ? data : []);
        }
      } catch (e) {
        if (!cancel) setError(e?.message || 'Suggest failed');
      } finally {
        if (!cancel) setLoading(false);
      }
    }

    const t = setTimeout(run, 250); // tiny debounce
    return () => { cancel = true; clearTimeout(t); };
  }, [query, provider, centerProximity, liqKey, mbxSuggest]);

  // ============== FORWARD (Enter/Submit) ==============
  async function handleSubmit(e) {
    e.preventDefault();
    setError('');
    setCoordError('');
    setResults([]);

    const q = query.trim();
    if (!q) return;

    // Coordinates: add immediately
    const asCoord = validateLatLon(q);
    if (asCoord.valid) {
      dropWaypointAndFit(asCoord.lon, asCoord.lat, 'Custom point');
      setQuery('');
      return;
    }
    if (q.length < 3) return;

    // --- MAPBOX FORWARD ---
    if (provider === 'mapbox') {
      try {
        setLoading(true);
        // Fire the proxy forward (→ should show POST /mapbox/forward in Network)
        console.debug('[search] Forward → /mapbox/forward', { q, proximity: centerProximity });
        const payload = {
          q,
          limit: 5,
          language: 'en',
          proximity: centerProximity || undefined,
          session_token: sessionTokenRef.current,
        };
        const resp = await mbxForward(payload); // {features:[...]}
        const feat = resp?.features?.[0];
        if (!feat) {
          setError('No results from Mapbox forward');
          return;
        }
        // Prefer Point geometry; otherwise fallback to center of bbox
        let lng, lat, label;
        label = feat.place_name || feat.properties?.name || 'Result';
        if (feat?.geometry?.type === 'Point' && Array.isArray(feat.geometry.coordinates)) {
          [lng, lat] = feat.geometry.coordinates;
        } else if (Array.isArray(feat?.center)) {
          [lng, lat] = feat.center;
        } else if (Array.isArray(feat?.bbox) && feat.bbox.length === 4) {
          const [minX, minY, maxX, maxY] = feat.bbox;
          lng = (minX + maxX) / 2; lat = (minY + maxY) / 2;
        }
        if (Number.isFinite(lng) && Number.isFinite(lat)) {
          // (Optional) Retrieve for richer details if mapbox_id exists
          if (feat?.properties?.mapbox_id) {
            try {
              const det = await mbxRetrieve({ id: feat.properties.mapbox_id, session_token: sessionTokenRef.current });
              const richer = det?.features?.[0];
              if (richer?.geometry?.type === 'Point') {
                const c = richer.geometry.coordinates;
                if (Array.isArray(c)) [lng, lat] = c;
                label = richer.place_name || richer.properties?.name || label;
              }
            } catch (_) { /* non-fatal */ }
          }
          dropWaypointAndFit(lng, lat, label);
          setQuery('');
        } else {
          setError('Forward result had no usable coordinates');
        }
      } catch (e) {
        setError(e?.message || 'Forward failed');
      } finally {
        setLoading(false);
      }
      return;
    }

    // --- LOCATIONIQ "forward" style (fallback: reuse autocomplete then pick first) ---
    try {
      setLoading(true);
      const url = `https://locationiq.com/v1/autocomplete?key=${liqKey}&q=${encodeURIComponent(q)}&format=json&limit=1`;
      const r = await fetch(url);
      const data = await r.json();
      const first = Array.isArray(data) && data[0];
      if (first) {
        const lng = parseFloat(first.lon), lat = parseFloat(first.lat);
        if (Number.isFinite(lng) && Number.isFinite(lat)) {
          dropWaypointAndFit(lng, lat, first.display_name);
          setQuery('');
        } else {
          setError('LocationIQ returned invalid coordinates');
        }
      } else {
        setError('No results from LocationIQ');
      }
    } catch (e) {
      setError(e?.message || 'LocationIQ request failed');
    } finally {
      setLoading(false);
    }
  }

  // ============== SELECT from suggest list ==============
  async function handleSelect(item) {
    setError('');
    try {
      if (provider === 'mapbox') {
        // item is a Mapbox feature
        let feat = item;
        // Optionally retrieve richer data if mapbox_id present
        if (feat?.properties?.mapbox_id) {
          try {
            const det = await mbxRetrieve({ id: feat.properties.mapbox_id, session_token: sessionTokenRef.current });
            if (Array.isArray(det?.features) && det.features[0]) feat = det.features[0];
          } catch (_) { /* ignore */ }
        }
        let lng, lat, label = feat.place_name || feat.properties?.name || 'Result';
        if (feat?.geometry?.type === 'Point') {
          [lng, lat] = feat.geometry.coordinates || [];
        } else if (Array.isArray(feat?.center)) {
          [lng, lat] = feat.center;
        }
        if (Number.isFinite(lng) && Number.isFinite(lat)) {
          dropWaypointAndFit(lng, lat, label);
        }
      } else {
        // item is a LocationIQ record
        const lng = parseFloat(item.lon), lat = parseFloat(item.lat);
        if (Number.isFinite(lng) && Number.isFinite(lat)) {
          dropWaypointAndFit(lng, lat, item.display_name);
        }
      }
    } finally {
      setResults([]);
      setQuery('');
    }
  }

  return (
    <div className="mb-4">
      {/* Provider switch (simple) */}
      <div className="mb-2 flex gap-2 text-xs">
        <button
          className={`px-2 py-0.5 rounded ${provider==='mapbox'?'bg-blue-600 text-white':'bg-gray-200 dark:bg-gray-700'}`}
          onClick={() => setProvider('mapbox')}
          type="button"
        >Mapbox</button>
        <button
          className={`px-2 py-0.5 rounded ${provider==='locationiq'?'bg-blue-600 text-white':'bg-gray-200 dark:bg-gray-700'}`}
          onClick={() => setProvider('locationiq')}
          type="button"
        >LocationIQ</button>
      </div>

      {/* Wrap in form so Enter triggers forward */}
      <form onSubmit={handleSubmit}>
        <input
          type="text"
          value={query}
          placeholder="🔍 Search place or lat,lon"
          onChange={(e) => {
            setQuery(e.target.value);
            setError('');
            setCoordError('');
          }}
          className="w-full px-2 py-1 border rounded text-sm dark:bg-gray-700 dark:text-white"
        />
      </form>

      {loading && <div className="text-xs text-gray-500 mt-1">Loading…</div>}
      {error && <div className="text-xs text-red-600 mt-1">{error}</div>}
      {coordError && <div className="text-xs text-red-600 mt-1">{coordError}</div>}

      {results.length > 0 && (
        <ul className="mt-1 border rounded bg-white dark:bg-gray-800 shadow text-sm max-h-60 overflow-y-auto">
          {results.map((r, i) => (
            <li
              key={r.id || i}
              data-search-item
              data-lon={provider==='mapbox' ? (r?.center?.[0] ?? r?.geometry?.coordinates?.[0] ?? '') : r.lon}
              data-lat={provider==='mapbox' ? (r?.center?.[1] ?? r?.geometry?.coordinates?.[1] ?? '') : r.lat}
              onClick={() => handleSelect(r)}
              className="px-2 py-1 hover:bg-gray-100 dark:hover:bg-gray-700 cursor-pointer"
            >
              {provider==='mapbox'
                ? (r.place_name || r.text || r.properties?.name || 'Place')
                : r.display_name}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};

export default SidebarSearchBox;
