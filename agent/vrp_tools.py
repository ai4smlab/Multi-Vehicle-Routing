from langchain.tools import tool
import json
import copy
import streamlit as st
from datetime import datetime
import sys
import os
from typing import Union, Optional

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
def modify_waypoint_constraints(customer_ids: str = "all", remove_time_window: bool = False) -> str:
    """Modifies waypoint constraints (like time windows) and re-optimizes.
    
    Args:
        customer_ids: Comma-separated customer IDs, or "all" for all customers
        remove_time_window: If True, removes time window constraints
    
    Returns: JSON with optimization result after constraint removal
    """
    
    if 'vrp_data' not in st.session_state:
        return "ERROR: No VRP session found. Please run optimization first."
    
    old_result = st.session_state.vrp_data["current_result"]
    waypoints = st.session_state.vrp_data["waypoints"]
    
    # Determine which customers to modify
    if customer_ids.lower() == "all":
        target_customers = [wp["id"] for wp in waypoints]
    else:
        target_customers = [cid.strip() for cid in customer_ids.split(",")]
    
    # Apply modifications
    changes = []
    for wp in waypoints:
        if wp["id"] in target_customers:
            if remove_time_window:
                old_tw = wp.get("time_window")
                wp["time_window"] = None
                changes.append({
                    "customer_id": wp["id"],
                    "removed_constraint": "time_window",
                    "old_value": old_tw
                })
    
    if not changes:
        return "ERROR: No matching customers found or no changes applied."
    
    # Re-optimize without constraints
    new_result = reoptimize_routes()
    
    if new_result.get('status') != 'success':
        return f"ERROR: Re-optimization failed: {new_result.get('message', 'Unknown error')}"
    
    # Track modification
    add_modification_record("constraint_removal", changes, old_result, new_result)
    
    improvement = calculate_improvement(old_result, new_result)
    
    response = {
        "status": "success",
        "message": f"Removed time window constraints for {len(changes)} customer(s) and re-optimized",
        "changes": changes,
        "improvement": improvement,
        "new_metrics": extract_metrics(new_result)
    }
    
    return json.dumps(response, indent=2)


# @tool
# def get_route_summary() -> str:
#     """Gets current optimization results and route details.
    
#     Returns: Current routes, metrics, and waypoint information
#     """
    
#     if 'vrp_data' not in st.session_state:
#         return "ERROR: No VRP session found. Please run optimization first."
    
#     current_result = st.session_state.vrp_data["current_result"]
#     waypoints = st.session_state.vrp_data["waypoints"]
    
#     summary = {
#         "session_info": {
#             "total_waypoints": len(waypoints),
#             "total_vehicles": len(st.session_state.vrp_data["fleet"]),
#             "solver": st.session_state.vrp_data["solver_config"]["solver"]
#         },
#         "current_metrics": extract_metrics(current_result),
#         "routes": current_result.get("routes", []),
#         "waypoints": waypoints
#     }
    
#     return json.dumps(summary, indent=2)


# @tool
# def get_route_summary(invocation_state: dict = None) -> str:
#     """Gets current optimization results and route details.
    
#     Args:
#         invocation_state: State passed from agent invocation
    
#     Returns: Current routes, metrics, and waypoint information
#     """
    
#     # Get VRP data from invocation_state instead of st.session_state
#     if not invocation_state or 'vrp_data' not in invocation_state:
#         return "ERROR: No VRP session found. Please run optimization first."
    
#     vrp_data = invocation_state['vrp_data']
#     current_result = vrp_data["current_result"]
#     waypoints = vrp_data["waypoints"]
    
#     summary = {
#         "session_info": {
#             "total_waypoints": len(waypoints),
#             "total_vehicles": len(vrp_data["fleet"]),
#             "solver": vrp_data["solver_config"]["solver"]
#         },
#         "current_metrics": extract_metrics(current_result),
#         "routes": current_result.get("routes", []) if "data" not in current_result else current_result["data"].get("routes", []),
#         "waypoints": waypoints
#     }
    
#     return json.dumps(summary, indent=2)


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
        "routes": current_result.get("routes", []) if "data" not in current_result else current_result["data"].get("routes", []),
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
    
    original_result = st.session_state.vrp_data.get("original_result", {})
    current_result = st.session_state.vrp_data.get("current_result", {})
    
    # ===== DEBUG: Print raw results to console =====
    print("\n🔍 DEBUG: compare_solutions()")
    print(f"Original result keys: {original_result.keys() if original_result else 'None'}")
    print(f"Current result keys: {current_result.keys() if current_result else 'None'}")
    print(f"Original result status: {original_result.get('status')}")
    print(f"Current result status: {current_result.get('status')}")
    
    if "routes" in original_result:
        print(f"Original routes: {len(original_result.get('routes', []))}")
        if original_result.get('routes'):
            print(f"  First route: {original_result['routes'][0].keys()}")
    
    if "routes" in current_result:
        print(f"Current routes: {len(current_result.get('routes', []))}")
        if current_result.get('routes'):
            print(f"  First route: {current_result['routes'][0].keys()}")
    # ===== END DEBUG =====
    
    original_metrics = extract_metrics(original_result)
    current_metrics = extract_metrics(current_result)
    improvement = calculate_improvement(original_result, current_result)
    
    # ===== DEBUG: Print extracted metrics =====
    print(f"\nExtracted original metrics: {original_metrics}")
    print(f"Extracted current metrics: {current_metrics}")
    print(f"Calculated improvement: {improvement}")
    # ===== END DEBUG =====
    
    comparison = {
        "original_metrics": original_metrics,
        "current_metrics": current_metrics,
        "improvement": improvement,
        "total_modifications": len(st.session_state.vrp_data.get("modification_history", []))
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

# def get_customer_location(customer_id: str):
#     """Get current location of a customer"""
#     waypoints = st.session_state.vrp_data["waypoints"]
#     for wp in waypoints:
#         if wp.get("id") == customer_id:
#             location = wp["location"]
#             # Handle both dict and list formats
#             if isinstance(location, dict):
#                 return [location["lat"], location["lon"]]
#             else:
#                 return location
#     return None


def get_customer_location(customer_id: str):
    """Get current location of a customer"""
    waypoints = st.session_state.vrp_data["waypoints"]
    for wp in waypoints:
        if wp.get("id") == customer_id:
            location = wp["location"]
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


@tool
def create_single_route_scenario(customers_data: Union[str, list, None] = None) -> str:
    """Creates a single-route scenario optimized for all customers.

    If customers_data is NOT provided (None), uses EXISTING waypoints from the current session.
    If customers_data IS provided, uses the new waypoints instead.

    Args:
        customers_data: (Optional) List or JSON string with NEW customer waypoints.
        Accepts a list: [{"id": "customer_1", "lat": 40.7128, "lon": -74.006}, ...]
        Or a JSON string: '[{"id": "customer_1", "lat": 40.7128, "lon": -74.006}, ...]'
        Each customer may also use nested location: {"id": "...", "location": {"lat": ..., "lon": ...}}
        If None or empty, uses existing customers from session.

    Returns: JSON with new single-route optimization result

    Configuration applied:
    - 1 vehicle with infinite capacity
    - Service duration: 300 seconds per customer
    - No time windows (removed for optimization)
    - Depot remains from previous session

    USE THIS TOOL when user asks for:
    - "Create a single route"
    - "Optimize for one vehicle"
    - "Consolidate into one route"
    - "Show me a single route solution"
    """

    if 'vrp_data' not in st.session_state:
        return "ERROR: No VRP session found. Need existing session with depot."

    # Get existing waypoints from session
    existing_waypoints = st.session_state.vrp_data.get("waypoints", [])

    if not existing_waypoints:
        return "ERROR: No waypoints found in session."

    # Get depot
    depot = next((wp for wp in existing_waypoints if wp.get("type") == "depot"), None)

    if depot is None:
        return "ERROR: No depot found in existing session"

    # Normalize customers_data — accept list, JSON string, or None
    if isinstance(customers_data, list):
        raw_list = customers_data
    elif isinstance(customers_data, str) and customers_data.strip():
        try:
            raw_list = json.loads(customers_data)
        except json.JSONDecodeError as e:
            return f"ERROR: Invalid JSON format. {str(e)}"
    else:
        raw_list = None

    # Determine which customers to use
    if raw_list is None:
        # Use EXISTING customers from session
        existing_customers = [wp for wp in existing_waypoints if wp.get("type") == "customer"]

        if not existing_customers:
            return "ERROR: No customers found in session."

        customers_list = existing_customers
        source = "existing_session"
    else:
        if not isinstance(raw_list, list) or len(raw_list) == 0:
            return "ERROR: customers_data must be a non-empty list or JSON array"
        customers_list = raw_list
        source = "provided_data"
    
    # Get existing depot from session
    existing_waypoints = st.session_state.vrp_data.get("waypoints", [])
    depot = next((wp for wp in existing_waypoints if wp.get("type") == "depot"), None)
    
    if depot is None:
        return "ERROR: No depot found in existing session"
    
    # Build new waypoints: depot + customers (with modified constraints)
    new_waypoints = [depot]  # Keep existing depot

    for customer in customers_list:
        if source == "existing_session":
            # Copy existing customer but remove time windows
            customer_wp = {
                "id": customer.get("id"),
                "type": "customer",
                "location": customer.get("location"),
                "demand": customer.get("demand", [1]),
                "service_duration": 300,  # 5 minutes per customer
                "time_window": None  # Remove time windows
            }
        else:
            # Validate and use new customer data
            if not isinstance(customer, dict):
                return f"ERROR: Each customer must be a dict. Got {type(customer)}"

            # Support both flat {"lat": ..., "lon": ...} and nested {"location": {"lat": ..., "lon": ...}}
            lat = customer.get("lat") or customer.get("location", {}).get("lat")
            lon = customer.get("lon") or customer.get("location", {}).get("lon")

            if "id" not in customer or lat is None or lon is None:
                return "ERROR: Each customer must have 'id' and coordinates ('lat'/'lon' or 'location.lat'/'location.lon')"

            customer_wp = {
                "id": str(customer.get("id")),
                "type": "customer",
                "location": {
                    "lat": float(lat),
                    "lon": float(lon)
                },
                "demand": customer.get("demand", [1]),
                "service_duration": 300,  # 5 minutes per customer
                "time_window": None  # No time windows
            }
        new_waypoints.append(customer_wp)

    # Count customers
    customer_count = len(customers_list)

    # Create single vehicle with infinite capacity
    single_vehicle = {
        "id": "vehicle_1",
        "capacity": [10**9],  # Infinite capacity
        "start_location": depot.get("location"),
        "start": 0,  # Start at depot index
        "end": 0,  # End at depot index
        "time_window": None  # No time window
    }

    # Store original state for comparison
    original_waypoints = st.session_state.vrp_data.get("waypoints", [])
    original_fleet = st.session_state.vrp_data.get("fleet", [])
    original_result = st.session_state.vrp_data.get("current_result", {})

    # Update session state
    st.session_state.vrp_data["waypoints"] = new_waypoints
    st.session_state.vrp_data["fleet"] = [single_vehicle]

    # Update solver config for single route
    st.session_state.vrp_data["solver_config"]["allow_drop"] = False
    st.session_state.vrp_data["solver_config"]["vehicle_fixed_cost"] = 0  # No penalty for vehicle

    # Re-optimize with new configuration
    new_result = reoptimize_routes()

    if new_result.get('status') != 'success':
        # Restore original if optimization failed
        st.session_state.vrp_data["waypoints"] = original_waypoints
        st.session_state.vrp_data["fleet"] = original_fleet
        return f"ERROR: Optimization failed: {new_result.get('message', 'Unknown error')}"

    # Track this as a modification
    modification = {
        "action": "create_single_route_scenario",
        "description": f"Re-configured session for single-route optimization with {customer_count} customers",
        "source": source,
        "previous_vehicles": len(original_fleet),
        "new_vehicles": 1,
        "customers_count": customer_count,
        "time_windows_removed": customer_count,
        "vehicle_capacity": 10**9,
        "service_duration_per_customer": 300
    }

    if "modification_history" not in st.session_state.vrp_data:
        st.session_state.vrp_data["modification_history"] = []

    st.session_state.vrp_data["modification_history"].append(modification)

    # Extract metrics
    routes = new_result.get("routes", []) if "data" not in new_result else new_result.get("data", {}).get("routes", [])
    total_distance = sum(r.get("total_distance", 0) for r in routes)
    total_duration = sum(r.get("total_duration", 0) for r in routes)

    response = {
        "status": "success",
        "message": f"Created single-route scenario using {customer_count} {'existing' if source == 'existing_session' else 'new'} customers",
        "configuration": {
            "vehicles": 1,
            "vehicle_capacity": "∞ (infinite)",
            "customers": customer_count,
            "customer_ids": [c.get("id") if isinstance(c, dict) else c["id"] for c in customers_list],
            "service_duration": "300 seconds per customer",
            "time_windows": "Removed for optimization",
            "depot": depot.get("id")
        },
        "result": {
            "total_distance": round(total_distance, 2),
            "total_duration_seconds": int(total_duration),
            "total_duration_hours": round(total_duration / 3600, 2),
            "route_sequence": routes[0].get("waypoint_ids", []) if routes else [],
            "stops": len(routes[0].get("waypoint_ids", [])) - 1 if routes else 0
        },
        "comparison_with_original": {
            "original_distance": extract_metrics(original_result).get("total_distance", 0),
            "new_distance": round(total_distance, 2),
            "distance_change": round(extract_metrics(original_result).get("total_distance", 0) - total_distance, 2)
        }
    }

    return json.dumps(response, indent=2)




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
    """Extract key metrics from solver result - handles multiple result formats"""
    
    if not result or result.get('status') != 'success':
        return {
            "total_distance": 0,
            "total_time": 0,
            "total_cost": 0,
            "num_routes": 0
        }
    
    # Handle nested "data" structure
    if "data" in result:
        data = result["data"]
        routes = data.get("routes", [])
    else:
        routes = result.get("routes", [])
    
    # If no routes, return zeros
    if not routes:
        return {
            "total_distance": 0,
            "total_time": 0,
            "total_cost": 0,
            "num_routes": 0
        }
    
    # Calculate metrics from routes
    total_distance = sum(route.get("total_distance", 0) for route in routes)
    total_time = sum(route.get("total_duration", 0) for route in routes)
    total_cost = result.get("total_cost", 0)
    
    # If total_distance is 0, check if we need to look for alternative fields
    if total_distance == 0:
        # Try alternative field names
        total_distance = result.get("distance", 0) or result.get("total_distance", 0)
    
    if total_time == 0:
        # Try alternative field names
        total_time = result.get("duration", 0) or result.get("total_duration", 0)
    
    return {
        "total_distance": round(total_distance, 2),
        "total_time": round(total_time, 2),
        "total_cost": round(total_cost, 2),
        "num_routes": len(routes)
    }


def calculate_improvement(old_result, new_result):
    """Calculate improvement metrics between two results"""
    
    old_metrics = extract_metrics(old_result)
    new_metrics = extract_metrics(new_result)
    
    distance_change = old_metrics["total_distance"] - new_metrics["total_distance"]
    time_change = old_metrics["total_time"] - new_metrics["total_time"]
    cost_change = old_metrics["total_cost"] - new_metrics["total_cost"]
    
    # Calculate percentage improvements
    distance_pct = round((distance_change / old_metrics["total_distance"] * 100), 2) if old_metrics["total_distance"] > 0 else 0
    time_pct = round((time_change / old_metrics["total_time"] * 100), 2) if old_metrics["total_time"] > 0 else 0
    
    return {
        "distance_change": round(distance_change, 2),
        "distance_change_pct": distance_pct,
        "time_change": round(time_change, 2),
        "time_change_pct": time_pct,
        "cost_change": round(cost_change, 2),
        "routes_change": new_metrics["num_routes"] - old_metrics["num_routes"]
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