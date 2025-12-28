from strands.tools import tool
import json
import copy
import streamlit as st
from datetime import datetime
import sys
import os

# Add the parent directory to the path to import components
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'streamlit-app'))
from components.api_client import get_api_client

@tool
def update_waypoint_location(customer_id: str, lat: float, lon: float) -> str:
    """Updates a single waypoint's coordinates and re-optimizes routes.
    
    Args:
        customer_id: The customer ID to update (e.g., "customer_1", "depot")
        lat: New latitude coordinate
        lon: New longitude coordinate
    
    Returns: JSON with before/after metrics and new route solution
    """
    
    if 'vrp_data' not in st.session_state:
        return "ERROR: No VRP session found. Please run optimization first."
    
    # Get current state
    old_result = st.session_state.vrp_data["current_result"]
    old_location = get_customer_location(customer_id)
    
    if old_location is None:
        return f"ERROR: Customer '{customer_id}' not found."
    
    # Apply change
    update_customer_location(customer_id, lat, lon)
    new_result = reoptimize_routes()
    
    if new_result.get('status') != 'success':
        return f"ERROR: Re-optimization failed: {new_result.get('message', 'Unknown error')}"
    
    # Track modification
    changes = [{
        "customer_id": customer_id,
        "old_location": old_location,
        "new_location": [lat, lon]
    }]
    
    add_modification_record("single_update", changes, old_result, new_result)
    
    return format_update_response(old_result, new_result, changes)

@tool
def update_multiple_waypoints(updates: str) -> str:
    """Updates multiple waypoints at once and re-optimizes routes.
    
    Args:
        updates: JSON string with format:
        '[{"customer_id": "customer_1", "lat": 40.7128, "lon": -74.0060}, 
          {"customer_id": "customer_3", "lat": 40.7589, "lon": -73.9851}]'
    
    Returns: JSON with before/after metrics and new route solution
    """
    
    if 'vrp_data' not in st.session_state:
        return "ERROR: No VRP session found. Please run optimization first."
    
    try:
        updates_list = json.loads(updates)
    except json.JSONDecodeError:
        return "ERROR: Invalid JSON format for updates."
    
    old_result = st.session_state.vrp_data["current_result"]
    
    # Collect all changes
    changes = []
    for update in updates_list:
        customer_id = update.get("customer_id")
        lat = update.get("lat")
        lon = update.get("lon")
        
        if not all([customer_id, lat is not None, lon is not None]):
            return "ERROR: Each update must have customer_id, lat, and lon."
        
        old_location = get_customer_location(customer_id)
        if old_location is None:
            return f"ERROR: Customer '{customer_id}' not found."
        
        changes.append({
            "customer_id": customer_id,
            "old_location": old_location,
            "new_location": [lat, lon]
        })
        update_customer_location(customer_id, lat, lon)
    
    # Single re-optimization
    new_result = reoptimize_routes()
    
    if new_result.get('status') != 'success':
        return f"ERROR: Re-optimization failed: {new_result.get('message', 'Unknown error')}"
    
    # Track batch modification
    add_modification_record("batch_update", changes, old_result, new_result)
    
    return format_batch_update_response(old_result, new_result, changes)

@tool
def get_route_summary() -> str:
    """Gets current optimization results and route details.
    
    Returns: Current routes, metrics, and waypoint information
    """
    
    if 'vrp_data' not in st.session_state:
        return "ERROR: No VRP session found. Please run optimization first."
    
    current_result = st.session_state.vrp_data["current_result"]
    waypoints = st.session_state.vrp_data["waypoints"]
    
    summary = {
        "session_info": {
            "total_waypoints": len(waypoints),
            "total_vehicles": len(st.session_state.vrp_data["fleet"]),
            "solver": st.session_state.vrp_data["solver_config"]["solver"]
        },
        "current_metrics": extract_metrics(current_result),
        "routes": current_result.get("routes", []),
        "waypoints": waypoints
    }
    
    return json.dumps(summary, indent=2)

@tool
def compare_solutions() -> str:
    """Compares original vs current solution after modifications.
    
    Returns: Side-by-side comparison of metrics (distance, time, cost)
    """
    
    if 'vrp_data' not in st.session_state:
        return "ERROR: No VRP session found. Please run optimization first."
    
    original_result = st.session_state.vrp_data["original_result"]
    current_result = st.session_state.vrp_data["current_result"]
    
    comparison = {
        "original_metrics": extract_metrics(original_result),
        "current_metrics": extract_metrics(current_result),
        "improvement": calculate_improvement(original_result, current_result),
        "total_modifications": len(st.session_state.vrp_data["modification_history"])
    }
    
    return json.dumps(comparison, indent=2)

@tool
def get_modification_history() -> str:
    """Returns the complete modification history for this session"""
    
    if 'vrp_data' not in st.session_state:
        return "ERROR: No VRP session found. Please run optimization first."
    
    history = st.session_state.vrp_data.get("modification_history", [])
    
    if not history:
        return "No modifications made yet."
    
    summary = {
        "total_modifications": len(history),
        "total_customers_modified": len(set(
            change["customer_id"] 
            for record in history 
            for change in record["changes"]
        )),
        "cumulative_improvement": calculate_cumulative_improvement(history),
        "modification_details": history
    }
    
    return json.dumps(summary, indent=2)

@tool
def reset_to_original() -> str:
    """Resets all waypoints back to original positions"""
    
    if 'vrp_data' not in st.session_state:
        return "ERROR: No VRP session found. Please run optimization first."
    
    # Restore original waypoints
    st.session_state.vrp_data["waypoints"] = copy.deepcopy(
        st.session_state.vrp_data["original_waypoints"]
    )
    
    # Re-optimize with original data
    original_result = st.session_state.vrp_data["original_result"]
    st.session_state.vrp_data["current_result"] = original_result
    
    # Clear history
    st.session_state.vrp_data["modification_history"] = []
    
    return "Reset to original waypoint positions. All modifications cleared."

# Helper Functions
def get_location_as_dict(location):
    """Convert location to dict format for API"""
    if isinstance(location, dict):
        return location
    elif isinstance(location, list) and len(location) >= 2:
        return {"lat": location[0], "lon": location[1]}
    else:
        return location

def get_customer_location(customer_id: str):
    """Get current location of a customer"""
    waypoints = st.session_state.vrp_data["waypoints"]
    for wp in waypoints:
        if wp.get("id") == customer_id:
            location = wp["location"]
            # Handle both dict and list formats
            if isinstance(location, dict):
                return [location["lat"], location["lon"]]
            else:
                return location
    return None

def update_customer_location(customer_id: str, lat: float, lon: float):
    """Update customer location in session state"""
    waypoints = st.session_state.vrp_data["waypoints"]
    for wp in waypoints:
        if wp.get("id") == customer_id:
            # Update location in dict format
            if isinstance(wp["location"], dict):
                wp["location"]["lat"] = lat
                wp["location"]["lon"] = lon
            else:
                wp["location"] = [lat, lon]
            break

def reoptimize_routes():
    """Re-run optimization with current waypoints"""
    api_client = get_api_client()
    
    # Get current configuration
    waypoints = st.session_state.vrp_data["waypoints"]
    fleet = st.session_state.vrp_data["fleet"]
    config = st.session_state.vrp_data["solver_config"]
    
    # Calculate new distance matrix
    matrix_payload = {
        "adapter": config["adapter"],
        "origins": [get_location_as_dict(wp["location"]) for wp in waypoints],
        "destinations": [get_location_as_dict(wp["location"]) for wp in waypoints]
    }
    matrix_result = api_client.get_distance_matrix(matrix_payload)
    
    if matrix_result.get('status') != 'success':
        return {"status": "error", "message": "Failed to calculate distance matrix"}
    
    # Extract demands and time windows
    demands = [wp.get("demand", [0])[0] if wp.get("demand") else 0 for wp in waypoints]
    node_time_windows = []
    for wp in waypoints:
        tw = wp.get("time_window")
        if tw and "start" in tw and "end" in tw:
            node_time_windows.append([tw["start"], tw["end"]])
        else:
            node_time_windows.append(None)
    
    # Build solve payload
    payload = {
        "solver": config["solver"],
        "fleet": fleet,
        "matrix": matrix_result['data']['matrix'],
        "demands": demands,
        "node_time_windows": node_time_windows,
        "weights": config["weights"]
    }
    
    # Call solver
    result = api_client.solve_vrp(payload)
    
    if result.get('status') == 'success':
        st.session_state.vrp_data["current_result"] = result
    
    return result

def extract_metrics(result):
    """Extract key metrics from solver result"""
    return {
        "total_distance": result.get("total_distance", 0),
        "total_time": result.get("total_time", 0),
        "total_cost": result.get("total_cost", 0),
        "num_routes": len(result.get("routes", []))
    }

def calculate_improvement(old_result, new_result):
    """Calculate improvement metrics"""
    old_metrics = extract_metrics(old_result)
    new_metrics = extract_metrics(new_result)
    
    return {
        "distance_change": old_metrics["total_distance"] - new_metrics["total_distance"],
        "time_change": old_metrics["total_time"] - new_metrics["total_time"],
        "cost_change": old_metrics["total_cost"] - new_metrics["total_cost"]
    }

def calculate_cumulative_improvement(history):
    """Calculate total improvement from original to current state"""
    if not history:
        return {"distance_change": 0, "time_change": 0, "cost_change": 0}
    
    original = st.session_state.vrp_data["original_result"]
    current = st.session_state.vrp_data["current_result"]
    
    return calculate_improvement(original, current)

def add_modification_record(action_type, changes, old_result, new_result):
    """Add a modification record to history"""
    
    record = {
        "timestamp": datetime.now().isoformat(),
        "action": action_type,
        "changes": changes,
        "metrics_before": extract_metrics(old_result),
        "metrics_after": extract_metrics(new_result),
        "improvement": calculate_improvement(old_result, new_result)
    }
    
    st.session_state.vrp_data["modification_history"].append(record)

def format_update_response(old_result, new_result, changes):
    """Format response for single update"""
    improvement = calculate_improvement(old_result, new_result)
    
    response = {
        "status": "success",
        "message": f"Updated {changes[0]['customer_id']} location",
        "changes": changes,
        "improvement": improvement,
        "new_metrics": extract_metrics(new_result)
    }
    
    return json.dumps(response, indent=2)

def format_batch_update_response(old_result, new_result, changes):
    """Format response for batch update"""
    improvement = calculate_improvement(old_result, new_result)
    
    response = {
        "status": "success",
        "message": f"Updated {len(changes)} customer locations",
        "changes": changes,
        "improvement": improvement,
        "new_metrics": extract_metrics(new_result)
    }
    
    return json.dumps(response, indent=2)