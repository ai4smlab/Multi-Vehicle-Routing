import { describe, it, expect, beforeEach } from 'vitest';
import useRouteStore from '@/hooks/useRouteStore';

describe('useRouteStore.addSolutionFromSolver', () => {
  beforeEach(() => {
    const s = useRouteStore.getState();
    s.clearAllRoutes?.();
  });

  it('normalizes waypoint_ids → coords', () => {
    const waypoints = [
      { id: '0', coordinates: [10, 20] },
      { id: '1', coordinates: [30, 40] },
    ];

    const solveRes = {
      data: {
        routes: [
          { vehicle_id: 'veh-1', waypoint_ids: ['0', '1', '0'], total_distance: 123 }
        ]
      }
    };

    useRouteStore.getState().addSolutionFromSolver(solveRes, waypoints, {
      solver: 'ortools', adapter: 'haversine', vrpType: 'TSP', id: 'run-1'
    });

    const st = useRouteStore.getState();
    expect(st.routes.length).toBe(1);
    expect(st.routes[0].coords).toEqual([[10, 20], [30, 40], [10, 20]]);
  });
});
