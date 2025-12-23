import streamlit as st
from components.api_client import get_api_client

# Page configuration
st.set_page_config(
    page_title="VRP Engine",
    page_icon="🚚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 3rem;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .status-success {
        color: #28a745;
        font-weight: bold;
    }
    .status-error {
        color: #dc3545;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# Main header
st.markdown('<h1 class="main-header">🚚 Vehicle Routing Problem Engine</h1>', unsafe_allow_html=True)

# Sidebar navigation info
st.sidebar.success("👆 Select a page above to get started")
st.sidebar.markdown("---")
st.sidebar.markdown("### Available Pages:")
st.sidebar.markdown("🚚 **Solver** - Optimize vehicle routes")
st.sidebar.markdown("📊 **Benchmarks** - Test with standard datasets")
st.sidebar.markdown("🗺️ **OSM Data** - Import real-world locations")
st.sidebar.markdown("📏 **Distance Matrix** - Calculate travel distances")
st.sidebar.markdown("📈 **Analytics** - Performance analysis")

# Main content
col1, col2 = st.columns([2, 1])

with col1:
    st.markdown("## Welcome to the VRP Engine Interface")
    st.markdown("""
    This Streamlit application provides an analytical interface for the Vehicle Routing Problem (VRP) engine.
    
    **Key Features:**
    - 🎯 **Route Optimization**: Solve VRP problems with multiple solvers (OR-Tools, VROOM, Pyomo)
    - 📊 **Benchmark Testing**: Compare solver performance on standard datasets
    - 🗺️ **Real-World Data**: Import locations from OpenStreetMap
    - 📈 **Analytics**: Visualize and analyze routing solutions
    - 🔧 **Interactive Tools**: Easy-to-use forms and visualizations
    
    **Getting Started:**
    1. Ensure the FastAPI backend is running on `http://localhost:8000`
    2. Select a page from the sidebar to begin
    3. Follow the instructions on each page
    """)

with col2:
    st.markdown("## System Status")
    
    # Check API health
    api_client = get_api_client()
    
    with st.spinner("Checking backend status..."):
        is_healthy = api_client.check_health()
    
    if is_healthy:
        st.markdown('<p class="status-success">✅ Backend API is running</p>', unsafe_allow_html=True)
        
        # Get capabilities
        capabilities = api_client.get_capabilities()
        if capabilities:
            st.markdown("### Available Components")
            
            adapters = capabilities.get('adapters', [])
            solvers = capabilities.get('solvers', [])
            
            if adapters:
                st.markdown("**Distance Adapters:**")
                for adapter in adapters:
                    st.markdown(f"- {adapter}")
            
            if solvers:
                st.markdown("**Solvers:**")
                for solver in solvers:
                    st.markdown(f"- {solver}")
    else:
        st.markdown('<p class="status-error">❌ Backend API not available</p>', unsafe_allow_html=True)
        st.error("""
        The FastAPI backend is not running. Please start it with:
        
        ```bash
        cd backend
        uvicorn main:app --reload
        ```
        """)

# Footer
st.markdown("---")
st.markdown("### About")
st.markdown("""
This interface connects to the Multi-Vehicle Routing Engine backend to provide:
- Interactive route optimization
- Performance benchmarking
- Real-world data integration
- Comprehensive analytics

Built with Streamlit for rapid prototyping and analysis.
""")

# Quick start guide
with st.expander("🚀 Quick Start Guide"):
    st.markdown("""
    **For Route Optimization:**
    1. Go to the **🚚 Solver** page
    2. Input waypoints (use sample data or create your own)
    3. Configure fleet settings
    4. Select a solver and run optimization
    5. View results and route visualization
    
    **For Benchmark Testing:**
    1. Go to the **📊 Benchmarks** page
    2. Select a dataset (e.g., Solomon C101)
    3. Choose solvers to compare
    4. Run benchmarks and analyze results
    
    **For Real-World Data:**
    1. Go to the **🗺️ OSM Data** page
    2. Search for locations (e.g., "Manhattan restaurants")
    3. Convert POIs to waypoints
    4. Use in solver for realistic routing
    """)