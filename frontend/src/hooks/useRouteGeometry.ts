// src/hooks/useRouteGeometry.ts
import { useEffect, useMemo, useRef, useState } from 'react';
import { coordsFromAnyGeometry } from '@/utils/routeGeometry';
import useRouteStore from '@/hooks/useRouteStore';
import useRenderSettingsStore from '@/hooks/useRenderSettingsStore';
import { getGeometryWithCache } from '@/utils/routeGeometry';
import api from '@/api/api';

type Provider = 'auto' | 'backend' | 'mapbox' | 'osrm' | 'none';
type Status = 'idle' | 'loading' | 'ok' | 'error';

type Options = {
    source?: Provider;
    profile?: 'driving' | 'driving-traffic' | 'cycling' | 'walking';
    osrmUrl?: string;
    /** POST { coordinates, profile } -> {status,data:{geometry}} (backend) */
    backendGeometryEndpoint?: string;      // default: /route/geometry
    /** POST { coordinates, profile, geometries?, tidy? } -> Mapbox match JSON (backend proxy) */
    backendMapboxEndpoint?: string;        // default: /mapbox/match
};

const disabledProviders = new Set<Provider>(); // session-only backoff in auto mode

const dedupeLoop = (inCoords: number[][]) => {
    if (!Array.isArray(inCoords) || inCoords.length < 2) return [];
    const a = inCoords[0], b = inCoords[inCoords.length - 1];
    const same = Array.isArray(a) && Array.isArray(b) && a[0] === b[0] && a[1] === b[1];
    return same ? inCoords.slice(0, -1) : inCoords;
};

export function useRouteGeometry(
    route: { coords?: number[][]; raw?: any } | null | undefined,
    options?: Options
) {
    const storeSource = useRenderSettingsStore(s => s.geometrySource) as Provider | undefined;
    const storeOsrm = useRenderSettingsStore(s => s.osrmUrl) as string | undefined;

    const profile = options?.profile ?? 'driving';
    const osrmUrl = options?.osrmUrl ?? storeOsrm ?? (process.env.NEXT_PUBLIC_OSRM_URL || 'https://router.project-osrm.org');

    const apiBase =
        (api?.defaults?.baseURL?.replace(/\/+$/, '') || process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000')
            .replace(/\/+$/, '');

    const backendMapboxEndpoint = options?.backendMapboxEndpoint ?? `${apiBase}/mapbox/match`;
    const backendGeometryEndpoint = options?.backendGeometryEndpoint ?? `${apiBase}/route/geometry`;

    const effectiveSource: Provider = options?.source ?? storeSource ?? 'auto';
    const adapter = route?.raw?.adapter as string | undefined;
    const coords = useMemo(() => dedupeLoop(route?.coords || []), [route?.coords]);
    const coordsKey = useMemo(() => JSON.stringify(coords), [coords]);

    const [state, setState] = useState<{
        status: Status;
        coords: number[][] | null;
        provider: Provider | null;
        error?: string;
    }>({ status: 'idle', coords: null, provider: null });
    const lastOkKey = useRef<string | null>(null);

    const reqId = useRef(0);

    useEffect(() => {
        if (coords.length < 2) {
            setState({ status: 'idle', coords: null, provider: null });
            return;
        }

        if (effectiveSource === 'none') {
            setState({ status: 'idle', coords: null, provider: 'none' });
            return;
        }

    const myId = ++reqId.current;
    // Only go to 'loading' if these coords are actually new
    setState(prev => {
        if (prev.status === 'ok' && lastOkKey.current === coordsKey) return prev;
        return { status: 'loading', coords: null, provider: null };
    });

        const p0 = profile.split('-')[0] as 'driving' | 'walking' | 'cycling';

        const fetchByProvider = (prov: Exclude<Provider, 'auto' | 'none'>) => {
            return getGeometryWithCache(async ({ signal }) => {
                if (prov === 'backend') {
                    const base = (api?.defaults?.baseURL || '').replace(/\/$/, '');
                    const candidates = Array.from(new Set([
                        backendGeometryEndpoint,
                        `${base}/route/geometry`,
                        `${base}/api/route/geometry`,
                        '/route/geometry',
                        '/api/route/geometry',
                    ])).filter(Boolean) as string[];

                    let last: any = null;
                    for (const url of candidates) {
                        try {
                            const r = await fetch(url, {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ coordinates: coords, profile }),
                                signal
                            });
                            if (!r.ok) { last = r.status; continue; }
                            const j = await r.json();
                            const payload = j?.data?.geometry || j?.geometry || j?.data || j;
                            const c =
                                coordsFromAnyGeometry(payload) ||
                                coordsFromAnyGeometry({ geometry: payload }) ||
                                null;
                            if (c && c.length >= 2) return c;
                        } catch (e) {
                            last = e;
                        }
                    }
                    throw new Error(`backend geometry failed (${String(last)})`);
                }

                if (prov === 'mapbox') {
                    const res = await api.post(
                        backendMapboxEndpoint,
                        { coordinates: coords, profile: p0, geometries: 'geojson', tidy: true }
                    );
                    const j = res?.data;
                    const c =
                        (j?.tracepoints && j?.matchings?.[0]?.geometry?.coordinates) ||
                        j?.geometry?.coordinates ||
                        j?.routes?.[0]?.geometry?.coordinates ||
                        coordsFromAnyGeometry(j) ||
                        null;
                    return c || [];
                }

                const path = coords.map(c => `${c[0]},${c[1]}`).join(';');
                const url = `${osrmUrl.replace(/\/+$/, '')}/route/v1/${p0}/${path}?overview=full&geometries=geojson`;
                const r = await fetch(url, { cache: 'no-store' });
                if (!r.ok) throw new Error(`osrm ${r.status}`);
                const j = await r.json();
                const c = j?.routes?.[0]?.geometry?.coordinates || [];
                return c;
            }, {
                source: prov,
                profile: p0,
                adapter: adapter || 'auto',
                coords
            });
        };

        const tryAuto = async () => {
            const candidates: Provider[] = (['backend', 'mapbox', 'osrm'] as Provider[])
                .filter(p => !disabledProviders.has(p));

            let picked: Provider | null = null;
            let snapped: number[][] | null = null;
            let lastErr: string | undefined;

            for (const prov of candidates) {
                try {
                    const c = await fetchByProvider(prov as Exclude<Provider, 'auto' | 'none'>);
                    if (Array.isArray(c) && c.length >= 2) {
                        picked = prov as Provider;
                        snapped = c;
                        break;
                    }
                    throw new Error('No geometry in response');
                } catch (e: any) {
                    lastErr = e?.message || String(e);
                    disabledProviders.add(prov);
                    console.warn('[RouteGeom] backoff provider', prov, lastErr);
                }
            }

            if (reqId.current !== myId) return;

            if (snapped) {
                console.debug('[RouteGeom] geometry ok', { provider: picked, n: snapped.length });
                setState({ status: 'ok', coords: snapped, provider: picked! });
            } else {
                setState({ status: 'error', coords: null, provider: null, error: lastErr || 'Geometry fetch failed' });
            }
        };

        const runSingle = async (prov: Exclude<Provider, 'auto' | 'none'>) => {
            try {
                const c = await fetchByProvider(prov);
                if (reqId.current !== myId) return;
                if (Array.isArray(c) && c.length >= 2) {
                    console.debug('[RouteGeom] geometry ok', { provider: prov, n: c.length });
                    setState({ status: 'ok', coords: c, provider: prov });
                } else {
                    setState({ status: 'error', coords: null, provider: null, error: 'No geometry in response' });
                }
            } catch (e: any) {
                if (reqId.current !== myId) return;
                setState({ status: 'error', coords: null, provider: null, error: e?.message || String(e) });
            }
        };

        if (effectiveSource === 'auto') {
            void tryAuto();
        } else {
            void runSingle(effectiveSource);
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [
        effectiveSource,
        adapter,
        profile,
        osrmUrl,
        backendGeometryEndpoint,
        backendMapboxEndpoint,
        coordsKey   // ← only the stable key
    ]);

    useEffect(() => {
        if (state.status !== 'ok' || !state.coords || state.coords.length < 2) return;
        // Remember we’ve satisfied this geometry key
        lastOkKey.current = coordsKey;
        useRouteStore.setState(s => {
            const next = Array.isArray(s.routes) ? [...s.routes] : [];
            const idx = s.currentIndex ?? 0;
            if (!next[idx]) return s;
            next[idx] = { ...next[idx], displayCoords: state.coords, displayProvider: state.provider };
            return { routes: next };
        });
    }, [state.status, state.coords, state.provider, coordsKey]);

    return state;
}
