import pandas as pd
import json
from typing import List, Dict, Any, Tuple

def pois_to_dataframe(pois: List[Dict]) -> pd.DataFrame:
    """Convert OSM POIs to DataFrame for mapping"""
    if not pois:
        return pd.DataFrame(columns=['lat', 'lon', 'name', 'type'])
    
    data = []
    for poi in pois:
        if 'lat' in poi and 'lon' in poi:
            data.append({
                'lat': float(poi['lat']),
                'lon': float(poi['lon']),
                'name': poi.get('tags', {}).get('name', 'Unknown'),
                'type': poi.get('tags', {}).get('amenity', poi.get('tags', {}).get('shop', 'poi'))
            })
    
    return pd.DataFrame(data)

def convert_pois_to_waypoints(pois: List[Dict]) -> List[Dict]:
    """Convert OSM POIs to VRP waypoints format"""
    waypoints = []
    
    for i, poi in enumerate(pois):
        if 'lat' in poi and 'lon' in poi:
            waypoint = {
                "id": f"poi_{i}",
                "location": {
                    "lat": float(poi['lat']),
                    "lon": float(poi['lon'])
                },
                "type": "customer",
                "demand": [1],
                "service_duration": 300,  # 5 minutes default
                "priority": 1
            }
            
            # Add name if available
            name = poi.get('tags', {}).get('name')
            if name:
                waypoint['id'] = f"{name.lower().replace(' ', '_')}_{i}"
            
            waypoints.append(waypoint)
    
    return waypoints

def validate_waypoints_json(waypoints_str: str) -> Tuple[bool, List[Dict], str]:
    """Validate and parse waypoints JSON"""
    try:
        waypoints = json.loads(waypoints_str)
        
        if not isinstance(waypoints, list):
            return False, [], "Waypoints must be a list"
        
        for i, wp in enumerate(waypoints):
            if not isinstance(wp, dict):
                return False, [], f"Waypoint {i} must be an object"
            
            if 'id' not in wp:
                return False, [], f"Waypoint {i} missing 'id' field"
            
            if 'location' not in wp or 'lat' not in wp['location'] or 'lon' not in wp['location']:
                return False, [], f"Waypoint {i} missing valid location"
        
        return True, waypoints, "Valid"
        
    except json.JSONDecodeError as e:
        return False, [], f"Invalid JSON: {e}"

def create_sample_waypoints() -> str:
    """Create sample waypoints JSON for testing"""
    sample = [
        {
            "id": "depot",
            "location": {"lat": 40.7128, "lon": -74.0060},
            "type": "depot",
            "demand": [0],
            "service_duration": 0
        },
        {
            "id": "customer_1",
            "location": {"lat": 40.7589, "lon": -73.9851},
            "type": "customer",
            "demand": [5],
            "service_duration": 300,
            "time_window": {"start": 32400, "end": 64800}
        },
        {
            "id": "customer_2", 
            "location": {"lat": 40.7282, "lon": -74.0776},
            "type": "customer",
            "demand": [3],
            "service_duration": 240,
            "time_window": {"start": 36000, "end": 68400}
        }
    ]
    
    return json.dumps(sample, indent=2)

def create_sample_fleet() -> List[Dict]:
    """Create sample fleet configuration"""
    return [
        {
            "id": "vehicle_1",
            "capacity": [20],
            "start": None,
            "end": None,
            "time_window": {"start": 28800, "end": 72000}
        },
        {
            "id": "vehicle_2", 
            "capacity": [15],
            "start": None,
            "end": None,
            "time_window": {"start": 28800, "end": 72000}
        }
    ]

def format_solution_results(result: Dict[str, Any]) -> pd.DataFrame:
    """Format solver results for display"""
    # Check for routes in nested data structure
    routes = result.get('routes') or result.get('data', {}).get('routes', [])
    
    if not routes:
        return pd.DataFrame()
    
    data = []
    for route in routes:
        data.append({
            'Vehicle': route.get('vehicle_id', 'Unknown'),
            'Waypoints': ' → '.join(route.get('waypoint_ids', [])),
            'Distance': f"{route.get('total_distance', 0):.2f}",
            'Duration': f"{route.get('total_duration', 0)} sec" if route.get('total_duration') else "N/A",
            'Emissions': f"{route.get('emissions', 0):.2f}" if route.get('emissions') else "N/A"
        })
    
    return pd.DataFrame(data)
