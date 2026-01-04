import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import folium
from streamlit_folium import st_folium
from typing import List, Dict, Any

def create_comparison_chart(results: Dict[str, Dict]) -> go.Figure:
    """Create comparison chart for benchmark results"""
    solvers = list(results.keys())
    distances = [results[solver].get('total_distance', 0) for solver in solvers]
    times = [results[solver].get('solve_time', 0) for solver in solvers]
    
    fig = go.Figure()
    
    # Distance bars
    fig.add_trace(go.Bar(
        name='Total Distance',
        x=solvers,
        y=distances,
        yaxis='y',
        offsetgroup=1
    ))
    
    # Time bars (secondary y-axis)
    fig.add_trace(go.Bar(
        name='Solve Time (s)',
        x=solvers,
        y=times,
        yaxis='y2',
        offsetgroup=2
    ))
    
    fig.update_layout(
        title='Solver Performance Comparison',
        xaxis_title='Solver',
        yaxis=dict(title='Distance', side='left'),
        yaxis2=dict(title='Time (seconds)', side='right', overlaying='y'),
        barmode='group'
    )
    
    return fig

def create_route_map(waypoints: List[Dict], routes: List[Dict] = None) -> folium.Map:
    """Create interactive map with waypoints and routes"""
    if not waypoints:
        # Default to NYC if no waypoints
        m = folium.Map(location=[40.7128, -74.0060], zoom_start=12)
        return m
    
    # Calculate center
    lats = [wp['location']['lat'] for wp in waypoints]
    lons = [wp['location']['lon'] for wp in waypoints]
    center_lat = sum(lats) / len(lats)
    center_lon = sum(lons) / len(lons)
    
    m = folium.Map(location=[center_lat, center_lon], zoom_start=12)
    
    # Add waypoints
    colors = ['red', 'blue', 'green', 'purple', 'orange', 'darkred', 'lightred', 'beige', 'darkblue', 'darkgreen']
    
    for i, wp in enumerate(waypoints):
        lat, lon = wp['location']['lat'], wp['location']['lon']
        wp_type = wp.get('type', 'customer')
        
        # Different icons for different types
        if wp_type == 'depot':
            icon = folium.Icon(color='red', icon='home')
        else:
            icon = folium.Icon(color='blue', icon='info-sign')
        
        folium.Marker(
            [lat, lon],
            popup=f"{wp.get('id', 'Unknown')}<br>Type: {wp_type}<br>Demand: {wp.get('demand', [0])}",
            tooltip=wp.get('id', 'Unknown'),
            icon=icon
        ).add_to(m)
    
    # Add routes if provided
    if routes:
        for i, route in enumerate(routes):
            color = colors[i % len(colors)]
            waypoint_ids = route.get('waypoint_ids', [])
            
            # Get coordinates for this route
            route_coords = []
            for wp_id in waypoint_ids:
                for wp in waypoints:
                    if wp['id'] == wp_id:
                        route_coords.append([wp['location']['lat'], wp['location']['lon']])
                        break
            
            if len(route_coords) > 1:
                folium.PolyLine(
                    route_coords,
                    color=color,
                    weight=3,
                    opacity=0.8,
                    popup=f"Vehicle: {route.get('vehicle_id', 'Unknown')}"
                ).add_to(m)
    
    return m

def display_metrics(result: Dict[str, Any]):
    """Display key metrics from solver results"""
    if not result:
        st.warning("No results to display")
        return
    
    # Handle nested data structure from API response
    if 'data' in result and isinstance(result['data'], dict):
        data = result['data']
    else:
        data = result
    
    # Check if routes exist
    if 'routes' not in data:
        st.warning(f"No 'routes' key found. Available keys: {list(data.keys())}")
        return
    
    routes = data['routes']
    if not routes:
        st.warning("No routes in result")
        return
    
    # Calculate metrics
    total_distance = sum(route.get('total_distance', 0) for route in routes)
    total_duration = sum(route.get('total_duration', 0) for route in routes if route.get('total_duration'))
    num_vehicles = len(routes)
    
    # Display metrics in three columns
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Total Distance (km)", f"{total_distance:.2f}")
    
    with col2:
        st.metric("Vehicles Used", num_vehicles)
    
    with col3:
        if total_duration and total_duration > 0:
            st.metric("Total Duration (s)", f"{total_duration}")
        else:
            st.metric("Total Duration", "N/A")

def create_performance_chart(benchmark_results: List[Dict]) -> go.Figure:
    """Create performance chart for multiple benchmark runs"""
    df = pd.DataFrame(benchmark_results)
    
    if df.empty:
        return go.Figure()
    
    fig = px.scatter(
        df, 
        x='solve_time', 
        y='total_distance',
        color='solver',
        size='num_waypoints',
        hover_data=['dataset'],
        title='Solver Performance: Distance vs Time'
    )
    
    fig.update_layout(
        xaxis_title='Solve Time (seconds)',
        yaxis_title='Total Distance'
    )
    
    return fig