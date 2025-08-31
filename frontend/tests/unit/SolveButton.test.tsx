// tests/unit/SolveButton.test.tsx
import React from 'react';
import { describe, it, beforeEach, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

import SolveButton from '@/components/vrp/SolveButton';
import useWaypointStore from '@/hooks/useWaypointStore';
import useFleetStore from '@/hooks/useFleetStore';
import useRouteStore from '@/hooks/useRouteStore';

// ---- Mock the backend hooks used by SolveButton
const dmMock = vi.fn();
const solveMock = vi.fn();

vi.mock('@/hooks/useBackend', () => ({
  useDistanceMatrix: () => ({
    mutateAsync: dmMock,
    isPending: false
  }),
  useSolve: () => ({
    mutateAsync: solveMock,
    isPending: false
  })
}));

// utility to seed state before each test
const resetAll = () => {
  useWaypointStore.setState({ waypoints: [] }, false);
  useFleetStore.setState({ vehicles: [] }, false);
  useRouteStore.setState({ routes: [], summary: null, currentIndex: 0 }, false);

  dmMock.mockReset();
  solveMock.mockReset();
};

describe('SolveButton', () => {
  beforeEach(() => resetAll());

  it('disables button with < 2 waypoints', () => {
    render(<SolveButton solver="ortools" adapter="haversine" vrpType="TSP" />);
    const btn = screen.getByRole('button', { name: /solve/i });
    expect(btn).toBeDisabled();
  });

  it('TSP: builds matrix and stores a route', async () => {
    // seed two waypoints
    useWaypointStore.setState({
      waypoints: [
        { id: '0', coordinates: [1, 2] },
        { id: '1', coordinates: [3, 4] }
      ]
    }, false);

    // mock /distance-matrix
    dmMock.mockResolvedValue({
      data: { matrix: { distances: [[0, 1000],[1000, 0]] } }
    });

    // mock /solver response
    solveMock.mockResolvedValue({
      data: {
        status: 'success',
        message: 'Solution found',
        routes: [{ vehicle_id: 'veh-1', waypoint_ids: ['0','1','0'], total_distance: 2000 }]
      }
    });

    render(<SolveButton solver="ortools" adapter="haversine" vrpType="TSP" />);

    const btn = screen.getByRole('button', { name: /solve/i });
    expect(btn).not.toBeDisabled();
    fireEvent.click(btn);

    // matrix called with origins=destinations coords
    await waitFor(() => expect(dmMock).toHaveBeenCalledTimes(1));
    const dmPayload = dmMock.mock.calls[0][0];
    expect(dmPayload.adapter).toBe('haversine');
    expect(dmPayload.origins.length).toBe(2);
    expect(dmPayload.destinations.length).toBe(2);

    // solver called with matrix and TSP fields
    await waitFor(() => expect(solveMock).toHaveBeenCalledTimes(1));
    const solvePayload = solveMock.mock.calls[0][0];
    expect(solvePayload.solver).toBe('ortools');
    expect(solvePayload.matrix?.distances).toEqual([[0,1000],[1000,0]]);
    expect(solvePayload.demands).toBeUndefined();

    // route stored
    await waitFor(() => {
      const st = useRouteStore.getState();
      expect(st.routes.length).toBe(1);
      expect(st.routes[0].waypointIds).toEqual(['0','1','0']);
    });
  });

  it('CVRP: includes demands in payload', async () => {
    useWaypointStore.setState({
      waypoints: [
        { id:'0', coordinates:[0,0] },
        { id:'1', coordinates:[1,1], demand: 2 },
        { id:'2', coordinates:[2,2], demand: 1 },
      ]
    }, false);

    dmMock.mockResolvedValue({
      data: { matrix: { distances: [[0, 10, 20],[10,0,15],[20,15,0]] } }
    });

    solveMock.mockResolvedValue({
      data: { status:'success', routes: [{ vehicle_id:'veh-1', waypoint_ids:['0','1','2','0'] }] }
    });

    render(<SolveButton solver="ortools" adapter="haversine" vrpType="CVRP" />);
    fireEvent.click(screen.getByRole('button', { name: /solve/i }));

    await waitFor(() => expect(solveMock).toHaveBeenCalled());
    const payload = solveMock.mock.calls[0][0];
    expect(Array.isArray(payload.demands)).toBe(true);
    // depot demand should be 0
    expect(payload.demands[0]).toBe(0);
  });

  it('VRPTW: includes time windows & service times', async () => {
    useWaypointStore.setState({
      waypoints: [
        { id:'0', coordinates:[0,0] },
        { id:'1', coordinates:[1,1], timeWindow: [0, 3600], serviceTime: 10 },
        { id:'2', coordinates:[2,2], timeWindow: [1800, 7200], serviceTime: 20 },
      ]
    }, false);

    dmMock.mockResolvedValue({
      data: { matrix: { distances: [[0, 10, 20],[10,0,15],[20,15,0]] } }
    });

    solveMock.mockResolvedValue({
      data: { status:'success', routes: [{ vehicle_id:'veh-1', waypoint_ids:['0','1','2','0'] }] }
    });

    render(<SolveButton solver="ortools" adapter="haversine" vrpType="VRPTW" />);
    fireEvent.click(screen.getByRole('button', { name: /solve/i }));

    await waitFor(() => expect(solveMock).toHaveBeenCalled());
    const payload = solveMock.mock.calls[0][0];
    expect(Array.isArray(payload.node_time_windows)).toBe(true);
    expect(Array.isArray(payload.node_service_times)).toBe(true);
    expect(payload.node_time_windows.length).toBe(3);
    expect(payload.node_service_times.length).toBe(3);
  });
});
