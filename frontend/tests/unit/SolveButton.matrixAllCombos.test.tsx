import React from 'react';
import { describe, it, expect, beforeEach, vi, beforeAll, afterAll } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import SolveButton from '@/components/vrp/SolveButton.jsx';
import useWaypointStore from '@/hooks/useWaypointStore';
import useFleetStore from '@/hooks/useFleetStore';
import useRouteStore from '@/hooks/useRouteStore';
import { getVrpSpec, evaluateRequirements } from '@/utils/capabilityHelpers';


// keep originals in case you want to forward non-matching logs
const originalLog = console.log.bind(console);

beforeAll(() => {
  const MUTE_MARKERS = [
    '🔎 SOLVE DEBUG',
    'matrix.distances shape',
    '📤 /solver payload',
    '📥 /solver response',
  ];

  vi.spyOn(console, 'log').mockImplementation((...args: any[]) => {
    const msg = args.map(String).join(' ');
    if (MUTE_MARKERS.some(m => msg.includes(m))) return; // drop debug
    originalLog(...args); // keep other logs, if any
  });

  vi.spyOn(console, 'debug').mockImplementation(() => {}); // often used for verbose dumps
  vi.spyOn(console, 'info').mockImplementation(() => {});
});

afterAll(() => {
  vi.restoreAllMocks();
});

// Capabilities (same as backend blob you pasted)
const CAPS = {
  data: {
    solvers: [
      {
        name: 'mapbox_optimizer',
        vrp_types: {
          TSP: { required: ['waypoints', 'fleet==1'], optional: ['roundtrip','depot_index','end_index','profile','annotations','radiuses','bearings','approaches','geometries','steps'] },
          PD:  { required: ['waypoints','fleet==1','pickup_delivery_pairs'], optional: ['roundtrip','depot_index','end_index','profile','annotations','radiuses','bearings','approaches','geometries','steps'] }
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

// UI supports these today
const SUPPORTED: Record<string, string[]> = {
  ortools: ['TSP', 'CVRP', 'VRPTW'],
  pyomo:   ['TSP', 'CVRP', 'VRPTW'],
  vroom:   ['TSP'],
  // mapbox_optimizer not yet supported by SolveButton payload builder → skip
};

const durationsAdapters = new Set(['google','mapbox','openrouteservice','osm_graph']);

// ---------- Mocks ----------
type DMFn = (payload: any) => Promise<{ data: { matrix: { distances: number[][]; durations?: number[][] } } }>;
type SolveFn = (payload: any) => Promise<{ data: { status: string; routes: any[] } }>;

const dmMock = vi.fn<DMFn>();
const solveMock = vi.fn<SolveFn>();

vi.mock('@/hooks/useBackend', () => ({
  useDistanceMatrix: () => ({
    isPending: false,
    mutateAsync: dmMock,
  }),
  useSolve: () => ({
    isPending: false,
    mutateAsync: solveMock,
  }),
}));

// ---------- Helpers ----------
function resetStores() {
  useWaypointStore.setState({ waypoints: [] }, false);
  useFleetStore.setState({ vehicles: [] }, false);
  useRouteStore.setState({ routes: [], summary: null, currentIndex: 0 }, false);
}

function seedMinimalData() {
  useWaypointStore.setState({
    waypoints: [
      { id: '0', coordinates: [0, 0] },
      { id: '1', coordinates: [1, 1], demand: 1, timeWindow: [0, 86400], serviceTime: 10 },
      { id: '2', coordinates: [2, 2], demand: 1, timeWindow: [0, 86400], serviceTime: 10 },
    ]
  }, false);
  useFleetStore.setState({
    vehicles: [{ id: 'veh-1', capacity: [5], start: 0, end: 0 }]
  }, false);
}

// Adapter-aware matrix mock (adds durations only if adapter supports them)
function installMatrixMock() {
  dmMock.mockImplementation(async (payload: any) => {
    const a = String(payload?.adapter ?? '');
    const addDur = durationsAdapters.has(a);
    return {
      data: {
        matrix: {
          distances: [[0,10,20],[10,0,15],[20,15,0]],
          ...(addDur ? { durations: [[0,600,1200],[600,0,900],[1200,900,0]] } : {})
        }
      }
    };
  });
}

// Validate required tokens before resolving; if missing → throw (simulates backend)
function installSolveMock(vrpType: string) {
  solveMock.mockImplementation(async (payload: any) => {
    const solverName = String(payload?.solver ?? '');
    const spec = getVrpSpec(CAPS.data as any, solverName, vrpType);
    const req = spec?.required ?? [];
    const checks = evaluateRequirements(CAPS.data as any, solverName, vrpType, payload);
    const by = Object.fromEntries(checks.map(c => [c.token, c.ok]));
    const ok = req.every(t => !!by[t]);
    if (!ok) throw new Error(`Missing required tokens: ${req.filter(t => !by[t]).join(', ')}`);
    // Minimal success body
    return { data: { status: 'success', routes: [{ vehicle_id: 'veh-1', waypoint_ids: ['0','1','2','0'] }] } };
  });
}

function adapterCan(token: string, provides: string[]): boolean {
  switch (token) {
    case 'matrix.distances': return provides.includes('matrix.distances');
    case 'matrix.durations': return provides.includes('matrix.durations');
    case 'waypoints|matrix': return true;   // we always send waypoints
    case 'waypoints':        return true;   // SolveButton certainly has waypoints available
    default:                 return true;   // other tokens we seed in payload via the component logic
  }
}

// ---------- Tests ----------
describe('SolveButton across solver/type/adapter combos', () => {
  beforeEach(() => {
    resetStores();
    dmMock.mockReset();
    solveMock.mockReset();
    seedMinimalData();
    installMatrixMock();
  });

  const { solvers, adapters } = CAPS.data;

  for (const solver of solvers) {
    const supportedTypes = SUPPORTED[solver.name] || [];
    for (const vrpType of Object.keys(solver.vrp_types).filter(t => supportedTypes.includes(t))) {
      for (const adapter of adapters) {
        const title = `${solver.name} / ${vrpType} with ${adapter.name}`;
        it(title, async () => {
          installSolveMock(vrpType);

          // Expected feasibility (from capabilities only)
          const required = (solver.vrp_types as any)[vrpType].required as string[];
          const expectedFeasible = required.every(t => adapterCan(t, adapter.provides));

          render(<SolveButton solver={solver.name} vrpType={vrpType} adapter={adapter.name} />);

          const btn = screen.getByRole('button', { name: /solve/i });
          fireEvent.click(btn);

          if (expectedFeasible) {
            // Should reach backend and store a route
            await waitFor(() => expect(solveMock).toHaveBeenCalled(), { timeout: 2000 });
            await waitFor(() => {
              const st = useRouteStore.getState();
              expect(st.routes.length).toBeGreaterThan(0);
            });
          } else {
            // Should not end up with a stored route
            await waitFor(() => {
              const st = useRouteStore.getState();
              expect(st.routes.length).toBe(0);
            });
          }
        });
      }
    }
  }
});
