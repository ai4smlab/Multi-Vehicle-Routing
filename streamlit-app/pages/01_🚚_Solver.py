import streamlit as st
import json
import copy
import os
from components.api_client import get_api_client
from utils.data_processing import (
    validate_waypoints_json, 
    create_sample_waypoints, 
    create_sample_fleet,
    format_solution_results
)
from utils.visualization import create_route_map, display_metrics

st.set_page_config(page_title="VRP Solver", page_icon="🚚", layout="wide")

st.title("🚚 Vehicle Route Optimization")
st.markdown("Solve Vehicle Routing Problems with multiple optimization engines")

# Initialize API client
api_client = get_api_client()

# Check if backend is available
if not api_client.check_health():
    st.error("❌ Backend API not available. Please start the FastAPI server.")
    st.stop()

# Get available capabilities
capabilities = api_client.get_capabilities()
available_solvers = capabilities.get('solvers', ['ortools'])
available_adapters = capabilities.get('adapters', ['haversine'])

# Sidebar configuration
st.sidebar.header("Configuration")

# Solver selection
solver = st.sidebar.selectbox(
    "Select Solver",
    available_solvers,
    help="Choose the optimization engine"
)

# Distance adapter selection
adapter = st.sidebar.selectbox(
    "Distance Adapter", 
    available_adapters,
    help="Method for calculating distances between waypoints"
)

# Advanced options
with st.sidebar.expander("Advanced Options"):
    time_limit = st.number_input("Time Limit (seconds)", min_value=10, max_value=600, value=60)
    allow_drop = st.checkbox("Allow dropping customers", value=False)
    
    # Objective weights
    st.subheader("Objective Weights")
    weight_distance = st.slider("Distance Weight", 0.0, 2.0, 1.0, 0.1)
    weight_time = st.slider("Time Weight", 0.0, 2.0, 0.0, 0.1)

# Main content area
col1, col2 = st.columns([1, 1])

with col1:
    st.header("Input Configuration")
    
    # Waypoints input
    st.subheader("Waypoints")
    
    input_method = st.radio(
        "Input Method",
        ["Sample Data", "JSON Input", "Upload File"],
        horizontal=True
    )
    
    waypoints_data = None
    
    if input_method == "Sample Data":
        st.info("Using sample waypoints for demonstration")
        waypoints_str = create_sample_waypoints()
        st.code(waypoints_str, language="json")
        waypoints_data = json.loads(waypoints_str)
        
    elif input_method == "JSON Input":
        waypoints_str = st.text_area(
            "Waypoints JSON",
            value=create_sample_waypoints(),
            height=300,
            help="Enter waypoints in JSON format"
        )
        
        if waypoints_str:
            is_valid, waypoints_data, error_msg = validate_waypoints_json(waypoints_str)
            if is_valid:
                st.success(f"✅ Valid waypoints ({len(waypoints_data)} locations)")
            else:
                st.error(f"❌ {error_msg}")
                waypoints_data = None
    
    elif input_method == "Upload File":
        uploaded_file = st.file_uploader("Upload waypoints file", type=['json'])
        if uploaded_file:
            try:
                waypoints_str = uploaded_file.read().decode()
                is_valid, waypoints_data, error_msg = validate_waypoints_json(waypoints_str)
                if is_valid:
                    st.success(f"✅ Loaded {len(waypoints_data)} waypoints")
                else:
                    st.error(f"❌ {error_msg}")
            except Exception as e:
                st.error(f"Error reading file: {e}")
    
    # Fleet configuration
    st.subheader("Fleet Configuration")
    
    fleet_method = st.radio(
        "Fleet Setup",
        ["Default Fleet", "Custom Fleet"],
        horizontal=True
    )
    
    if fleet_method == "Default Fleet":
        num_vehicles = st.number_input("Number of Vehicles", min_value=1, max_value=10, value=2)
        vehicle_capacity = st.number_input("Vehicle Capacity", min_value=1, max_value=1000, value=20)
        
        fleet_data = []
        for i in range(num_vehicles):
            fleet_data.append({
                "id": f"vehicle_{i+1}",
                "capacity": [vehicle_capacity],
                "start": None,
                "end": None
            })
    else:
        fleet_str = st.text_area(
            "Fleet JSON",
            value=json.dumps(create_sample_fleet(), indent=2),
            height=200
        )
        try:
            fleet_data = json.loads(fleet_str)
            st.success(f"✅ Fleet configured ({len(fleet_data)} vehicles)")
        except:
            st.error("❌ Invalid fleet JSON")
            fleet_data = create_sample_fleet()

with col2:
    st.header("Optimization Results")
    
    # Solve button
    if st.button("🚀 Optimize Routes", type="primary", use_container_width=True):
        if not waypoints_data:
            st.error("Please provide valid waypoints")
        elif not fleet_data:
            st.error("Please configure fleet")
        else:
            with st.spinner(f"Solving with {solver}..."):
                # Prepare payload
                # Step 1: Calculate distance matrix
                matrix_payload = {
                    "adapter": adapter,
                    "origins": [wp["location"] for wp in waypoints_data],
                    "destinations": [wp["location"] for wp in waypoints_data]
                }
                matrix_result = api_client.get_distance_matrix(matrix_payload)

                # Check if matrix calculation succeeded
                if (not matrix_result or 
                    matrix_result.get('status') != 'success' or 
                    'data' not in matrix_result or 
                    'matrix' not in matrix_result['data'] or 
                    'distances' not in matrix_result['data']['matrix']):
                    st.error(f"❌ Failed to calculate distance matrix. Result: {matrix_result}")
                    st.stop()

                # Extract the actual matrix data
                matrix_data = matrix_result['data']['matrix']
                st.success(f"✅ Distance matrix calculated ({len(matrix_data['distances'])}x{len(matrix_data['distances'])} matrix)")

                # Step 2: Extract demands and time windows from waypoints
                demands = [wp.get("demand", [0])[0] if wp.get("demand") else 0 for wp in waypoints_data]
                node_time_windows = []
                for wp in waypoints_data:
                    tw = wp.get("time_window")
                    if tw and "start" in tw and "end" in tw:
                        node_time_windows.append([tw["start"], tw["end"]])
                    else:
                        node_time_windows.append(None)

                # Step 3: Build solve payload
                payload = {
                    "solver": solver,
                    "fleet": fleet_data,
                    "matrix": matrix_data,  # Use the extracted matrix data
                    "demands": demands,
                    "node_time_windows": node_time_windows,
                    "weights": {
                        "distance": weight_distance,
                        "time": weight_time
                    }
                }


                # Call solver
                result = api_client.solve_vrp(payload)
                
                if result.get('status') == 'success':
                    st.success("✅ Routes optimized successfully!")
                    
                    # Store enhanced session data for AI agent
                    st.session_state.vrp_data = {
                        "waypoints": waypoints_data,
                        "original_waypoints": copy.deepcopy(waypoints_data),
                        "fleet": fleet_data,
                        "solver_config": {
                            "solver": solver,
                            "adapter": adapter,
                            "weights": {"distance": weight_distance, "time": weight_time},
                            "time_limit": time_limit,
                            "allow_drop": allow_drop
                        },
                        "original_result": result,
                        "current_result": result,
                        "modification_history": [],
                        "session_id": os.urandom(16).hex()
                    }
                    
                    # Store legacy session state for compatibility
                    st.session_state.solver_result = result
                    st.session_state.waypoints_data = waypoints_data
                    
                        
                else:
                    st.error(f"❌ Optimization failed: {result.get('message', 'Unknown error')}")


    if 'solver_result' in st.session_state:
                        result = st.session_state.solver_result
                        waypoints_data = st.session_state.waypoints_data
                        # Display metrics
                        display_metrics(result)
                        
                        # Display routes table
                        st.subheader("Route Details")
                        routes_df = format_solution_results(result)
                        if not routes_df.empty:
                            st.dataframe(routes_df, use_container_width=True)
                        
                        # Add AI Agent launch section
                        st.subheader("Next Steps")
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.button("🤖 Launch AI Agent", type="secondary", use_container_width=True):
                                st.switch_page("pages/02_🤖_AI_Agent.py")
                        with col2:
                            if st.button("🔄 Run Another Optimization", use_container_width=True):
                                st.rerun()

# Display map if we have results
if 'solver_result' in st.session_state and 'waypoints_data' in st.session_state:
    st.header("Route Visualization")
    
    try:
        # Create map
        route_map = create_route_map(
            st.session_state.waypoints_data,
            st.session_state.solver_result.get('routes', [])
        )
        
        # Display map
        st.components.v1.html(route_map._repr_html_(), height=500)
        
    except Exception as e:
        st.error(f"Error creating map: {e}")
        
        # Fallback: show waypoints on simple map
        if st.session_state.waypoints_data:
            import pandas as pd
            
            map_data = []
            for wp in st.session_state.waypoints_data:
                map_data.append({
                    'lat': wp['location']['lat'],
                    'lon': wp['location']['lon']
                })
            
            if map_data:
                st.map(pd.DataFrame(map_data))

# Help section
with st.expander("ℹ️ Help & Tips"):
    st.markdown("""
    **Waypoint Format:**
    ```json
    {
        "id": "unique_identifier",
        "location": {"lat": 40.7128, "lon": -74.0060},
        "type": "customer",  // or "depot"
        "demand": [5],       // array of demands
        "service_duration": 300,  // seconds
        "time_window": {"start": 32400, "end": 64800}  // optional
    }
    ```
    
    **Solver Comparison:**
    - **OR-Tools**: Best for complex constraints, slower on large instances
    - **VROOM**: Fast heuristic, good for large problems
    - **Pyomo**: Mathematical optimization, good for research
    
    **Distance Adapters:**
    - **haversine**: Great circle distance (fast, offline)
    - **euclidean**: Planar distance (for benchmarks)
    - **openrouteservice**: Real road routing (requires API key)
    """)