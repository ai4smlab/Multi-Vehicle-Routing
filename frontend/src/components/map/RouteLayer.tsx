// src/components/map/RouteLayer.tsx
import { useEffect, useMemo } from 'react';
import type { Map, GeoJSONSource } from 'mapbox-gl';
import type { Feature, FeatureCollection, LineString, Point } from 'geojson';

type Props = {
    map: Map;
    coords: number[][];
    layerBeforeId?: string | null;
};

function bearingDeg(a: number[], b: number[]) {
    const toRad = Math.PI / 180;
    const φ1 = a[1] * toRad, φ2 = b[1] * toRad, Δλ = (b[0] - a[0]) * toRad;
    const y = Math.sin(Δλ) * Math.cos(φ2);
    const x = Math.cos(φ1) * Math.sin(φ2) - Math.sin(φ1) * Math.cos(φ2) * Math.cos(Δλ);
    return (Math.atan2(y, x) * 180 / Math.PI + 360) % 360;
}

function arrowPointsFromCoords(coords: number[][]) {
    const features: Feature<Point>[] = [];
    for (let i = 0; i < coords.length - 1; i++) {
        const a = coords[i], b = coords[i + 1];
        const mid: [number, number] = [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2];
        features.push({ type: 'Feature', properties: { bearing: bearingDeg(a, b) }, geometry: { type: 'Point', coordinates: mid } });
    }
    return { type: 'FeatureCollection', features } as FeatureCollection<Point>;
}

function segmentsFromCoords(coords: number[][]) {
    const SEG_COLORS = ['#22d3ee', '#a78bfa', '#34d399', '#f59e0b', '#f472b6', '#60a5fa'];
    const features: Feature<LineString>[] = [];
    for (let i = 0; i < coords.length - 1; i++) {
        features.push({
            type: 'Feature',
            properties: { idx: i, offset: (i % 2 === 0) ? 0.8 : -0.8, stroke: SEG_COLORS[i % SEG_COLORS.length] },
            geometry: { type: 'LineString', coordinates: [coords[i], coords[i + 1]] },
        });
    }
    return { type: 'FeatureCollection', features } as FeatureCollection<LineString>;
}

function terminalsFromCoords(coords: number[][]) {
    const features: Feature<Point>[] = [];
    if (coords.length >= 1) features.push({ type: 'Feature', properties: { kind: 'start', label: 'S' }, geometry: { type: 'Point', coordinates: coords[0] as any } });
    if (coords.length >= 2) features.push({ type: 'Feature', properties: { kind: 'end', label: 'E' }, geometry: { type: 'Point', coordinates: coords[coords.length - 1] as any } });
    return { type: 'FeatureCollection', features } as FeatureCollection<Point>;
}

function ensureArrowImage(map: Map, id = 'route-arrow') {
    if (map.hasImage(id)) return;
    const size = 64;
    const canvas = document.createElement('canvas');
    canvas.width = canvas.height = size;
    const ctx = canvas.getContext('2d')!;
    ctx.translate(size / 2, size / 2);
    ctx.fillStyle = '#ffffff';
    ctx.beginPath();
    ctx.moveTo(0, -28);
    ctx.lineTo(24, 20);
    ctx.lineTo(-24, 20);
    ctx.closePath();
    ctx.fill();
    const imageData = ctx.getImageData(0, 0, size, size);
    const rgba = new Uint8Array(imageData.data.buffer);
    map.addImage(id, { data: rgba, width: size, height: size }, { pixelRatio: 2 });
}

export default function RouteLayer({ map, coords, layerBeforeId }: Props) {
    const depsHash = useMemo(() => JSON.stringify(coords), [coords]);

    useEffect(() => {
        if (!map || !Array.isArray(coords) || coords.length < 2) return;
        let alive = true;

        const lineSrcId = 'route-line-src';
        const segSrcId = 'route-segments-src';
        const termSrcId = 'route-terminals-src';
        const arrowPtsSrcId = 'route-arrows-pts-src';

        const casingId = 'route-casing';
        const lineId = 'route-main';
        const segId = 'route-segments';
        const arrowId = 'route-arrows';
        const termCirclesId = 'route-terminals';
        const termLabelsId = 'route-terminal-labels';

        const addOrUpdateAll = () => {
            if (!alive) return;
            const lineFC: FeatureCollection<LineString> = {
                type: 'FeatureCollection',
                features: [{ type: 'Feature', properties: {}, geometry: { type: 'LineString', coordinates: coords as any } }],
            };
            const segFC = segmentsFromCoords(coords);
            const termFC = terminalsFromCoords(coords);
            const arrowPtsFC = arrowPointsFromCoords(coords);

            // sources
            if (!map.getSource(lineSrcId)) {
                try { map.addSource(lineSrcId, { type: 'geojson', data: lineFC }); } catch (e) { console.error('[route] addSource(line) failed', e); }
            }
            if (!map.getSource(segSrcId)) {
                try { map.addSource(segSrcId, { type: 'geojson', data: segFC }); } catch (e) { console.error('[route] addSource(seg) failed', e); }
            }
            if (!map.getSource(termSrcId)) {
                try { map.addSource(termSrcId, { type: 'geojson', data: termFC }); } catch (e) { console.error('[route] addSource(term) failed', e); }
            }
            if (!map.getSource(arrowPtsSrcId)) {
                try { map.addSource(arrowPtsSrcId, { type: 'geojson', data: arrowPtsFC }); } catch (e) { console.error('[route] addSource(arrows) failed', e); }
            }
            
            // data updates
            (map.getSource(lineSrcId) as GeoJSONSource).setData(lineFC);
            (map.getSource(segSrcId) as GeoJSONSource).setData(segFC);
            (map.getSource(termSrcId) as GeoJSONSource).setData(termFC);
            (map.getSource(arrowPtsSrcId) as GeoJSONSource).setData(arrowPtsFC);

            ensureArrowImage(map);

            // layers (idempotent)
            if (!map.getLayer(casingId)) {
                map.addLayer({
                    id: casingId, type: 'line', source: lineSrcId,
                    layout: { 'line-cap': 'round', 'line-join': 'round' },
                    paint: { 'line-color': '#0f172a', 'line-width': 8, 'line-opacity': 0.9, 'line-blur': 0.5 },
                }, layerBeforeId || undefined);
            }
            if (!map.getLayer(lineId)) {
                map.addLayer({
                    id: lineId, type: 'line', source: lineSrcId,
                    layout: { 'line-cap': 'round', 'line-join': 'round' },
                    paint: { 'line-color': '#67e8f9', 'line-width': 4, 'line-opacity': 0.95 },
                }, layerBeforeId || undefined);
            }
            if (!map.getLayer(segId)) {
                map.addLayer({
                    id: segId, type: 'line', source: segSrcId,
                    layout: { 'line-cap': 'round', 'line-join': 'round' },
                    paint: { 'line-color': ['get', 'stroke'], 'line-width': 3, 'line-opacity': 0.9, 'line-offset': ['get', 'offset'], 'line-dasharray': [1.2, 0.8] },
                }, layerBeforeId || undefined);
            }
            if (!map.getLayer(arrowId)) {
                map.addLayer({
                    id: arrowId, type: 'symbol', source: arrowPtsSrcId,
                    layout: {
                        'symbol-placement': 'point',
                        'icon-image': 'route-arrow',
                        'icon-size': 0.55,
                        'icon-rotation-alignment': 'map',
                        'icon-keep-upright': false,
                        'icon-rotate': ['get', 'bearing'],
                        'icon-allow-overlap': true
                    },
                    paint: { 'icon-opacity': 0.9 }
                }, layerBeforeId || undefined);
            }
            if (!map.getLayer(termCirclesId)) {
                map.addLayer({
                    id: termCirclesId, type: 'circle', source: termSrcId,
                    paint: {
                        'circle-radius': 7,
                        'circle-color': ['match', ['get', 'kind'], 'start', '#10b981', 'end', '#ef4444', '#ffffff'],
                        'circle-stroke-color': '#ffffff', 'circle-stroke-width': 2,
                    },
                }, layerBeforeId || undefined);
            }
            if (!map.getLayer(termLabelsId)) {
                map.addLayer({
                    id: termLabelsId, type: 'symbol', source: termSrcId,
                    layout: { 'text-field': ['get', 'label'], 'text-size': 11, 'text-font': ['Open Sans Bold', 'Arial Unicode MS Bold'], 'text-offset': [0, 0.9] },
                    paint: { 'text-color': '#0f172a', 'text-halo-color': '#ffffff', 'text-halo-width': 1.2 },
                }, layerBeforeId || undefined);
            }
        };

        const onStyleData = () => {
            if (!alive) return;
            if (map.isStyleLoaded()) addOrUpdateAll();
        };

        // initial pass
        if (map.isStyleLoaded()) addOrUpdateAll();
        map.on('styledata', onStyleData);

        return () => {
            alive = false;
            map.off('styledata', onStyleData);
            [termLabelsId, termCirclesId, arrowId, segId, lineId, casingId].forEach(id => { if (map.getLayer(id)) map.removeLayer(id); });
            [termSrcId, segSrcId, lineSrcId, arrowPtsSrcId].forEach(id => { if (map.getSource(id)) map.removeSource(id); });
        };
        // re-run on coords change or when insertion target changes
    }, [map, depsHash, layerBeforeId]);

    return null;
}
