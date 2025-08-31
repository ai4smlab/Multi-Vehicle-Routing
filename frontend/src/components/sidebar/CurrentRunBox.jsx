// src/components/sidebar/CurrentRunBox.jsx
'use client';
import useRouteStore from '@/hooks/useRouteStore';

function km(m) { return (Number(m) / 1000).toFixed(2); }
function min(s) { return Math.round(Number(s) / 60); }

export default function CurrentRunBox() {
  const routes = useRouteStore(s =>
    (Array.isArray(s.routes) && s.routes.length ? s.routes :
     (Array.isArray(s.runs) ? s.runs : []))
  );
  const currentIndex = useRouteStore(s => Number.isInteger(s.currentIndex) ? s.currentIndex : 0);

  const run = routes?.[currentIndex] ?? null;
  const legs = (run?.data?.routes && run.data.routes) || (run?.routes && run.routes) || [];
  if (!run) return null;

  return (
    <div className="rounded border border-slate-700 bg-slate-800/50 p-2 mb-3">
      <div className="text-xs font-semibold mb-1">Per-vehicle</div>
      {(!legs || legs.length === 0) && <div className="text-xs text-gray-400">No vehicle legs.</div>}
      {Array.isArray(legs) && legs.map((r, idx) => {
        const ids = Array.isArray(r?.waypoint_ids) ? r.waypoint_ids : [];
        // Basic stop estimate: exclude depot at both ends if closed
        const stops = ids.length >= 2 && ids[0] === ids[ids.length - 1]
          ? Math.max(0, ids.length - 2)
          : Math.max(0, ids.length - 1);

        return (
          <div key={idx} className="text-xs py-1 border-t border-slate-700/60 first:border-t-0">
            <div className="font-medium">{String(r?.vehicle_id ?? `veh-${idx+1}`)}</div>
            <div className="opacity-80">{stops} {stops === 1 ? 'stop' : 'stops'}</div>
            <div>Distance: {km(Number(r?.total_distance) || 0)} km</div>
            <div>Duration: {min(Number(r?.total_duration) || 0)} min</div>
            <div>Cost: —</div>
            <div>Emissions: {Number.isFinite(Number(r?.emissions)) ? Number(r.emissions).toFixed(2) : '—'}</div>
            <div>Reliability: —</div>
          </div>
        );
      })}
    </div>
  );
}
