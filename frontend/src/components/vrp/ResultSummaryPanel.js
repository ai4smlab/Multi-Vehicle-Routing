// src/components/sidebar/ResultSummaryPanel.js
'use client';
import { useMemo, useEffect } from 'react';
import Section from '@/components/sidebar/Section';
import useRouteStore from '@/hooks/useRouteStore';
import CurrentRunBox from '@/components/sidebar/CurrentRunBox';
import { computeGapPct } from '@/utils/metrics';

function km(m) { return (Number(m) / 1000).toFixed(2); }
function min(s) { return Math.round(Number(s) / 60); }

function collectTotals(run) {
  if (!run) return null;
  const s = run?.summary || run?.totals || {};
  let distanceMeters = Number(s.distanceMeters ?? s.distance ?? run?.meta?.distance ?? NaN);
  let durationSeconds = Number(s.durationSeconds ?? s.duration ?? NaN);

  const legs = (run?.data?.routes || run?.routes || []);
  if ((!Number.isFinite(distanceMeters) || distanceMeters <= 0) && Array.isArray(legs)) {
    distanceMeters = legs.reduce((a, r) => a + (Number(r?.total_distance) || 0), 0);
  }
  if ((!Number.isFinite(durationSeconds) || durationSeconds <= 0) && Array.isArray(legs)) {
    durationSeconds = legs.reduce((a, r) => a + (Number(r?.total_duration) || 0), 0);
  }

  let vehiclesUsed =
    Number(s.vehiclesUsed) ||
    (Array.isArray(legs) ? legs.filter(r => Array.isArray(r?.waypoint_ids) && r.waypoint_ids.length >= 2).length : 0);
  if (vehiclesUsed === 0 && Array.isArray(legs) && legs.length) vehiclesUsed = 1;

  const emissionsTotal =
    Number(s.emissions) ||
    (Array.isArray(legs) ? legs.reduce((a, r) => a + (Number(r?.emissions) || 0), 0) : 0);

  return {
    distanceMeters: Number(distanceMeters) || 0,
    durationSeconds: Number(durationSeconds) || 0,
    vehiclesUsed: Number(vehiclesUsed) || 1,
    emissions: Number(emissionsTotal) || 0,
  };
}

export default function ResultSummaryPanel() {
  const routes = useRouteStore(s =>
  (Array.isArray(s.routes) && s.routes.length ? s.routes :
    (Array.isArray(s.runs) ? s.runs : []))
  );
  const currentIndex = useRouteStore(s => Number.isInteger(s.currentIndex) ? s.currentIndex : 0);
  const setIndexFn = useRouteStore(s => s.setIndex);
  const safeSetIndex = (i) => {
    if (typeof setIndexFn === 'function') return setIndexFn(i);
    useRouteStore.setState({ currentIndex: i });
  };

  const removeAt = useRouteStore(s => s.removeRouteAt) || ((i) => useRouteStore.setState(s => {
    const next = (Array.isArray(s.runs) ? [...s.runs] : []);
    const idx = Math.max(0, Math.min(next.length - 1, Number(i) || 0));
    next.splice(idx, 1);
    return { runs: next, routes: next, currentIndex: 0, activeRunId: next[0]?.id ?? null };
  }));
  const clearAll = useRouteStore(s => s.clearAllRoutes) || (() => useRouteStore.setState({ runs: [], routes: [], currentIndex: 0, activeRunId: null }));

  // keep index valid
  useEffect(() => {
    const n = routes?.length ?? 0;
    if (!n) return;
    if (!Number.isInteger(currentIndex) || currentIndex < 0 || currentIndex >= n) {
      safeSetIndex(0);
    }
  }, [routes, currentIndex]);

  const current = routes?.[currentIndex] ?? null;
  const totals = useMemo(() => collectTotals(current), [current]);

  const bestIndex = useMemo(() => {
    if (!routes?.length) return -1;
    let j = -1, best = Infinity;
    for (let i = 0; i < routes.length; i++) {
      const t = collectTotals(routes[i]);
      if (t && t.distanceMeters < best) { best = t.distanceMeters; j = i; }
    }
    return j;
  }, [routes]);

  const ecoIndex = useMemo(() => {
    if (!routes?.length) return -1;
    let j = -1, bestEm = Infinity;
    for (let i = 0; i < routes.length; i++) {
      const t = collectTotals(routes[i]);
      if (Number.isFinite(t?.emissions) && t.emissions < bestEm) { bestEm = t.emissions; j = i; }
    }
    return j;
  }, [routes]);

  const { bestKnownKm, gapPct } = useMemo(() => {
    if (!current) return { bestKnownKm: null, gapPct: null };
    const bestMeters =
      Number(current?.meta?.comparison?.best) ||
      Number(current?.meta?.benchmark?.bestKnown) ||
      Number(current?.meta?.benchmark?.bestKnownMeters) || null;
    const bestKm = Number.isFinite(bestMeters)
      ? bestMeters / 1000
      : (Number.isFinite(current?.meta?.benchmark?.bestKnownKm) ? current.meta.benchmark.bestKnownKm : null);
    const ourMeters =
      Number(current?.meta?.comparison?.ours) ||
      Number(totals?.distanceMeters ?? 0);
    return {
      bestKnownKm: bestKm,
      gapPct: computeGapPct(bestKm, ourMeters > 0 ? ourMeters / 1000 : null),
    };
  }, [current, totals]);

  const onPrev = () => safeSetIndex(Math.max(0, currentIndex - 1));
  const onNext = () => safeSetIndex(Math.min((routes?.length ?? 1) - 1, currentIndex + 1));
  const onBest = () => { if (bestIndex >= 0) safeSetIndex(bestIndex); };
  const onEco = () => { if (ecoIndex >= 0) safeSetIndex(ecoIndex); };
  const onExport = () => {
    if (!current) return;
    const blob = new Blob([JSON.stringify(current, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a'); a.href = url; a.download = `route-${currentIndex + 1}.json`; a.click();
    URL.revokeObjectURL(url);
  };
  const onClearCurrent = () => { if (routes?.length) removeAt?.(currentIndex); };

  const hasActive = !!current;

  return (
    <Section title="📊 VRP Result Summary">
      {!hasActive && <div className="text-sm text-gray-500">No routes yet.</div>}

      {hasActive && totals && (
        <div className="text-sm space-y-1 mb-4">
          <div className="font-medium">Active Run</div>
          <div>Solver: <strong>{current?.meta?.solver ?? 'unknown'}</strong></div>
          <div>Adapter: <strong>{current?.meta?.adapter ?? 'unknown'}</strong></div>
          <div>Type: <strong>{current?.meta?.vrpType ?? 'unknown'}</strong></div>

          <div><strong>Total Distance:</strong> {km(totals.distanceMeters)} km</div>
          <div><strong>Total Duration:</strong> {min(totals.durationSeconds)} min</div>
          <div><strong>Vehicles Used:</strong> {Math.max(1, Number(totals.vehiclesUsed || 0))}</div>
          {Number.isFinite(totals.emissions) && totals.emissions > 0 && (
            <div><strong>Total Emissions:</strong> {totals.emissions.toFixed(2)}</div>
          )}

          {current?.meta?.benchmark && (
            <div className="mt-2 text-xs">
              <div className="font-semibold">Benchmark</div>
              <div>{current.meta.benchmark.dataset} / {current.meta.benchmark.name}</div>
              <div>
                {Number.isFinite(bestKnownKm)
                  ? <>Best-known: {bestKnownKm.toFixed(2)} km</>
                  : <span className="text-gray-400">Best-known: —</span>}
              </div>
              <div>Our result: {km(totals.distanceMeters)} km</div>
              <div className={
                Number.isFinite(gapPct)
                  ? (gapPct <= 0 ? 'text-emerald-400' : 'text-amber-300')
                  : 'text-gray-400'
              }>
                Gap: {Number.isFinite(gapPct) ? `${gapPct.toFixed(2)}%` : '—'}
              </div>
            </div>
          )}
        </div>
      )}

      {hasActive && <CurrentRunBox />}

      {hasActive && (
        <>
          <div className="flex gap-2 flex-wrap mb-4">
            <button onClick={onBest} disabled={bestIndex < 0} className="text-xs px-2 py-1 bg-green-600 text-white rounded disabled:opacity-50">
              Best Route
            </button>
            <button onClick={onEco} disabled={ecoIndex < 0} className="text-xs px-2 py-1 bg-yellow-600 text-white rounded disabled:opacity-50">
              Eco Route
            </button>
            <button onClick={onPrev} disabled={currentIndex <= 0} className="text-xs px-2 py-1 bg-gray-500 text-white rounded disabled:opacity-50">⬅ Prev</button>
            <button onClick={onNext} disabled={currentIndex >= (routes?.length ?? 1) - 1} className="text-xs px-2 py-1 bg-gray-500 text-white rounded disabled:opacity-50">Next ➡</button>
          </div>

          <div className="flex gap-2 flex-wrap">
            <button onClick={onExport} className="text-xs px-3 py-1 bg-blue-600 text-white rounded">Export</button>
            <button onClick={onClearCurrent} className="text-xs px-3 py-1 bg-orange-600 text-white rounded">Clear Current</button>
            <button onClick={clearAll} className="text-xs px-3 py-1 bg-red-600 text-white rounded">Clear All</button>
          </div>
        </>
      )}
    </Section>
  );
}
