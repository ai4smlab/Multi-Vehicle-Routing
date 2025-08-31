import { describe, it, expect } from 'vitest';
import { getVrpSpec, evaluateRequirements } from '@/utils/capabilityHelpers';

// --- Capabilities fixture (copy of what backend returns) ---
const CAPS = {
  data: {
    solvers: [
      {
        name: 'mapbox_optimizer',
        vrp_types: {
          TSP: {
            required: ['waypoints', 'fleet==1'],
            optional: ['roundtrip','depot_index','end_index','profile','annotations','radiuses','bearings','approaches','geometries','steps']
          },
          PD: {
            required: ['waypoints','fleet==1','pickup_delivery_pairs'],
            optional: ['roundtrip','depot_index','end_index','profile','annotations','radiuses','bearings','approaches','geometries','steps']
          }
        }
      },
      {
        name: 'ortools',
        vrp_types: {
          TSP:   { required: ['matrix.distances','fleet>=1','depot_index'], optional: ['matrix.durations','weights'] },
          CVRP:  { required: ['matrix.distances','fleet>=1','demands','depot_index'], optional: ['matrix.durations','node_service_times','weights'] },
          VRPTW: { required: ['matrix.durations','node_time_windows','fleet>=1','depot_index'], optional: ['matrix.distances','node_service_times','weights'] },
          PDPTW: { required: ['matrix.durations','node_time_windows','pickup_delivery_pairs','demands','fleet>=1','depot_index'], optional: ['matrix.distances','node_service_times','weights'] }
        }
      },
      {
        name: 'pyomo',
        vrp_types: {
          TSP:   { required: ['matrix.distances','fleet>=1','depot_index'], optional: [] },
          CVRP:  { required: ['matrix.distances','fleet>=1','demands','depot_index'], optional: [] },
          VRPTW: { required: ['matrix.durations','node_time_windows','fleet>=1','depot_index'], optional: [] }
        }
      },
      {
        name: 'vroom',
        vrp_types: {
          TSP: { required: ['waypoints|matrix','fleet==1','depot_index'], optional: ['weights'] }
        }
      }
    ],
    adapters: [
      { name: 'google',          provides: ['matrix.distances','matrix.durations'] },
      { name: 'haversine',       provides: ['matrix.distances'] },
      { name: 'mapbox',          provides: ['matrix.distances','matrix.durations'] },
      { name: 'openrouteservice',provides: ['matrix.distances','matrix.durations'] },
      { name: 'osm_graph',       provides: ['matrix.distances','matrix.durations'] }
    ]
  }
};

// --- Build a minimal payload the front-end would send for a given combo ---
function buildPayload(vrpType: string, adapterProvides: string[]) {
  const haveDist = adapterProvides.includes('matrix.distances');
  const haveDur  = adapterProvides.includes('matrix.durations');

  // 3 nodes: depot(0) + 2 stops
  const payload: any = {
    fleet: { vehicles: [{ id: 'veh-1', capacity: [5], start: 0, end: 0 }] }, // satisfies fleet==1 and fleet>=1
    depot_index: 0,
    waypoints: [
      { id: '0', coordinates: [0,0] },
      { id: '1', coordinates: [1,1] },
      { id: '2', coordinates: [2,2] }
    ]
  };

  if (haveDist || haveDur) payload.matrix = {};
  if (haveDist) payload.matrix.distances = [[0,10,20],[10,0,15],[20,15,0]];
  if (haveDur)  payload.matrix.durations = [[0,600,1200],[600,0,900],[1200,900,0]];

  // Type-specific fields we *can* provide generically
  if (vrpType === 'CVRP' || vrpType === 'PDPTW') payload.demands = [0,1,1];
  if (vrpType === 'VRPTW' || vrpType === 'PDPTW') {
    payload.node_time_windows  = [[0,86400],[0,86400],[0,86400]];
    payload.node_service_times = [0,10,10]; // optional in many specs, but fine to include
  }
  if (vrpType === 'PD' || vrpType === 'PDPTW') {
    // Just presence is checked by evaluateRequirements
    payload.pickup_delivery_pairs = [[1,2]];
  }

  return payload;
}

// Can the adapter *in principle* satisfy a required token?
function adapterCan(token: string, provides: string[]): boolean {
  switch (token) {
    case 'matrix.distances': return provides.includes('matrix.distances');
    case 'matrix.durations': return provides.includes('matrix.durations');
    case 'waypoints|matrix': return true; // we always include waypoints
    case 'waypoints':        return true; // we include waypoints
    // everything else we always add in buildPayload
    default:                 return true;
  }
}

describe('capability matrix: every (solver, vrpType, adapter)', () => {
  const { solvers, adapters } = CAPS.data;

  for (const solver of solvers) {
    for (const vrpType of Object.keys(solver.vrp_types)) {
      for (const adapter of adapters) {
        const title = `${solver.name} / ${vrpType} with ${adapter.name}`;
        it(title, () => {
          // 1) What this combo *requires*
          const spec = getVrpSpec(CAPS.data as any, solver.name, vrpType);
          const required = spec?.required ?? [];

          // 2) Build the payload our frontend should craft
          const payload = buildPayload(vrpType, adapter.provides);

          // 3) What we *expect* given the adapter’s capabilities
          const expectedAllOk = required.every(t => adapterCan(t, adapter.provides));

          // 4) What we actually satisfy per helper
          const checks = evaluateRequirements(CAPS.data as any, solver.name, vrpType, payload);
          const byToken = Object.fromEntries(checks.map(c => [c.token, c.ok]));
          const actualAllOk = required.every(t => !!byToken[t]);

          // Helpful debug if it fails
          if (expectedAllOk !== actualAllOk) {
            // eslint-disable-next-line no-console
            console.log('Mismatch', {
              solver: solver.name, vrpType, adapter: adapter.name,
              required,
              adapterProvides: adapter.provides,
              missing: required.filter(t => !byToken[t])
            });
          }

          expect(actualAllOk).toBe(expectedAllOk);
        });
      }
    }
  }
});
