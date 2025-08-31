import React from 'react';
import { describe, it, beforeEach, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import SolveButton from '@/components/vrp/SolveButton.jsx';
import useWaypointStore from '@/hooks/useWaypointStore';
import useFleetStore from '@/hooks/useFleetStore';
import useRouteStore from '@/hooks/useRouteStore';

// mocks
const dmMock = vi.fn();
const solveMock = vi.fn();

vi.mock('@/hooks/useBackend', () => ({
  useDistanceMatrix: () => ({ mutateAsync: dmMock, isPending: false }),
  useSolve: () => ({ mutateAsync: solveMock, isPending: false }),
}));

const adapters = ['google','haversine','mapbox','openrouteservice','osm_graph'];

const resetAll = () => {
  useWaypointStore.setState({
    waypoints: [
      { id:'0', coordinates:[0,0], type:'Depot' },         // depot
      { id:'1', coordinates:[1,1], type:'Delivery' },
      { id:'2', coordinates:[2,2], type:'Delivery' },
    ]
  }, false);
  useFleetStore.setState({ vehicles: [{ id:'veh-1', capacity: 10 }] }, false);
  useRouteStore.setState({ routes: [], summary: null, currentIndex: 0 }, false);
  dmMock.mockReset();
  solveMock.mockReset();
};

describe('SolveButton (mapbox_optimizer)', () => {
  beforeEach(resetAll);

  for (const adapter of adapters) {
    it(`TSP with ${adapter}`, async () => {
      solveMock.mockResolvedValue({
        data: { status:'success', routes: [{ vehicle_id:'veh-1', waypoint_ids:['0','1','2','0'] }] }
      });

      render(<SolveButton solver="mapbox_optimizer" adapter={adapter} vrpType="TSP" />);
      fireEvent.click(screen.getByRole('button', { name: /solve/i }));

      // no distance-matrix call for mapbox_optimizer
      await waitFor(() => expect(dmMock).not.toHaveBeenCalled());
      await waitFor(() => {
        const st = useRouteStore.getState();
        expect(st.routes.length).toBe(1);
      });
    });

    it(`PD with ${adapter}`, async () => {
      useWaypointStore.setState({
        waypoints: [
          { id:'0', coordinates:[0,0], type:'Depot' },
          { id:'1', coordinates:[1,1], type:'Pickup',   pairId:'A' },
          { id:'2', coordinates:[2,2], type:'Delivery', pairId:'A' },
        ]
      }, false);

      solveMock.mockResolvedValue({
        data: { status:'success', routes: [{ vehicle_id:'veh-1', waypoint_ids:['0','1','2','0'] }] }
      });

      render(<SolveButton solver="mapbox_optimizer" adapter={adapter} vrpType="PD" />);
      fireEvent.click(screen.getByRole('button', { name: /solve/i }));

      await waitFor(() => expect(dmMock).not.toHaveBeenCalled());
      await waitFor(() => {
        const st = useRouteStore.getState();
        expect(st.routes.length).toBe(1);
      });

      // ensure PD pairs were sent
      const sent = solveMock.mock.calls[0][0];
      expect(Array.isArray(sent.pickup_delivery_pairs)).toBe(true);
      expect(sent.pickup_delivery_pairs[0]).toEqual([1,2]); // indices in waypoint array
    });
  }
});
