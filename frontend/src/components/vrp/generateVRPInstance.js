export default function generateVRPInstance(waypoints, type = 'CVRP') {
  const depots = waypoints.filter(wp => wp.type === 'depot');
  const customers = waypoints.filter(wp => wp.type !== 'depot');

  const instance = {
    type,
    depots: depots.map(d => ({
      id: d.id,
      location: d.coordinates,
    })),
    customers: customers.map(c => ({
      id: c.id,
      location: c.coordinates,
      demand: c.demand,
      serviceTime: c.serviceTime,
      timeWindow: c.timeWindow ?? null,
      type: c.type,
      pairId: c.pairId ?? null,
    }))
  };

  return instance;
}
