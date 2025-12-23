import streamlit as st
import pandas as pd
import numpy as np
import json
from components.api_client import get_api_client
from utils.data_processing import validate_waypoints_json, create_sample_waypoints

st.set_page_config(page_title="Distance Matrix", page_icon="📏", layout="wide")

st.title("📏 Distance Matrix Calculator")
st.markdown("Calculate travel distances and times between waypoints using different adapters")

# Initialize API client
api_client = get_api_client()

# Check if backend is available
if not api_client.check_health():
    st.error("❌ Backend API not available. Please start the FastAPI server.")
    st.stop()

# Get available capabilities
capabilities = api_client.get_capabilities()
available_adapters = capabilities.get('adapters', ['haversine'])

# Sidebar configuration
st.sidebar.header("Configuration")

# Adapter selection
adapter = st.sidebar.selectbox(
    "Distance Adapter",
    available_adapters,
    help="Method for calculating distances"
)

# Mode selection (for online adapters)
if adapter in ['openrouteservice', 'google', 'mapbox']:
    mode = st.sidebar.selectbox(
        "Travel Mode",
        ["driving", "walking", "cycling"],
        help="Transportation mode for routing"
    )
else:
    mode = "driving"  # Default for offline adapters

# Display adapter info
st.sidebar.markdown("### Adapter Information")
adapter_info = {
    'haversine': "Great circle distance (offline)",
    'euclidean': "Planar XY distance (for benchmarks)",
    'openrouteservice': "Real road routing (requires API key)",
    'google': "Google Maps routing (requires API key)",
    'mapbox': "Mapbox routing (requires API key)",
    'osm_graph': "Local OSM routing (downloads map data)"
}

st.sidebar.info(adapter_info.get(adapter, "Distance calculation adapter"))

# Main content
col1, col2 = st.columns([1, 1])

with col1:
    st.header("Input Waypoints")
    
    # Input method selection
    input_method = st.radio(
        "Input Method",
        ["Sample Data", "JSON Input", "From OSM Data", "Upload File"],
        horizontal=True
    )
    
    waypoints_data = None
    
    if input_method == "Sample Data":
        st.info("Using sample waypoints")
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
    
    elif input_method == "From OSM Data":
        if 'converted_waypoints' in st.session_state:
            waypoints_data = st.session_state.converted_waypoints
            st.success(f"✅ Using {len(waypoints_data)} waypoints from OSM data")
            
            # Show preview
            with st.expander("Preview Waypoints"):
                for i, wp in enumerate(waypoints_data[:3]):
                    st.write(f"**{wp['id']}**: ({wp['location']['lat']:.6f}, {wp['location']['lon']:.6f})")
                if len(waypoints_data) > 3:
                    st.write(f"... and {len(waypoints_data) - 3} more")
        else:
            st.warning("No OSM waypoints available. Please import data from the OSM Data page first.")
    
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
    
    # Calculate button
    calculate_button = st.button(
        "🧮 Calculate Distance Matrix",
        type="primary",
        use_container_width=True,
        disabled=not waypoints_data
    )

with col2:
    st.header("Matrix Results")
    
    if calculate_button and waypoints_data:
        with st.spinner(f"Calculating distances using {adapter}..."):
            # Extract coordinates
            origins = []
            destinations = []
            
            for wp in waypoints_data:
                coord = {
                    "lat": wp['location']['lat'],
                    "lon": wp['location']['lon']
                }
                origins.append(coord)
                destinations.append(coord)
            
            # Prepare payload
            payload = {
                "adapter": adapter,
                "mode": mode,
                "origins": origins,
                "destinations": destinations
            }
            
            # Call API
            result = api_client.get_distance_matrix(payload)
            
            if result and 'distances' in result:
                st.success("✅ Distance matrix calculated successfully!")
                
                # Store result
                st.session_state.distance_matrix = result
                st.session_state.matrix_waypoints = waypoints_data
                
                # Display summary
                distances = result['distances']
                n = len(distances)
                
                st.subheader("Summary")
                st.write(f"**Matrix Size:** {n} × {n}")
                st.write(f"**Adapter:** {adapter}")
                st.write(f"**Mode:** {mode}")
                
                # Calculate statistics
                flat_distances = []
                for i in range(n):
                    for j in range(n):
                        if i != j and distances[i][j] is not None:
                            flat_distances.append(distances[i][j])
                
                if flat_distances:
                    st.write(f"**Min Distance:** {min(flat_distances):.2f}")
                    st.write(f"**Max Distance:** {max(flat_distances):.2f}")
                    st.write(f"**Avg Distance:** {np.mean(flat_distances):.2f}")
            
            else:
                st.error("❌ Failed to calculate distance matrix")
                if result:
                    st.error(f"Error: {result.get('message', 'Unknown error')}")

# Display matrix if available
if 'distance_matrix' in st.session_state and 'matrix_waypoints' in st.session_state:
    st.header("Distance Matrix Visualization")
    
    result = st.session_state.distance_matrix
    waypoints = st.session_state.matrix_waypoints
    
    # Create DataFrame for display
    distances = result['distances']
    durations = result.get('durations')
    
    waypoint_ids = [wp['id'] for wp in waypoints]
    
    # Distance matrix
    st.subheader("Distance Matrix")
    
    # Convert to DataFrame
    distance_df = pd.DataFrame(distances, index=waypoint_ids, columns=waypoint_ids)
    
    # Format for display
    display_df = distance_df.round(2)
    
    # Color coding
    st.dataframe(
        display_df.style.background_gradient(cmap='RdYlBu_r', axis=None),
        use_container_width=True
    )
    
    # Duration matrix (if available)
    if durations:
        st.subheader("Duration Matrix (seconds)")
        duration_df = pd.DataFrame(durations, index=waypoint_ids, columns=waypoint_ids)
        
        st.dataframe(
            duration_df.style.background_gradient(cmap='RdYlBu_r', axis=None),
            use_container_width=True
        )
    
    # Export options
    st.subheader("Export Options")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # CSV export
        csv_data = distance_df.to_csv()
        st.download_button(
            "📥 Download Distance CSV",
            data=csv_data,
            file_name=f"distance_matrix_{adapter}.csv",
            mime="text/csv",
            use_container_width=True
        )
    
    with col2:
        # JSON export
        json_data = json.dumps(result, indent=2)
        st.download_button(
            "📥 Download Full JSON",
            data=json_data,
            file_name=f"matrix_result_{adapter}.json",
            mime="application/json",
            use_container_width=True
        )
    
    with col3:
        # Use in solver
        if st.button("🚚 Use in Solver", use_container_width=True):
            st.session_state.solver_matrix = result
            st.session_state.solver_waypoints = waypoints
            st.success("✅ Matrix ready for solver!")
    
    # Analysis
    st.subheader("Matrix Analysis")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Distance statistics
        st.write("**Distance Statistics:**")
        flat_distances = [d for row in distances for d in row if d is not None and d > 0]
        
        if flat_distances:
            stats_df = pd.DataFrame({
                'Metric': ['Min', 'Max', 'Mean', 'Median', 'Std Dev'],
                'Value': [
                    f"{min(flat_distances):.2f}",
                    f"{max(flat_distances):.2f}",
                    f"{np.mean(flat_distances):.2f}",
                    f"{np.median(flat_distances):.2f}",
                    f"{np.std(flat_distances):.2f}"
                ]
            })
            st.dataframe(stats_df, use_container_width=True)
    
    with col2:
        # Nearest neighbors
        st.write("**Nearest Neighbors:**")
        
        for i, wp_id in enumerate(waypoint_ids):
            row_distances = [(j, distances[i][j]) for j in range(len(distances[i])) 
                           if i != j and distances[i][j] is not None]
            
            if row_distances:
                nearest_idx, nearest_dist = min(row_distances, key=lambda x: x[1])
                nearest_id = waypoint_ids[nearest_idx]
                st.write(f"**{wp_id}** → {nearest_id} ({nearest_dist:.2f})")

# Comparison section
if st.checkbox("🔄 Compare Adapters"):
    st.header("Adapter Comparison")
    
    if waypoints_data and len(available_adapters) > 1:
        compare_adapters = st.multiselect(
            "Select adapters to compare",
            available_adapters,
            default=available_adapters[:2]
        )
        
        if st.button("Compare Adapters") and len(compare_adapters) > 1:
            comparison_results = {}
            
            progress_bar = st.progress(0)
            
            for i, comp_adapter in enumerate(compare_adapters):
                progress_bar.progress(i / len(compare_adapters))
                
                # Extract coordinates
                origins = [{"lat": wp['location']['lat'], "lon": wp['location']['lon']} 
                          for wp in waypoints_data]
                
                payload = {
                    "adapter": comp_adapter,
                    "mode": mode,
                    "origins": origins,
                    "destinations": origins
                }
                
                result = api_client.get_distance_matrix(payload)
                
                if result and 'distances' in result:
                    distances = result['distances']
                    flat_distances = [d for row in distances for d in row if d is not None and d > 0]
                    
                    comparison_results[comp_adapter] = {
                        'mean_distance': np.mean(flat_distances) if flat_distances else 0,
                        'max_distance': max(flat_distances) if flat_distances else 0,
                        'total_distance': sum(flat_distances) if flat_distances else 0
                    }
            
            progress_bar.progress(1.0)
            
            # Display comparison
            if comparison_results:
                comp_df = pd.DataFrame(comparison_results).T
                comp_df = comp_df.round(2)
                
                st.subheader("Adapter Comparison Results")
                st.dataframe(comp_df, use_container_width=True)
                
                # Visualization
                import plotly.express as px
                
                fig = px.bar(
                    x=list(comparison_results.keys()),
                    y=[comparison_results[adapter]['mean_distance'] for adapter in comparison_results],
                    title="Mean Distance by Adapter"
                )
                st.plotly_chart(fig, use_container_width=True)

# Help section
with st.expander("ℹ️ Help & Information"):
    st.markdown("""
    **Distance Adapters:**
    
    **Offline Adapters:**
    - **haversine**: Great circle distance, fast and offline
    - **euclidean**: Planar distance, good for benchmarks
    - **osm_graph**: Local OSM routing, downloads map data
    
    **Online Adapters:**
    - **openrouteservice**: Real road routing, requires API key
    - **google**: Google Maps routing, requires API key  
    - **mapbox**: Mapbox routing, requires API key
    
    **Travel Modes:**
    - **driving**: Car routing with roads
    - **walking**: Pedestrian routing
    - **cycling**: Bicycle routing
    
    **Matrix Format:**
    - Rows = Origins, Columns = Destinations
    - Diagonal elements are typically 0 (same location)
    - Values represent distance/time between locations
    
    **Use Cases:**
    - Validate waypoint accessibility
    - Compare routing methods
    - Analyze geographic distribution
    - Prepare data for VRP solving
    """)