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

@st.cache_resource
def get_vrp_agent():
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