import streamlit as st
from strands import Agent
from strands.models.ollama import OllamaModel
from .vrp_tools import (
    update_waypoint_location,
    update_multiple_waypoints,
    get_route_summary,
    compare_solutions,
    get_modification_history,
    reset_to_original
)

OLLAMA_HOST = "http://localhost:11434"
OLLAMA_MODEL_ID = "llama3.1:8b-instruct-q6_K"

SYSTEM_PROMPT = """
You are a Vehicle Routing Optimization Agent. You help users modify waypoints and re-optimize routes.

AVAILABLE TOOLS:
1. update_waypoint_location() - Update single customer coordinates
2. update_multiple_waypoints() - Update multiple customers at once  
3. get_route_summary() - Show current routes and metrics
4. compare_solutions() - Compare original vs modified solutions
5. get_modification_history() - Show all changes made
6. reset_to_original() - Reset to original waypoint positions

WORKFLOW:
1. Always confirm waypoint changes before applying
2. Use update_multiple_waypoints() for batch updates (more efficient)
3. Use update_waypoint_location() for single changes
4. Show comparison metrics after modifications
5. Explain routing impacts in simple terms

MULTI-WAYPOINT UPDATES:
- For "move customer_1 to X,Y and customer_3 to A,B" → use update_multiple_waypoints()
- For "move customer_5 to X,Y" → use update_waypoint_location()
- Always call compare_solutions() after updates to show impact

HISTORY TRACKING:
- All modifications are automatically tracked
- Use get_modification_history() to show what changes have been made
- Always mention cumulative improvements when showing history
- Explain which customers have been moved and the impact

EXAMPLE RESPONSES:
- "I've moved customer_5. This is modification #3 in this session."
- "Total improvements so far: 15.2km distance saved, 8 minutes faster"
"""

@st.cache_resource
def get_vrp_agent():
    try:
        ollama_model = OllamaModel(
            host=OLLAMA_HOST,
            model_id=OLLAMA_MODEL_ID,
            temperature=0.0
        )
        
        agent = Agent(
            name="VRPAgent",
            system_prompt=SYSTEM_PROMPT,
            model=ollama_model,
            tools=[
                update_waypoint_location,
                update_multiple_waypoints,
                get_route_summary,
                compare_solutions,
                get_modification_history,
                reset_to_original
            ]
        )
        return agent
    except Exception as e:
        st.error(f"Error initializing VRP agent: {e}")
        return None