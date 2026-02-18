import streamlit as st
from langchain_ollama import ChatOllama
from .vrp_tools import (
    update_waypoint_location,
    update_multiple_waypoints,
    get_route_summary,
    compare_solutions,
    get_modification_history,
    reset_to_original
)

OLLAMA_HOST = "http://localhost:11434"
OLLAMA_MODEL_ID = "qwen3:latest"

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
    """
    Initialize and return a VRP optimization agent with comprehensive tool binding and system prompt.
    
    The agent is configured with:
    - Tool selection guidance for single vs batch waypoint updates
    - Workflow instructions for confirmation and comparison
    - History tracking and impact explanation capabilities
    
    Returns:
        ChatOllama: LLM agent with VRP tools and system prompt, or None if initialization fails
    """
    try:
        llm = ChatOllama(
            base_url=OLLAMA_HOST,
            model=OLLAMA_MODEL_ID,
            temperature=0
        )
        
        tools = [
            update_waypoint_location,
            update_multiple_waypoints,
            get_route_summary,
            compare_solutions,
            get_modification_history,
            reset_to_original
        ]
        
        # Bind tools to LLM
        agent = llm.bind_tools(tools)
        return agent
    except Exception as e:
        st.error(f"Error initializing VRP agent: {e}")
        return None