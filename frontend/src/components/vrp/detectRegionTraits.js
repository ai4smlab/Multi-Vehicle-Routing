export default function detectRegionTraits(center){
  const [lng, lat] = center;

  let region = 'Unknown';
  let reason = 'Default weights applied';
  let weights = {
    cost: 20,
    time: 20,
    emissions: 20,
    distance: 20,
    reliability: 20,
  };

  if (lat > 35 && lat < 70 && lng > -10 && lng < 40) {
    // Europe
    region = 'Europe';
    reason = 'Dense cities and strong environmental policies';
    weights = {
      cost: 15,
      time: 25,
      emissions: 30,
      distance: 15,
      reliability: 15,
    };
  } else if (lat > 25 && lat < 55 && lng < -60) {
    // North America
    region = 'North America';
    reason = 'Long distances, suburban layouts';
    weights = {
      cost: 30,
      time: 20,
      emissions: 10,
      distance: 30,
      reliability: 10,
    };
  } else if (lat > -10 && lat < 55 && lng > 60 && lng < 150) {
    // Asia
    region = 'Asia';
    reason = 'Dense cities and traffic';
    weights = {
      cost: 20,
      time: 30,
      emissions: 10,
      distance: 20,
      reliability: 20,
    };
  } else if (lat < 15 && lng > -20 && lng < 50) {
    // Africa
    region = 'Africa';
    reason = 'Sparse infrastructure and variable roads';
    weights = {
      cost: 25,
      time: 10,
      emissions: 10,
      distance: 25,
      reliability: 30,
    };
  } else if (lat > -60 && lat < -10 && lng < -30) {
    // South America
    region = 'South America';
    reason = 'Challenging terrain and infrastructure';
    weights = {
      cost: 25,
      time: 15,
      emissions: 10,
      distance: 20,
      reliability: 30,
    };
  } else if (lat > -45 && lat < -10 && lng > 110) {
    // Australia
    region = 'Australia';
    reason = 'Large area, sparse depots';
    weights = {
      cost: 30,
      time: 10,
      emissions: 10,
      distance: 30,
      reliability: 20,
    };
  }

  return {
    region,
    reason,
    suggestedWeights: weights
  };
}
