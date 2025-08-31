/* eslint-disable no-restricted-globals */
import * as turf from '@turf/turf';

self.onmessage = (e) => {
  const { id, action, payload } = e.data;
  try {
    if (action === 'simplify') {
      const { fc, tolerance = 0.0005 } = payload;
      const out = turf.simplify(fc, { tolerance, highQuality: false, mutate: false });
      postMessage({ id, ok: true, data: out });
    } else if (action === 'bbox') {
      const { fc } = payload;
      const b = turf.bbox(fc);
      postMessage({ id, ok: true, data: b });
    } else {
      postMessage({ id, ok: false, error: 'unknown action' });
    }
  } catch (err) {
    postMessage({ id, ok: false, error: err?.message || String(err) });
  }
};
