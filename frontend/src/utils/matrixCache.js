import { matrix as mbxMatrix } from '@/api/mapboxProxy';

const _cache = new Map();   // key -> Promise|value
const MAX = 50;

const sig = (coords=[], profile='driving') =>
  `${profile}|` + coords.map(([x,y]) => `${(+x).toFixed(5)},${(+y).toFixed(5)}`).join('|');

export async function matrixCached({ coordinates, profile='driving', ...rest }) {
  const key = sig(coordinates, profile);
  if (_cache.has(key)) return _cache.get(key);

  const p = mbxMatrix({ coordinates, profile, ...rest })
    .then((data) => {
      _cache.set(key, data);
      // prune oldest if needed
      if (_cache.size > MAX) _cache.delete(_cache.keys().next().value);
      return data;
    })
    .catch((e) => { _cache.delete(key); throw e; });

  _cache.set(key, p);
  return p;
}
