import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
from datetime import datetime, timedelta

st.set_page_config(page_title="Analytics", page_icon="📈", layout="wide")

st.title("📈 Performance Analytics")
st.markdown("Analyze and visualize VRP solver performance and results")

# Initialize session state for analytics data
if 'analytics_data' not in st.session_state:
    st.session_state.analytics_data = []

# Sidebar filters
st.sidebar.header("Analytics Filters")

# Data source selection
data_sources = []
if 'benchmark_results' in st.session_state and st.session_state.benchmark_results:
    data_sources.append("Benchmark Results")
if 'solver_result' in st.session_state:
    data_sources.append("Latest Solver Run")

if not data_sources:
    st.warning("No data available for analysis. Please run some benchmarks or solver operations first.")
    st.stop()

selected_source = st.sidebar.selectbox("Data Source", data_sources)

# Load data based on selection
if selected_source == "Benchmark Results":
    df = pd.DataFrame(st.session_state.benchmark_results)
elif selected_source == "Latest Solver Run":
    # Convert latest solver result to DataFrame format
    result = st.session_state.solver_result
    if result.get('routes'):
        solver_data = []
        for route in result['routes']:
            solver_data.append({
                'solver': 'latest_run',
                'vehicle_id': route.get('vehicle_id', 'unknown'),
                'total_distance': route.get('total_distance', 0),
                'total_duration': route.get('total_duration', 0),
                'num_waypoints': len(route.get('waypoint_ids', [])),
                'timestamp': datetime.now().timestamp()
            })
        df = pd.DataFrame(solver_data)
    else:
        st.error("No route data available in latest solver result")
        st.stop()

if df.empty:
    st.warning("No data to analyze")
    st.stop()

# Filter controls
if 'solver' in df.columns:
    available_solvers = df['solver'].unique()
    selected_solvers = st.sidebar.multiselect(
        "Select Solvers",
        available_solvers,
        default=available_solvers
    )
    df = df[df['solver'].isin(selected_solvers)]

# Date range filter (if timestamp available)
if 'timestamp' in df.columns:
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='s')
    
    min_date = df['datetime'].min().date()
    max_date = df['datetime'].max().date()
    
    if min_date != max_date:
        date_range = st.sidebar.date_input(
            "Date Range",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date
        )
        
        if len(date_range) == 2:
            start_date, end_date = date_range
            df = df[(df['datetime'].dt.date >= start_date) & 
                   (df['datetime'].dt.date <= end_date)]

# Main analytics content
if selected_source == "Benchmark Results":
    st.header("Benchmark Performance Analysis")
    
    # Key metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_runs = len(df)
        st.metric("Total Runs", total_runs)
    
    with col2:
        avg_distance = df['total_distance'].mean()
        st.metric("Avg Distance", f"{avg_distance:.2f}")
    
    with col3:
        avg_time = df['solve_time'].mean() if 'solve_time' in df.columns else 0
        st.metric("Avg Solve Time", f"{avg_time:.2f}s")
    
    with col4:
        unique_datasets = df['dataset'].nunique() if 'dataset' in df.columns else 0
        st.metric("Datasets Tested", unique_datasets)
    
    # Performance comparison charts
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Distance vs Solve Time")
        
        if 'solve_time' in df.columns and len(df) > 1:
            fig = px.scatter(
                df, 
                x='solve_time', 
                y='total_distance',
                color='solver',
                size='num_waypoints' if 'num_waypoints' in df.columns else None,
                hover_data=['dataset'] if 'dataset' in df.columns else None,
                title="Solver Performance Comparison"
            )
            fig.update_layout(
                xaxis_title="Solve Time (seconds)",
                yaxis_title="Total Distance"
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Insufficient data for scatter plot")
    
    with col2:
        st.subheader("Solver Performance Distribution")
        
        if 'solver' in df.columns and len(df['solver'].unique()) > 1:
            fig = px.box(
                df,
                x='solver',
                y='total_distance',
                title="Distance Distribution by Solver"
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            # Alternative: histogram of distances
            fig = px.histogram(
                df,
                x='total_distance',
                title="Distance Distribution",
                nbins=20
            )
            st.plotly_chart(fig, use_container_width=True)
    
    # Detailed performance table
    st.subheader("Detailed Results")
    
    # Summary statistics by solver
    if 'solver' in df.columns:
        summary_stats = df.groupby('solver').agg({
            'total_distance': ['count', 'mean', 'min', 'max', 'std'],
            'solve_time': ['mean', 'min', 'max'] if 'solve_time' in df.columns else ['count'],
            'num_vehicles': ['mean'] if 'num_vehicles' in df.columns else ['count']
        }).round(2)
        
        st.dataframe(summary_stats, use_container_width=True)
    
    # Raw data table
    with st.expander("Raw Data"):
        st.dataframe(df, use_container_width=True)

elif selected_source == "Latest Solver Run":
    st.header("Latest Solution Analysis")
    
    # Route-level analysis
    st.subheader("Route Performance")
    
    # Metrics
    col1, col2, col3 = st.columns(3)
    
    with col1:
        total_distance = df['total_distance'].sum()
        st.metric("Total Distance", f"{total_distance:.2f}")
    
    with col2:
        num_vehicles = len(df)
        st.metric("Vehicles Used", num_vehicles)
    
    with col3:
        avg_route_length = df['num_waypoints'].mean()
        st.metric("Avg Route Length", f"{avg_route_length:.1f} stops")
    
    # Route comparison
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Distance by Vehicle")
        
        fig = px.bar(
            df,
            x='vehicle_id',
            y='total_distance',
            title="Distance per Vehicle"
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.subheader("Route Length Distribution")
        
        fig = px.bar(
            df,
            x='vehicle_id',
            y='num_waypoints',
            title="Waypoints per Vehicle"
        )
        st.plotly_chart(fig, use_container_width=True)
    
    # Route details table
    st.subheader("Route Details")
    
    display_df = df[['vehicle_id', 'total_distance', 'num_waypoints']].copy()
    display_df['total_distance'] = display_df['total_distance'].round(2)
    
    if 'total_duration' in df.columns:
        display_df['total_duration'] = df['total_duration'].round(0)
    
    st.dataframe(display_df, use_container_width=True)

# Advanced analytics
st.header("Advanced Analytics")

# Time series analysis (if multiple data points)
if 'datetime' in df.columns and len(df) > 5:
    st.subheader("Performance Over Time")
    
    # Group by date and calculate daily averages
    daily_stats = df.groupby(df['datetime'].dt.date).agg({
        'total_distance': 'mean',
        'solve_time': 'mean' if 'solve_time' in df.columns else 'count'
    }).reset_index()
    
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    
    # Distance trend
    fig.add_trace(
        go.Scatter(
            x=daily_stats['datetime'],
            y=daily_stats['total_distance'],
            name="Avg Distance",
            line=dict(color='blue')
        ),
        secondary_y=False
    )
    
    # Solve time trend (if available)
    if 'solve_time' in daily_stats.columns:
        fig.add_trace(
            go.Scatter(
                x=daily_stats['datetime'],
                y=daily_stats['solve_time'],
                name="Avg Solve Time",
                line=dict(color='red')
            ),
            secondary_y=True
        )
    
    fig.update_xaxes(title_text="Date")
    fig.update_yaxes(title_text="Distance", secondary_y=False)
    fig.update_yaxes(title_text="Solve Time (s)", secondary_y=True)
    
    st.plotly_chart(fig, use_container_width=True)

# Correlation analysis
if len(df.select_dtypes(include=[np.number]).columns) > 2:
    st.subheader("Correlation Analysis")
    
    # Select numeric columns
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    correlation_matrix = df[numeric_cols].corr()
    
    fig = px.imshow(
        correlation_matrix,
        title="Feature Correlation Matrix",
        color_continuous_scale='RdBu',
        aspect='auto'
    )
    st.plotly_chart(fig, use_container_width=True)

# Export analytics
st.header("Export Analytics")

col1, col2, col3 = st.columns(3)

with col1:
    # Export current data
    csv_data = df.to_csv(index=False)
    st.download_button(
        "📥 Export Data (CSV)",
        data=csv_data,
        file_name=f"vrp_analytics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv",
        use_container_width=True
    )

with col2:
    # Export summary statistics
    if 'solver' in df.columns:
        summary = df.groupby('solver').describe()
        summary_csv = summary.to_csv()
        st.download_button(
            "📊 Export Summary (CSV)",
            data=summary_csv,
            file_name=f"vrp_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            use_container_width=True
        )

with col3:
    # Clear analytics data
    if st.button("🗑️ Clear Analytics Data", use_container_width=True):
        if 'benchmark_results' in st.session_state:
            st.session_state.benchmark_results = []
        st.success("Analytics data cleared!")
        st.rerun()

# Insights and recommendations
with st.expander("🔍 Insights & Recommendations"):
    st.markdown("### Automated Insights")
    
    if 'solver' in df.columns and len(df['solver'].unique()) > 1:
        # Best performing solver
        avg_by_solver = df.groupby('solver')['total_distance'].mean()
        best_solver = avg_by_solver.idxmin()
        best_distance = avg_by_solver.min()
        
        st.success(f"**Best Solver:** {best_solver} (avg distance: {best_distance:.2f})")
        
        # Performance variance
        std_by_solver = df.groupby('solver')['total_distance'].std()
        most_consistent = std_by_solver.idxmin()
        
        st.info(f"**Most Consistent:** {most_consistent} (lowest variance)")
    
    if 'solve_time' in df.columns:
        # Speed vs quality trade-off
        fast_solver = df.loc[df['solve_time'].idxmin(), 'solver'] if 'solver' in df.columns else 'N/A'
        quality_solver = df.loc[df['total_distance'].idxmin(), 'solver'] if 'solver' in df.columns else 'N/A'
        
        if fast_solver != quality_solver:
            st.warning(f"**Trade-off Detected:** {fast_solver} is fastest, {quality_solver} gives best quality")
    
    st.markdown("### Recommendations")
    st.markdown("""
    - **For Production:** Use the most consistent solver for reliable results
    - **For Research:** Compare multiple solvers to understand trade-offs
    - **For Large Problems:** Consider faster solvers even if quality is slightly lower
    - **For Time-Critical:** Monitor solve time vs problem size relationship
    """)

# Help section
with st.expander("ℹ️ Analytics Help"):
    st.markdown("""
    **Available Metrics:**
    - **Total Distance:** Sum of all route distances
    - **Solve Time:** Time taken by optimization algorithm
    - **Num Vehicles:** Number of vehicles used in solution
    - **Num Waypoints:** Number of stops per route
    
    **Chart Types:**
    - **Scatter Plot:** Shows relationship between two metrics
    - **Box Plot:** Shows distribution and outliers
    - **Bar Chart:** Compares values across categories
    - **Time Series:** Shows trends over time
    
    **Correlation Matrix:**
    - Values near +1: Strong positive correlation
    - Values near -1: Strong negative correlation  
    - Values near 0: No correlation
    
    **Tips:**
    - Run multiple benchmarks to get meaningful analytics
    - Compare solvers on same datasets for fair comparison
    - Monitor performance trends over time
    - Export data for external analysis tools
    """)