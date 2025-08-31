// tests/unit/routeStore.more.test.ts
import { describe, it, beforeEach, expect } from 'vitest';
import useRouteStore from '@/hooks/useRouteStore';

const resetRoutes = () => {
  useRouteStore.setState({ routes: [], summary: null, currentIndex: 0 }, false);
};

describe('useRouteStore – more cases', () => {
  beforeEach(() => {
    resetRoutes();
  });

  it('maps numeric waypoint_ids to coords (fallback)', () => {
    const waypoints = [
      { id: 'wp-a', coordinates: [10, 20] },
      { id: 'wp-b', coordinates: [30, 40] }
    ];

    const solveRes = {
      data: {
        routes: [
          { vehicle_id: 'veh-1', waypoint_ids: ['0','1','0'], total_distance: 1234 }
        ]
      }
    };

    useRouteStore.getState().addSolutionFromSolver(solveRes, waypoints, { solver:'ortools', adapter:'haversine', vrpType:'TSP', id:'run-1' });

    const st = useRouteStore.getState();
    expect(st.routes.length).toBe(1);
    expect(st.routes[0].coords).toEqual([[10,20],[30,40],[10,20]]);
    expect(st.summary?.routeCount).toBe(1);
    expect(st.currentIndex).toBe(0);
  });

  it('removeRouteAt updates summary and clamps currentIndex', () => {
    const waypoints = [
      { id: '0', coordinates: [0, 0] },
      { id: '1', coordinates: [1, 1] },
      { id: '2', coordinates: [2, 2] }
    ];

    const solveRes = {
      data: {
        routes: [
          { vehicle_id: 'veh-1', waypoint_ids: ['0','1','0'], total_distance: 100 },
          { vehicle_id: 'veh-2', waypoint_ids: ['0','2','0'], total_distance: 200 }
        ]
      }
    };

    const S = useRouteStore.getState();
    S.addSolutionFromSolver(solveRes, waypoints, { solver:'ortools', adapter:'haversine', vrpType:'TSP', id:'run-2' });
    expect(useRouteStore.getState().routes.length).toBe(2);

    // Select the last route then remove index 1
    useRouteStore.getState().setIndex(1);
    useRouteStore.getState().removeRouteAt(1);

    let st = useRouteStore.getState();
    expect(st.routes.length).toBe(1);
    expect(st.summary?.routeCount).toBe(1);
    // currentIndex should clamp back to 0
    expect(st.currentIndex).toBe(0);

    // Removing the remaining route leaves store empty
    st.removeRouteAt(0);
    st = useRouteStore.getState();
    expect(st.routes.length).toBe(0);
    expect(st.summary).toBeNull();
    expect(st.currentIndex).toBe(0);
  });

  it('setIndex clamps to valid range', () => {
    // No routes yet — any setIndex should clamp to 0
    useRouteStore.getState().setIndex(999);
    expect(useRouteStore.getState().currentIndex).toBe(0);

    // Add one route, index should still clamp between [0..0]
    const solveRes = { data: { routes: [{ vehicle_id:'veh-1', waypoint_ids:['0','0'], total_distance: 1 }] } };
    const wps = [{ id: '0', coordinates: [0,0] }];
    useRouteStore.getState().addSolutionFromSolver(solveRes, wps, { id: 'run-3' });

    useRouteStore.getState().setIndex(-10);
    expect(useRouteStore.getState().currentIndex).toBe(0);
    useRouteStore.getState().setIndex(5);
    expect(useRouteStore.getState().currentIndex).toBe(0);
  });

  it('clearAllRoutes resets everything', () => {
    useRouteStore.setState({
      routes: [{ coords: [[0,0],[1,1]], totalDistance: 10, totalDuration: 1, meta: { id:'x' } }],
      summary: { label:'Best Route', totalDistance: 10, totalDuration: 1, vehiclesUsed: 1, routeCount: 1 },
      currentIndex: 0
    }, false);

    useRouteStore.getState().clearAllRoutes();
    const st = useRouteStore.getState();
    expect(st.routes).toEqual([]);
    expect(st.summary).toBeNull();
    expect(st.currentIndex).toBe(0);
  });
});
