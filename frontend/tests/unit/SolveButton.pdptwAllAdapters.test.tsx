import React from 'react';
import { describe, it, beforeEach, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import SolveButton from '@/components/vrp/SolveButton.jsx';
import useWaypointStore from '@/hooks/useWaypointStore';
import useFleetStore from '@/hooks/useFleetStore';
import useRouteStore from '@/hooks/useRouteStore';

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
      { id:'0', coordinates:[0,0], type:'Depot', timeWindow:[0,86400] },
      { id:'1', coordinates:[1,1], type:'Pickup',   pairId:'A', demand: 1, timeWindow:[0,3600], serviceTime: 10 },
      { id:'2', coordinates:[2,2], type:'Delivery', pairId:'A', demand: 1, timeWindow:[1800,7200], serviceTime: 10 },
    ]
  }, false);
  useFleetStore.setState({ vehicles: [{ id:'veh-1', capacity: 10 }] }, false);
  useRouteStore.setState({ routes: [], summary: null, currentIndex: 0 }, false);
  dmMock.mockReset();
  solveMock.mockReset();
};

describe('SolveButton (ortools/PDPTW)', () => {
  beforeEach(resetAll);

  for (const adapter of adapters) {
    it(`PDPTW with ${adapter}`, async () => {
      // Matrix mock: give distances always; give durations for non-haversine; leave missing for haversine to hit fallback
      const distances = [[0,1000,2000],[1000,0,1500],[2000,1500,0]];
      const durations = [[0,120,240],[120,0,180],[240,180,0]];
      const matrix: any = { distances };
      if (adapter !== 'haversine') matrix.durations = durations;

      dmMock.mockResolvedValue({ data: { matrix } });

      solveMock.mockResolvedValue({
        data: { status:'success', routes: [{ vehicle_id:'veh-1', waypoint_ids:['0','1','2','0'] }] }
      });

      render(<SolveButton solver="ortools" adapter={adapter} vrpType="PDPTW" />);
      fireEvent.click(screen.getByRole('button', { name: /solve/i }));

      await waitFor(() => expect(dmMock).toHaveBeenCalledTimes(1));
      await waitFor(() => expect(solveMock).toHaveBeenCalledTimes(1));

      const sent = solveMock.mock.calls[0][0];
      expect(Array.isArray(sent.matrix?.durations)).toBe(true); // derived for haversine
      expect(Array.isArray(sent.node_time_windows)).toBe(true);
      expect(Array.isArray(sent.node_service_times)).toBe(true);
      expect(Array.isArray(sent.pickup_delivery_pairs)).toBe(true);
      expect(Array.isArray(sent.demands)).toBe(true);

      await waitFor(() => {
        const st = useRouteStore.getState();
        expect(st.routes.length).toBe(1);
      });
    });
  }
});
