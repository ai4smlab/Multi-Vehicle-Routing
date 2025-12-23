import streamlit as st
import pandas as pd
import json
from components.api_client import get_api_client
from utils.data_processing import pois_to_dataframe, convert_pois_to_waypoints

st.set_page_config(page_title="OSM Data", page_icon="🗺️", layout="wide")

st.title("🗺️ OpenStreetMap Data Import")
st.markdown("Import real-world locations from OpenStreetMap to create realistic VRP scenarios")

# Initialize API client
api_client = get_api_client()

# Check if backend is available
if not api_client.check_health():
    st.error("❌ Backend API not available. Please start the FastAPI server.")
    st.stop()

# Sidebar configuration
st.sidebar.header("Search Configuration")

# Search method
search_method = st.sidebar.radio(
    "Search Method",
    ["By Place Name", "By Coordinates"],
    help="Choose how to define the search area"
)

# Common parameters
poi_categories = {
    "Restaurants": {"key": "amenity", "value": "restaurant"},
    "Hospitals": {"key": "amenity", "value": "hospital"},
    "Schools": {"key": "amenity", "value": "school"},
    "Supermarkets": {"key": "shop", "value": "supermarket"},
    "Gas Stations": {"key": "amenity", "value": "fuel"},
    "ATMs": {"key": "amenity", "value": "atm"},
    "Pharmacies": {"key": "amenity", "value": "pharmacy"},
    "Hotels": {"key": "tourism", "value": "hotel"},
    "Custom": {"key": "", "value": ""}
}

category = st.sidebar.selectbox("POI Category", list(poi_categories.keys()))

if category == "Custom":
    key = st.sidebar.text_input("OSM Key", placeholder="amenity")
    value = st.sidebar.text_input("OSM Value", placeholder="restaurant")
else:
    key = poi_categories[category]["key"]
    value = poi_categories[category]["value"]
    st.sidebar.write(f"Key: `{key}`")
    st.sidebar.write(f"Value: `{value}`")

# Search parameters
limit = st.sidebar.number_input("Max Results", min_value=10, max_value=1000, value=100)
timeout = st.sidebar.number_input("Timeout (seconds)", min_value=30, max_value=300, value=120)

# Main content
col1, col2 = st.columns([1, 1])

with col1:
    st.header("Search Parameters")
    
    if search_method == "By Place Name":
        place = st.text_input(
            "Place Name",
            value="Manhattan, New York",
            help="Enter a place name (city, neighborhood, etc.)"
        )
        
        # Additional options
        include_ways = st.checkbox("Include Ways", value=True, help="Include linear features")
        include_relations = st.checkbox("Include Relations", value=True, help="Include complex features")
        
    else:  # By Coordinates
        st.subheader("Bounding Box")
        col_lat, col_lon = st.columns(2)
        
        with col_lat:
            north = st.number_input("North Latitude", value=40.8, format="%.6f")
            south = st.number_input("South Latitude", value=40.7, format="%.6f")
        
        with col_lon:
            east = st.number_input("East Longitude", value=-73.9, format="%.6f")
            west = st.number_input("West Longitude", value=-74.1, format="%.6f")
    
    # Search button
    search_button = st.button(
        "🔍 Search POIs",
        type="primary",
        use_container_width=True,
        disabled=not key or not value
    )

with col2:
    st.header("Search Results")
    
    if search_button:
        if not key or not value:
            st.error("Please specify both key and value for the search")
        else:
            with st.spinner("Searching OpenStreetMap..."):
                try:
                    if search_method == "By Place Name":
                        pois = api_client.get_osm_pois(
                            place=place,
                            key=key,
                            value=value,
                            limit=limit
                        )
                    else:
                        # For coordinate search, we'd need to implement bbox search
                        st.error("Coordinate search not yet implemented in this interface")
                        pois = []
                    
                    if pois:
                        st.success(f"✅ Found {len(pois)} POIs")
                        
                        # Store in session state
                        st.session_state.osm_pois = pois
                        st.session_state.search_params = {
                            'place': place if search_method == "By Place Name" else None,
                            'key': key,
                            'value': value,
                            'category': category
                        }
                        
                        # Display summary
                        st.subheader("Summary")
                        st.write(f"**Location:** {place if search_method == 'By Place Name' else 'Coordinate area'}")
                        st.write(f"**Category:** {category}")
                        st.write(f"**Total POIs:** {len(pois)}")
                        
                        # Sample POI info
                        if pois:
                            sample_poi = pois[0]
                            st.write("**Sample POI:**")
                            st.json({
                                "lat": sample_poi.get('lat'),
                                "lon": sample_poi.get('lon'),
                                "tags": sample_poi.get('tags', {})
                            })
                    
                    else:
                        st.warning("No POIs found. Try different search parameters.")
                        
                except Exception as e:
                    st.error(f"Search failed: {e}")

# Display results if available
if 'osm_pois' in st.session_state and st.session_state.osm_pois:
    st.header("POI Analysis")
    
    pois = st.session_state.osm_pois
    
    # Convert to DataFrame for analysis
    df = pois_to_dataframe(pois)
    
    if not df.empty:
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.subheader("POI Details")
            
            # Display table
            display_df = df[['name', 'type', 'lat', 'lon']].copy()
            display_df['lat'] = display_df['lat'].round(6)
            display_df['lon'] = display_df['lon'].round(6)
            
            st.dataframe(display_df, use_container_width=True, height=300)
            
            # Statistics
            st.subheader("Statistics")
            st.write(f"**Total POIs:** {len(df)}")
            st.write(f"**Unique Types:** {df['type'].nunique()}")
            
            # Type distribution
            type_counts = df['type'].value_counts()
            st.write("**Type Distribution:**")
            for poi_type, count in type_counts.head(5).items():
                st.write(f"- {poi_type}: {count}")
        
        with col2:
            st.subheader("Map Visualization")
            
            # Display map
            if len(df) > 0:
                st.map(df[['lat', 'lon']], use_container_width=True)
            
            # Convert to waypoints
            st.subheader("Convert to Waypoints")
            
            # Waypoint configuration
            default_demand = st.number_input("Default Demand", min_value=1, max_value=100, value=1)
            service_time = st.number_input("Service Time (seconds)", min_value=60, max_value=3600, value=300)
            
            if st.button("🔄 Convert to Waypoints", use_container_width=True):
                waypoints = convert_pois_to_waypoints(pois)
                
                # Update waypoints with user settings
                for wp in waypoints:
                    wp['demand'] = [default_demand]
                    wp['service_duration'] = service_time
                
                st.session_state.converted_waypoints = waypoints
                st.success(f"✅ Converted {len(waypoints)} POIs to waypoints")

# Display converted waypoints
if 'converted_waypoints' in st.session_state:
    st.header("Generated Waypoints")
    
    waypoints = st.session_state.converted_waypoints
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("Waypoints Preview")
        
        # Show first few waypoints
        preview_count = min(5, len(waypoints))
        for i in range(preview_count):
            wp = waypoints[i]
            st.write(f"**{wp['id']}**")
            st.write(f"- Location: ({wp['location']['lat']:.6f}, {wp['location']['lon']:.6f})")
            st.write(f"- Demand: {wp['demand']}")
            st.write(f"- Service Time: {wp['service_duration']}s")
            st.write("---")
        
        if len(waypoints) > preview_count:
            st.write(f"... and {len(waypoints) - preview_count} more waypoints")
    
    with col2:
        st.subheader("Export Options")
        
        # JSON export
        waypoints_json = json.dumps(waypoints, indent=2)
        
        st.download_button(
            label="📥 Download as JSON",
            data=waypoints_json,
            file_name=f"waypoints_{st.session_state.search_params.get('category', 'osm')}.json",
            mime="application/json",
            use_container_width=True
        )
        
        # Copy to solver
        if st.button("🚚 Use in Solver", use_container_width=True):
            # Store waypoints for solver page
            st.session_state.solver_waypoints = waypoints
            st.success("✅ Waypoints ready for solver! Go to the Solver page.")
        
        # Show JSON preview
        with st.expander("JSON Preview"):
            st.code(waypoints_json, language="json")

# Examples section
with st.expander("💡 Search Examples"):
    st.markdown("""
    **Popular Searches:**
    
    **Food Delivery:**
    - Place: "Manhattan, New York"
    - Category: Restaurants
    
    **Medical Supplies:**
    - Place: "Boston, Massachusetts" 
    - Category: Hospitals
    
    **Retail Distribution:**
    - Place: "Chicago, Illinois"
    - Category: Supermarkets
    
    **Service Routes:**
    - Place: "San Francisco, California"
    - Category: ATMs
    
    **Custom Searches:**
    - Key: "shop", Value: "bakery"
    - Key: "tourism", Value: "attraction"
    - Key: "amenity", Value: "bank"
    """)

# Help section
with st.expander("ℹ️ Help & Tips"):
    st.markdown("""
    **Search Tips:**
    - Use specific place names for better results
    - Try different POI categories for variety
    - Adjust the limit based on your needs
    - Larger areas may require higher timeouts
    
    **OSM Tags:**
    - **amenity**: Services (restaurant, hospital, school)
    - **shop**: Retail (supermarket, bakery, pharmacy)
    - **tourism**: Tourist attractions (hotel, museum)
    - **office**: Business locations
    
    **Waypoint Conversion:**
    - All POIs become "customer" type waypoints
    - Add a depot manually if needed
    - Adjust demands based on your use case
    - Service times can vary by POI type
    
    **Integration:**
    - Converted waypoints can be used directly in the Solver
    - Export JSON for external use
    - Combine with custom waypoints as needed
    """)