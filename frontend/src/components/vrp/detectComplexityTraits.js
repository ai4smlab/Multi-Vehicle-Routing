export default function detectComplexityTraits(waypoints, vehicleCount = 1) {
  const traits = [];
  const reasons = [];
  let weights = {
    cost: 20,
    time: 20,
    emissions: 20,
    distance: 20,
    reliability: 20,
  };

  if (waypoints.length > 50) {
    traits.push('High Waypoint Count');
    weights.reliability += 10;
    weights.time += 5;
    weights.cost -= 5;
    reasons.push('Increased waypoint count makes routes harder to manage.');
  }

  const hasTimeWindows = waypoints.some(wp => Array.isArray(wp.timeWindow));
  if (hasTimeWindows) {
    traits.push('Time Windows');
    weights.time += 10;
    weights.cost -= 5;
    reasons.push('Time window constraints increase time pressure.');
  }

  const demands = waypoints.map(wp => wp.demand ?? 1);
  const demandSpread = Math.max(...demands) - Math.min(...demands);
  if (demandSpread > 10) {
    traits.push('High Demand Variance');
    weights.reliability += 10;
    weights.emissions += 5;
    weights.cost -= 5;
    reasons.push('Wide variation in demand requires more reliable planning.');
  }

  // Simple clustering estimate (average nearest-neighbor distance)
  const avgDist = estimateAverageDistance(waypoints.map(wp => wp.coordinates));
  if (avgDist < 0.01) {
    traits.push('Highly Clustered');
    weights.time += 10;
    weights.distance -= 10;
    reasons.push('Dense locations increase local traffic complexity.');
  } else if (avgDist > 1.0) {
    traits.push('Spread Out');
    weights.distance += 10;
    weights.cost += 5;
    reasons.push('Spread out locations increase distance and fuel usage.');
  }

  // Normalize weights
  const total = Object.values(weights).reduce((a, b) => a + b, 0);
  for (const key in weights) {
    weights[key] = +(weights[key] / total).toFixed(2);
  }

  return {
    traits,
    suggestedWeights: weights,
    reasons,
  };
}

// Rough average distance calculator (uses haversine)
function estimateAverageDistance(coords) {
  if (coords.length < 2) return 0;

  let totalDist = 0;
  for (let i = 0; i < coords.length - 1; i++) {
    totalDist += haversineDistance(coords[i], coords[i + 1]);
  }

  return totalDist / (coords.length - 1);
}

function haversineDistance([lon1, lat1], [lon2, lat2]) {
  const R = 6371; // Earth radius km
  const toRad = deg => (deg * Math.PI) / 180;
  const dLat = toRad(lat2 - lat1);
  const dLon = toRad(lon2 - lon1);
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) ** 2;
  return R * 2 * Math.asin(Math.sqrt(a));
}