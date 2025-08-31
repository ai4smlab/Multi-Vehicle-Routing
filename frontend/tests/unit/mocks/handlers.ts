import { http, HttpResponse } from 'msw';

export const handlers = [
  http.post('/distance-matrix', async () => {
    return HttpResponse.json({ data: { matrix: { distances: [[0,1000],[1000,0]] } } });
  }),
  http.post('/solver', async () => {
    return HttpResponse.json({
      data: { status: 'success', routes: [{ vehicle_id: 'veh-1', waypoint_ids: ['0','1','0'], total_distance: 2000 }] }
    });
  })
];