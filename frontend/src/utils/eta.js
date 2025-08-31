// utils/eta.js
import { matrix } from '@/api/mapboxProxy';

export function decimate(coords, step = 5) {
    if (!Array.isArray(coords) || coords.length <= 2) return coords || [];
    const out = [];
    for (let i = 0; i < coords.length; i += step) out.push(coords[i]);
    const last = coords[coords.length - 1];
    if (out.length === 0 || out[out.length - 1] !== last) out.push(last);
    return out;
}

/**
 * Returns { times:number[], indices:number[] }
 * - times = epoch seconds for each sampled vertex (length = indices.length+1; includes start)
 * - indices = which original vertex each time corresponds to (destination of each leg)
 */
export async function computeETAsFromMatrix(routeCoords, opts = {}) {
    console.debug('[eta] computeETAsFromMatrix has been called');
    const coords = decimate(routeCoords, opts.sampleEvery ?? 5);
    if (coords.length < 2) {
        const t0 = Math.floor((opts.startEpoch ?? Date.now() / 1000));
        return { times: [t0], indices: [0] };
    }

    const points = coords.map(([lon, lat]) => ({ lon, lat }));
    const n = points.length;
    const sources = Array.from({ length: n - 1 }, (_, i) => i);
    const destinations = Array.from({ length: n - 1 }, (_, i) => i + 1);

    let legSecs = [];
    try {
        const res = await matrix({
            profile: opts.profile || 'driving',
            coordinates: points,
            sources, destinations
        });
        const toRad = d => d * Math.PI / 180;
        const haversineSec = (a, b, kmh = 50) => {
            const R = 6371000, mps = (kmh * 1000) / 3600;
            const dLat = toRad(b[1] - a[1]), dLon = toRad(b[0] - a[0]);
            const s = Math.sin(dLat / 2) ** 2 + Math.cos(toRad(a[1])) * Math.cos(toRad(b[1])) * Math.sin(dLon / 2) ** 2;
            const meters = 2 * R * Math.asin(Math.sqrt(s));
            return Math.max(1, Math.round(meters / mps));
        };
        for (let i = 0; i < sources.length; i++) {
            const row = res?.durations?.[i] || [];
            const v = row[i];
            legSecs.push(Number.isFinite(v) && v > 0 ? v : haversineSec(coords[i], coords[i + 1], 50));
        }
    } catch (e) {
        console.warn('[eta] matrix() failed, falling back to haversine:', e?.message || e);        // simple haversine fallback @ 50 km/h
        const toRad = (d) => d * Math.PI / 180;
        const R = 6371000, mps = 50_000 / 3600;
        for (let i = 0; i < sources.length; i++) {
            const [a, b] = [coords[i], coords[i + 1]];
            const dLat = toRad(b[1] - a[1]), dLon = toRad(b[0] - a[0]);
            const s = Math.sin(dLat / 2) ** 2 + Math.cos(toRad(a[1])) * Math.cos(toRad(b[1])) * Math.sin(dLon / 2) ** 2;
            const meters = 2 * R * Math.asin(Math.sqrt(s));
            legSecs.push(Math.max(1, Math.round(meters / mps)));
        }
    }

    const start = Math.floor(opts.startEpoch ?? Date.now() / 1000);
    const times = [start];
    for (let i = 0; i < legSecs.length; i++) {
        times.push(times[i] + (legSecs[i] || 0));
    }
    console.debug('[eta] computeETAsFromMatrix values: ', times, sources.map(i => i + 1));
    return { times, indices: sources.map(i => i + 1) };
}
