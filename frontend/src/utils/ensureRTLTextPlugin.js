// lib/ensureRTLTextPlugin.js
// Robust, SSR-safe, HMR-proof RTL plugin loader for MapLibre GL

const CDN_SRC =
  'https://cdn.jsdelivr.net/npm/@mapbox/mapbox-gl-rtl-text@0.2.3/mapbox-gl-rtl-text.min.js';

// Returns: 'ssr' | 'loaded' | 'loading' | 'error' | 'unavailable'
export function ensureRTLTextPlugin(maplibregl, { src = CDN_SRC, lazy = true } = {}) {
  if (typeof window === 'undefined' || !maplibregl?.setRTLTextPlugin) return 'ssr';

  const w = window;
  const KEY = '__maplibre_rtl_plugin__';

  // If we already attempted (or finished), bail early.
  if (w[KEY]?.done) return w[KEY].status || 'loaded';

  const getStatus =
    typeof maplibregl.getRTLTextPluginStatus === 'function'
      ? maplibregl.getRTLTextPluginStatus
      : null;

  const statusNow = getStatus ? getStatus() : 'unavailable';

  // Initialize shared state exactly once per tab
  if (!w[KEY]) w[KEY] = { done: false, status: statusNow };

  // If another call already kicked off loading or it’s already loaded, mark done and exit.
  if (statusNow === 'loaded' || statusNow === 'loading') {
    w[KEY] = { done: true, status: statusNow };
    return statusNow;
  }

  try {
    // Mark done *before* calling setRTLTextPlugin to avoid race-y double calls.
    w[KEY] = { done: true, status: 'loading' };
    maplibregl.setRTLTextPlugin(
      src,
      () => {
        w[KEY].status = 'loaded';
      },
      lazy // defer network fetch until first RTL label
    );
    return 'loading';
  } catch (e) {
    // MapLibre throws if setRTLTextPlugin is called twice — normalize that to a "loaded" state.
    const msg = (e && e.message) || String(e);
    if (/cannot be called multiple times/i.test(msg)) {
      w[KEY] = { done: true, status: 'loaded' };
      return 'loaded';
    }
    console.warn('[rtl] failed to set plugin:', e);
    w[KEY] = { done: true, status: 'error' };
    return 'error';
  }
}

// (Optional) quick console helper:
export function rtlStatus(maplibregl) {
  const raw =
    typeof maplibregl?.getRTLTextPluginStatus === 'function'
      ? maplibregl.getRTLTextPluginStatus()
      : 'unavailable';
  const mark = typeof window !== 'undefined' ? window.__maplibre_rtl_plugin__ : null;
  return { raw, mark };
}
