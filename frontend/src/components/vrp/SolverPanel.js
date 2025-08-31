'use client';
import { useEffect, useMemo } from 'react';
import Section from '@/components/sidebar/Section';
import { useCapabilities } from '@/hooks/useBackend';
import useUiStore from '@/hooks/useUIStore';
import useWaypointStore from '@/hooks/useWaypointStore';
import useFleetStore from '@/hooks/useFleetStore';
import { evaluateRequirements, getVrpSpec, getSolverSpec } from '@/utils/capabilityHelpers';
import SolveButton from '@/components/vrp/SolveButton';

export default function SolverPanel() {
  const capsQ = useCapabilities();
  const caps = capsQ.data;

  const solverEngine = useUiStore(s => s.solverEngine);
  const setSolverEngine = useUiStore(s => s.setSolverEngine);
  const vrpType = useUiStore(s => s.vrpType);
  const setVrpType = useUiStore(s => s.setVrpType);
  const routingAdapter = useUiStore(s => s.routingAdapter);
  const setRoutingAdapter = useUiStore(s => s.setRoutingAdapter);

  const waypoints = useWaypointStore(s => s.waypoints);
  const fleet = useFleetStore(s => s.vehicles);

  const adapters = useMemo(
    () => caps?.adapters?.map(a => a.name) ?? ['haversine', 'osm_graph', 'openrouteservice', 'google', 'mapbox'],
    [caps]
  );

  const solverNamesFromCaps = useMemo(
    () => (Array.isArray(caps?.solvers) ? caps.solvers.map(s => s.name) : undefined),
    [caps]
  );

  const solverOptions = solverNamesFromCaps ?? ['ortools', 'pyomo', 'vroom', 'mapbox_optimizer'];

  const solverSpec = useMemo(() => getSolverSpec(caps, solverEngine), [caps, solverEngine]);
  const vrpTypes = useMemo(() => {
    const keys = Object.keys(solverSpec?.vrp_types || {});
    return keys.length ? keys : (vrpType ? [vrpType] : []);
  }, [solverSpec, vrpType]);
  useEffect(() => {
    if (solverSpec && !solverSpec.vrp_types?.[vrpType] && vrpTypes.length) {
      console.debug('[SolverPanel] snap VRP type ->', vrpTypes[0]);
      setVrpType(vrpTypes[0]);
    }
  }, [solverSpec, vrpType, vrpTypes, setVrpType]);

  const ctx = useMemo(() => ({
    depotIndex: 0,
    waypoints,
    fleet: { vehicles: fleet },
    demands: waypoints.map(w => w.demand ?? 0),
    node_time_windows: waypoints.map(w => Array.isArray(w.timeWindow) ? w.timeWindow : null),
    node_service_times: waypoints.map(w => w.serviceTime ?? 0),
    pickup_delivery_pairs: [],
    weights: null,
  }), [waypoints, fleet]);

  const reqChecks = useMemo(() => {
    try { return evaluateRequirements(caps, solverEngine, vrpType, ctx); }
    catch { return []; }
  }, [caps, solverEngine, vrpType, ctx]);

  const spec = useMemo(() => getVrpSpec(caps, solverEngine, vrpType), [caps, solverEngine, vrpType]);
  const optional = spec?.optional ?? [];

  const optChecks = useMemo(() => {
    if (!Array.isArray(optional) || !optional.length) return [];
    try { return evaluateRequirements({ rules: optional }, solverEngine, vrpType, ctx); }
    catch {
      try { return evaluateRequirements(optional, ctx); }
      catch { return []; }
    }
  }, [optional, solverEngine, vrpType, ctx]);

  return (
    <Section title="🧠 Solver">
      {/* Solver */}
      <label className="block text-sm font-medium mb-1">Solver</label>
      <select
        className="w-full border rounded p-1 text-sm mb-2"
        value={solverEngine}
        onChange={(e) => { console.debug('[SolverPanel] set solver', e.target.value); setSolverEngine(e.target.value); }}
      >
        {solverOptions.map(n => <option key={n} value={n}>{n}</option>)}
      </select>

      {/* VRP Type */}
      <label className="block text-sm font-medium mb-1">VRP Type</label>
      <select
        className="w-full border rounded p-1 text-sm mb-2"
        value={vrpType}
        onChange={(e) => { console.debug('[SolverPanel] set vrpType', e.target.value); setVrpType(e.target.value); }}
      >
        {vrpTypes.map(t => <option key={t} value={t}>{t}</option>)}
      </select>

      {/* Routing Adapter */}
      <label className="block text-sm font-medium mb-1">Routing Adapter</label>
      <select
        className="w-full border rounded p-1 text-sm mb-2"
        value={routingAdapter}
        onChange={(e) => { console.debug('[SolverPanel] set adapter', e.target.value); setRoutingAdapter(e.target.value); }}
      >
        {adapters.map(a => <option key={a} value={a}>{a}</option>)}
      </select>

      {/* Requirements */}
      <div className="mt-2">
        <div className="text-xs font-semibold mb-1">Required / Present</div>
        <ul className="text-xs space-y-1">
          {reqChecks.map(({ token, ok }) => (
            <li key={token} className="flex items-center gap-2">
              <span className={`inline-block w-2 h-2 rounded-full ${ok ? 'bg-emerald-500' : 'bg-red-500'}`} />
              <span>{token}</span>
            </li>
          ))}
        </ul>

        {optChecks.length > 0 && (
          <>
            <div className="text-xs font-semibold mt-2 mb-1">Optional</div>
            <ul className="text-xs space-y-1">
              {optChecks.map(({ token, ok }) => (
                <li key={token} className="flex items-center gap-2">
                  <span className={`inline-block w-2 h-2 rounded-full ${ok ? 'bg-emerald-400' : 'bg-gray-300'}`} />
                  <span>{token}</span>
                </li>
              ))}
            </ul>
          </>
        )}
      </div>

      {/* Solve */}
      <div className="mt-2">
        <SolveButton />
      </div>
    </Section>
  );
}
