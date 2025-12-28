# AI Agent for Multi-Vehicle-Routing

This AI agent allows you to conversationally modify waypoint coordinates and re-optimize routes using natural language.

## Features

- **Single Waypoint Updates**: Move individual customers to new coordinates
- **Batch Updates**: Move multiple customers in one command
- **Route Comparison**: Compare original vs modified solutions
- **History Tracking**: Track all modifications with metrics
- **Reset Functionality**: Restore original waypoint positions

## Setup

### Prerequisites

1. **Ollama**: Install and run Ollama with the required model
   ```bash
   # macOS
   brew install ollama
   
   # Start Ollama
   ollama serve
   
   # Pull the model
   ollama pull llama3.1:8b-instruct-q6_K
   ```

2. **Python Dependencies**: Install the required packages
   ```bash
   cd streamlit-app
   pip install strands-agents strands-agents-tools
   ```

### Quick Setup

Run the automated setup script:
```bash
./setup_ai_agent.sh
```

## Usage

1. **Start the Backend**: 
   ```bash
   cd backend
   uvicorn main:app --reload
   ```

2. **Start the Frontend**:
   ```bash
   cd streamlit-app
   streamlit run app.py
   ```

3. **Run Optimization**: Use the Solver page to optimize routes

4. **Launch AI Agent**: Click "🤖 Launch AI Agent" button

## Example Commands

### Single Waypoint Updates
- "Move customer_1 to latitude 40.7589, longitude -73.9851"
- "Update customer_5 coordinates to 40.7128, -74.0060"
- "Change depot location to 40.7282, -74.0776"

### Multiple Waypoint Updates
- "Move customer_1 to 40.7589, -73.9851 and customer_2 to 40.7282, -74.0776"
- "Update customer_1 to 40.7128, -74.0060 and customer_3 to 40.7589, -73.9851"

### Information Commands
- "Show me the current route summary"
- "Compare the original and current solutions"
- "What changes have I made so far?"
- "Show modification history"

### Reset Commands
- "Reset all waypoints to original positions"
- "Go back to the original solution"

## Architecture

```
agent/
├── vrp_agent.py      # Main agent with Ollama integration
└── vrp_tools.py      # Custom tools for VRP operations

streamlit-app/pages/
└── 02_🤖_AI_Agent.py # Chat interface
```

## Tools Available

1. **update_waypoint_location()** - Update single customer coordinates
2. **update_multiple_waypoints()** - Update multiple customers at once
3. **get_route_summary()** - Show current routes and metrics
4. **compare_solutions()** - Compare original vs modified solutions
5. **get_modification_history()** - Show all changes made
6. **reset_to_original()** - Reset to original waypoint positions

## Session Management

The AI agent uses Streamlit session state to:
- Store original and current waypoints
- Track modification history
- Maintain solver configuration
- Compare before/after metrics

## Troubleshooting

### Common Issues

1. **"No VRP session found"**
   - Run optimization in the Solver page first
   - Ensure you clicked "🤖 Launch AI Agent" after optimization

2. **"Failed to initialize VRP agent"**
   - Check if Ollama is running: `ollama serve`
   - Verify the model is installed: `ollama list`

3. **"Customer not found"**
   - Check customer IDs in your waypoints JSON
   - Use exact IDs like "customer_1", "depot", etc.

4. **"Re-optimization failed"**
   - Ensure backend API is running
   - Check if coordinates are valid (latitude: -90 to 90, longitude: -180 to 180)

### Model Requirements

- **Model**: llama3.1:8b-instruct-q6_K
- **Memory**: ~5GB RAM for the model
- **Disk**: ~4.7GB for model storage

## Performance

- **Session Data**: Stored in Streamlit session state (no external storage)
- **Re-optimization**: Uses existing FastAPI endpoints
- **Response Time**: 2-5 seconds per modification (depends on problem size)

## Future Enhancements

- Fleet modification capabilities
- Constraint adjustments (time windows, capacities)
- Multi-objective optimization
- Real-time route visualization updates