import streamlit as st
import pandas as pd
import time
from components.api_client import get_api_client
from utils.visualization import create_comparison_chart, create_performance_chart

st.set_page_config(page_title="Benchmarks", page_icon="📊", layout="wide")

st.title("📊 Benchmark Testing")
st.markdown("Compare solver performance on standard VRP datasets")

# Initialize API client
api_client = get_api_client()

# Check if backend is available
if not api_client.check_health():
    st.error("❌ Backend API not available. Please start the FastAPI server.")
    st.stop()

# Get available capabilities
capabilities = api_client.get_capabilities()
available_solvers = capabilities.get('solvers', ['ortools'])

# Sidebar configuration
st.sidebar.header("Benchmark Configuration")

# Solver selection
selected_solvers = st.sidebar.multiselect(
    "Select Solvers to Compare",
    available_solvers,
    default=available_solvers[:2] if len(available_solvers) >= 2 else available_solvers
)

# Time limit
time_limit = st.sidebar.slider("Time Limit per Run (seconds)", 10, 300, 60)

# Main content
col1, col2 = st.columns([1, 2])

with col1:
    st.header("Dataset Selection")
    
    # Get available benchmarks
    with st.spinner("Loading available datasets..."):
        benchmarks = api_client.get_benchmarks()
    
    if not benchmarks:
        st.error("No benchmark datasets available")
        st.stop()
    
    # Dataset selection
    dataset_names = [b.get('name', 'Unknown') for b in benchmarks]
    selected_dataset = st.selectbox(
        "Choose Dataset",
        dataset_names,
        help="Select a benchmark dataset to test"
    )
    
    # Dataset info
    if selected_dataset:
        dataset_info = next((b for b in benchmarks if b.get('name') == selected_dataset), None)
        if dataset_info:
            st.subheader("Dataset Information")
            st.write(f"**Name:** {dataset_info.get('name', 'N/A')}")
            st.write(f"**Type:** {dataset_info.get('type', 'N/A')}")
            st.write(f"**Nodes:** {dataset_info.get('num_nodes', 'N/A')}")
            st.write(f"**Vehicles:** {dataset_info.get('num_vehicles', 'N/A')}")
            
            if 'description' in dataset_info:
                st.write(f"**Description:** {dataset_info['description']}")
    
    # Run benchmark button
    run_benchmark = st.button(
        "🚀 Run Benchmark",
        type="primary",
        use_container_width=True,
        disabled=not selected_solvers
    )

with col2:
    st.header("Results")
    
    if run_benchmark and selected_dataset and selected_solvers:
        # Initialize results storage
        if 'benchmark_results' not in st.session_state:
            st.session_state.benchmark_results = []
        
        results = {}
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # Load dataset
        with st.spinner("Loading dataset..."):
            dataset = api_client.load_benchmark(selected_dataset)
        
        if not dataset:
            st.error("Failed to load dataset")
        else:
            # Run each solver
            for i, solver in enumerate(selected_solvers):
                status_text.text(f"Running {solver}...")
                progress_bar.progress((i) / len(selected_solvers))
                
                start_time = time.time()
                
                # Prepare payload
                payload = {
                    "solver": solver,
                    "dataset": selected_dataset,
                    "time_limit": time_limit
                }
                
                # Run solver
                result = api_client.solve_vrp(payload)
                
                solve_time = time.time() - start_time
                
                if result.get('status') == 'success':
                    # Calculate metrics
                    routes = result.get('routes', [])
                    total_distance = sum(route.get('total_distance', 0) for route in routes)
                    num_vehicles = len(routes)
                    
                    results[solver] = {
                        'status': 'success',
                        'total_distance': total_distance,
                        'num_vehicles': num_vehicles,
                        'solve_time': solve_time,
                        'routes': routes
                    }
                    
                    # Store for analytics
                    st.session_state.benchmark_results.append({
                        'dataset': selected_dataset,
                        'solver': solver,
                        'total_distance': total_distance,
                        'solve_time': solve_time,
                        'num_vehicles': num_vehicles,
                        'num_waypoints': dataset.get('num_nodes', 0),
                        'timestamp': time.time()
                    })
                    
                else:
                    results[solver] = {
                        'status': 'failed',
                        'error': result.get('message', 'Unknown error'),
                        'solve_time': solve_time
                    }
            
            progress_bar.progress(1.0)
            status_text.text("Benchmark complete!")
            
            # Display results
            st.subheader("Comparison Results")
            
            # Results table
            results_data = []
            for solver, result in results.items():
                if result['status'] == 'success':
                    results_data.append({
                        'Solver': solver,
                        'Distance': f"{result['total_distance']:.2f}",
                        'Vehicles': result['num_vehicles'],
                        'Time (s)': f"{result['solve_time']:.2f}",
                        'Status': '✅ Success'
                    })
                else:
                    results_data.append({
                        'Solver': solver,
                        'Distance': 'N/A',
                        'Vehicles': 'N/A', 
                        'Time (s)': f"{result['solve_time']:.2f}",
                        'Status': f"❌ {result.get('error', 'Failed')}"
                    })
            
            if results_data:
                st.dataframe(pd.DataFrame(results_data), use_container_width=True)
                
                # Comparison chart
                successful_results = {k: v for k, v in results.items() if v['status'] == 'success'}
                if len(successful_results) > 1:
                    st.subheader("Performance Comparison")
                    chart = create_comparison_chart(successful_results)
                    st.plotly_chart(chart, use_container_width=True)
                
                # Best solution
                if successful_results:
                    best_solver = min(successful_results.keys(), 
                                    key=lambda x: successful_results[x]['total_distance'])
                    best_distance = successful_results[best_solver]['total_distance']
                    
                    st.success(f"🏆 Best Solution: **{best_solver}** with distance {best_distance:.2f}")

# Analytics section
if 'benchmark_results' in st.session_state and st.session_state.benchmark_results:
    st.header("📈 Historical Analytics")
    
    # Performance over time
    if len(st.session_state.benchmark_results) > 1:
        st.subheader("Performance Analysis")
        chart = create_performance_chart(st.session_state.benchmark_results)
        st.plotly_chart(chart, use_container_width=True)
    
    # Summary statistics
    st.subheader("Summary Statistics")
    df = pd.DataFrame(st.session_state.benchmark_results)
    
    if not df.empty:
        # Group by solver
        summary = df.groupby('solver').agg({
            'total_distance': ['mean', 'min', 'std'],
            'solve_time': ['mean', 'min', 'max'],
            'num_vehicles': 'mean'
        }).round(2)
        
        st.dataframe(summary, use_container_width=True)
        
        # Clear results button
        if st.button("🗑️ Clear Results"):
            st.session_state.benchmark_results = []
            st.rerun()

# Available datasets info
with st.expander("📋 Available Datasets"):
    if benchmarks:
        for benchmark in benchmarks:
            st.write(f"**{benchmark.get('name', 'Unknown')}**")
            st.write(f"- Type: {benchmark.get('type', 'N/A')}")
            st.write(f"- Nodes: {benchmark.get('num_nodes', 'N/A')}")
            st.write(f"- Vehicles: {benchmark.get('num_vehicles', 'N/A')}")
            if 'description' in benchmark:
                st.write(f"- Description: {benchmark['description']}")
            st.write("---")

# Help section
with st.expander("ℹ️ About Benchmarks"):
    st.markdown("""
    **Benchmark Datasets:**
    - **Solomon**: Classic VRPTW instances with time windows
    - **VRPLIB**: Standard VRP benchmark library
    - **Custom**: User-uploaded datasets
    
    **Metrics Explained:**
    - **Distance**: Total travel distance for all vehicles
    - **Vehicles**: Number of vehicles used in solution
    - **Time**: Solver execution time (not route time)
    
    **Solver Characteristics:**
    - **OR-Tools**: Exact/heuristic, handles complex constraints
    - **VROOM**: Fast heuristic, good for large instances
    - **Pyomo**: Mathematical programming, research-oriented
    
    **Tips:**
    - Compare multiple solvers on same dataset
    - Consider both solution quality and solve time
    - Larger time limits may improve solution quality
    """)