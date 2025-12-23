# VRP Engine Streamlit Interface

A comprehensive Streamlit application for the Multi-Vehicle Routing Problem (VRP) Engine, providing an analytical interface for route optimization, benchmarking, and performance analysis.

## Features

### 🚚 Route Optimization
- Interactive solver interface with multiple optimization engines
- Support for OR-Tools, VROOM, and Pyomo solvers
- Flexible waypoint input (JSON, file upload, sample data)
- Fleet configuration and constraint management
- Real-time route visualization on interactive maps

### 📊 Benchmark Testing
- Standard dataset support (Solomon, VRPLIB)
- Multi-solver performance comparison
- Automated benchmarking with configurable parameters
- Performance metrics and statistical analysis
- Historical results tracking

### 🗺️ Real-World Data Integration
- OpenStreetMap POI search and import
- Convert real locations to VRP waypoints
- Geographic search by place name or coordinates
- Multiple POI categories (restaurants, hospitals, shops, etc.)
- Seamless integration with solver interface

### 📏 Distance Matrix Calculator
- Multiple distance calculation methods
- Support for offline (haversine, euclidean) and online (ORS, Google, Mapbox) adapters
- Travel mode selection (driving, walking, cycling)
- Matrix visualization and analysis
- Adapter performance comparison

### 📈 Performance Analytics
- Comprehensive performance visualization
- Solver comparison and trend analysis
- Statistical insights and recommendations
- Data export capabilities
- Historical performance tracking

## Installation

### Prerequisites
- Python 3.8+
- FastAPI backend running on `http://localhost:8000`

### Setup
1. Navigate to the streamlit-app directory:
   ```bash
   cd streamlit-app
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Start the Streamlit application:
   ```bash
   streamlit run app.py
   ```

4. Open your browser to `http://localhost:8501`

## Usage

### Getting Started
1. Ensure the FastAPI backend is running
2. Navigate through the sidebar pages
3. Start with the Solver page for basic route optimization
4. Use OSM Data to import real-world locations
5. Run Benchmarks to compare solver performance
6. Analyze results in the Analytics page

### Page Overview

#### 🚚 Solver
- Input waypoints via JSON, file upload, or use sample data
- Configure fleet parameters (vehicles, capacity, time windows)
- Select solver and optimization parameters
- View optimized routes and performance metrics
- Interactive map visualization

#### 📊 Benchmarks
- Select from available benchmark datasets
- Choose solvers for comparison
- Run automated benchmarks with configurable time limits
- View performance comparison charts and statistics
- Track historical benchmark results

#### 🗺️ OSM Data
- Search for Points of Interest by location and category
- Preview results on interactive maps
- Convert POIs to VRP waypoints with customizable parameters
- Export waypoints for use in solver
- Support for various POI types (amenities, shops, tourism)

#### 📏 Distance Matrix
- Calculate travel distances between waypoints
- Compare different distance calculation methods
- Visualize distance matrices with color coding
- Export matrices for external use
- Analyze geographic distribution of waypoints

#### 📈 Analytics
- Visualize solver performance over time
- Compare multiple solvers across various metrics
- Generate correlation analysis and insights
- Export analytical data and reports
- Automated performance recommendations

## Configuration

### Backend Connection
The application connects to the FastAPI backend at `http://localhost:8000` by default. Ensure the backend is running before starting the Streamlit app.

### API Keys (Optional)
For online distance adapters, configure API keys in the backend:
- `ORS_API_KEY` for OpenRouteService
- `GOOGLE_API_KEY` for Google Maps
- `MAPBOX_TOKEN` for Mapbox

## Data Formats

### Waypoints JSON Format
```json
[
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
  }
]
```

### Fleet Configuration
```json
[
  {
    "id": "vehicle_1",
    "capacity": [20],
    "start": null,
    "end": null,
    "time_window": {"start": 28800, "end": 72000}
  }
]
```

## Troubleshooting

### Common Issues

**Backend Connection Failed**
- Ensure FastAPI backend is running on port 8000
- Check that all required dependencies are installed in backend
- Verify no firewall blocking localhost connections

**Map Visualization Issues**
- Ensure folium and streamlit-folium are installed
- Check browser JavaScript is enabled
- Try refreshing the page if maps don't load

**Large Dataset Performance**
- Use smaller time limits for large problems
- Consider using faster solvers (VROOM) for initial testing
- Monitor memory usage with very large datasets

**OSM Search Failures**
- Check internet connection for OSM queries
- Try different search terms or smaller geographic areas
- Increase timeout for complex searches

## Development

### Project Structure
```
streamlit-app/
├── app.py                 # Main application entry point
├── pages/                 # Multi-page application
│   ├── 01_🚚_Solver.py
│   ├── 02_📊_Benchmarks.py
│   ├── 03_🗺️_OSM_Data.py
│   ├── 04_📏_Distance_Matrix.py
│   └── 05_📈_Analytics.py
├── components/            # Reusable components
│   └── api_client.py      # FastAPI communication
├── utils/                 # Utility functions
│   ├── data_processing.py
│   └── visualization.py
└── requirements.txt       # Dependencies
```

### Adding New Features
1. Create new page in `pages/` directory
2. Add utility functions in `utils/`
3. Update API client if new endpoints needed
4. Follow existing naming conventions and structure

## Contributing

1. Follow the existing code structure and naming conventions
2. Add appropriate error handling and user feedback
3. Include help documentation for new features
4. Test with various data sizes and edge cases
5. Update this README for significant changes

## License

This project is part of the Multi-Vehicle Routing Engine and follows the same license terms.