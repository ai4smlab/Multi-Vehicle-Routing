'use client';
import { useEffect, useRef, useState } from 'react';

const LS_PROVIDER_KEY = 'ctx_reverse_provider'; // persist user choice

async function reverseMapbox(lng, lat, language = 'en') {
  const token = process.env.NEXT_PUBLIC_MAPBOX_TOKEN;
  if (!token) throw new Error('Missing NEXT_PUBLIC_MAPBOX_TOKEN');
  const url =
    `https://api.mapbox.com/geocoding/v5/mapbox.places/` +
    `${encodeURIComponent(lng)},${encodeURIComponent(lat)}.json` +
    `?access_token=${encodeURIComponent(token)}&limit=1&language=${encodeURIComponent(language)}`;

  const r = await fetch(url);
  if (!r.ok) throw new Error(`Mapbox ${r.status}`);
  const data = await r.json();
  const feat = Array.isArray(data?.features) ? data.features[0] : null;
  const label =
    feat?.place_name ||
    feat?.properties?.full_address ||
    feat?.text ||
    '';
  return { label, raw: data };
}

async function reverseLocationIQ(lng, lat, language = 'en') {
  const key = process.env.NEXT_PUBLIC_LOCATIONIQ_API_KEY;
  const base = process.env.NEXT_PUBLIC_LOCATIONIQ_BASE || 'https://us1.locationiq.com';
  if (!key) throw new Error('Missing NEXT_PUBLIC_LOCATIONIQ_API_KEY');

  const url =
    `${base}/v1/reverse?key=${encodeURIComponent(key)}` +
    `&lat=${encodeURIComponent(lat)}&lon=${encodeURIComponent(lng)}` +
    `&format=json&normalizeaddress=1&accept-language=${encodeURIComponent(language)}`;

  const r = await fetch(url);
  if (!r.ok) throw new Error(`LocationIQ ${r.status}`);
  const data = await r.json();
  const label =
    data?.display_name ||
    [data?.address?.road, data?.address?.city, data?.address?.country].filter(Boolean).join(', ');
  return { label, raw: data };
}

export default function ContextMenu({ mapRef, items = [], language = 'en' }) {
  const [menu, setMenu] = useState(null);     // { x, y, lng, lat }
  const lastPDRef = useRef(null);
  const menuRef = useRef(null);

  // provider toggle: 'mapbox' | 'locationiq'
  const [provider, setProvider] = useState(
    () => (typeof window !== 'undefined' ? localStorage.getItem(LS_PROVIDER_KEY) : null) || 'mapbox'
  );
  const [revLoading, setRevLoading] = useState(false);
  const [revError, setRevError] = useState('');
  const [revLabel, setRevLabel] = useState('');

  const getMapAndContainer = () => {
    const map = mapRef?.current?.getMap?.() || null;
    let container = null;
    if (map && typeof map.getContainer === 'function') {
      container = map.getContainer();
    }
    if (!container) {
      const canvas = document.querySelector('.maplibregl-canvas');
      container = canvas?.parentElement || canvas || document.body;
    }
    return { map, container };
  };

  // Reverse geocode whenever menu opens OR provider changes
  useEffect(() => {
    if (!menu) return;
    let cancelled = false;

    async function run() {
      setRevLoading(true);
      setRevError('');
      setRevLabel('');
      try {
        const { lng, lat } = menu;
        const res =
          provider === 'locationiq'
            ? await reverseLocationIQ(lng, lat, language)
            : await reverseMapbox(lng, lat, language);
        if (!cancelled) setRevLabel(res.label || '');
      } catch (e) {
        if (!cancelled) setRevError(e?.message || 'Reverse geocoding failed');
      } finally {
        if (!cancelled) setRevLoading(false);
      }
    }

    run();
    return () => { cancelled = true; };
  }, [menu, provider, language]);

  useEffect(() => {
    if (typeof window !== 'undefined') {
      localStorage.setItem(LS_PROVIDER_KEY, provider);
    }
  }, [provider]);

  useEffect(() => {
    const { map, container } = getMapAndContainer();
    if (!container) return;

    const unproject = (pt) => {
      try {
        const m = mapRef?.current?.getMap?.();
        return m ? m.unproject(pt) : { lng: NaN, lat: NaN };
      } catch { return { lng: NaN, lat: NaN }; }
    };

    const onPointerDownCapture = (ev) => {
      const rect = container.getBoundingClientRect();
      const inside =
        ev.clientX >= rect.left && ev.clientX <= rect.right &&
        ev.clientY >= rect.top && ev.clientY <= rect.bottom;

      if (ev.button === 2 && inside) {
        ev.preventDefault();
        ev.stopPropagation();
        if (ev.stopImmediatePropagation) ev.stopImmediatePropagation();
        lastPDRef.current = {
          x: ev.clientX - rect.left,
          y: ev.clientY - rect.top,
          clientX: ev.clientX,
          clientY: ev.clientY
        };
      }
    };

    const onContextMenuCapture = (ev) => {
      const rect = container.getBoundingClientRect();
      const inside =
        ev.clientX >= rect.left && ev.clientX <= rect.right &&
        ev.clientY >= rect.top && ev.clientY <= rect.bottom;

      if (!inside) return;
      ev.preventDefault();
      ev.stopPropagation();
      if (ev.stopImmediatePropagation) ev.stopImmediatePropagation();

      const px = lastPDRef.current?.x ?? (ev.clientX - rect.left);
      const py = lastPDRef.current?.y ?? (ev.clientY - rect.top);
      const { lng, lat } = unproject([px, py]);
      setMenu({ x: px, y: py, lng, lat });
    };

    const onClickCapture = (ev) => {
      if (menuRef.current && menuRef.current.contains(ev.target)) return;
      setMenu(null);
    };

    document.addEventListener('pointerdown', onPointerDownCapture, true);
    document.addEventListener('contextmenu', onContextMenuCapture, true);
    document.addEventListener('click', onClickCapture, true);

    return () => {
      document.removeEventListener('pointerdown', onPointerDownCapture, true);
      document.removeEventListener('contextmenu', onContextMenuCapture, true);
      document.removeEventListener('click', onClickCapture, true);
    };
  }, [mapRef]);

  if (!menu) return null;

  const coordsStr = `${menu.lng.toFixed(6)}, ${menu.lat.toFixed(6)}`;

  const copy = async (text) => {
    try { await navigator.clipboard.writeText(text); }
    catch { /* ignore */ }
  };

  return (
    <div
      ref={menuRef}
      className="absolute bg-white text-sm rounded shadow-md border z-50 min-w-[240px] max-w-[320px] select-none"
      style={{ left: menu.x + 4, top: menu.y + 4 }}
      onContextMenu={(e) => { e.preventDefault(); e.stopPropagation(); }}
      onMouseDown={(e) => { e.stopPropagation(); }}
    >
      {/* Provider switch header */}
      <div className="px-3 py-2 border-b flex items-center justify-between gap-2">
        <span className={`text-xs font-medium ${provider==='locationiq' ? 'text-blue-600' : 'text-gray-700'}`}>
          LocationIQ
        </span>
        <label className="inline-flex items-center cursor-pointer">
          <input
            type="checkbox"
            className="sr-only peer"
            checked={provider === 'mapbox'}
            onChange={(e) => setProvider(e.target.checked ? 'mapbox' : 'locationiq')}
          />
          <div className="w-10 h-5 bg-gray-300 rounded-full peer-checked:bg-blue-600 relative transition-colors">
            <div className="absolute top-0.5 left-0.5 w-4 h-4 bg-white rounded-full transition-transform peer-checked:translate-x-5"></div>
          </div>
        </label>
        <span className={`text-xs font-medium ${provider==='mapbox' ? 'text-blue-600' : 'text-gray-700'}`}>
          Mapbox
        </span>
      </div>

      {/* Result + copy actions */}
      <div className="px-3 py-2 border-b">
        <div className="text-[11px] text-gray-500 mb-1">Result</div>
        {revLoading ? (
          <div className="text-xs text-gray-600">Looking up…</div>
        ) : revError ? (
          <div className="text-xs text-red-600">{revError}</div>
        ) : (
          <div className="text-xs text-gray-900 break-words">{revLabel || '—'}</div>
        )}

        <div className="mt-2 flex gap-2">
          <button
            className="px-2 py-1 text-xs text-gray-600 border rounded hover:bg-gray-200"
            onClick={() => copy(coordsStr)}
            title="Copy coordinates"
          >
            Copy coordinate
          </button>
          <button
            className="px-2 py-1 text-xs text-gray-600 border rounded hover:bg-gray-200 disabled:opacity-50"
            onClick={() => copy(revLabel || '')}
            disabled={!revLabel}
            title="Copy address"
          >
            Copy address
          </button>
        </div>
      </div>

      {/* Actions (from props) */}
      {items.length === 0 ? (
        <div className="px-3 py-2 text-gray-500">No actions</div>
      ) : (
        items.map((it, i) => (
          <button
            key={i}
            className={`block w-full text-left px-3 py-2 hover:bg-gray-100 ${it.className || ''}`}
            onClick={() => {
              try { it.onClick?.({ lng: menu.lng, lat: menu.lat, x: menu.x, y: menu.y, address: revLabel }); }
              finally { setMenu(null); }
            }}
            onContextMenu={(e) => { e.preventDefault(); e.stopPropagation(); }}
          >
            {it.label}
          </button>
        ))
      )}
    </div>
  );
}
