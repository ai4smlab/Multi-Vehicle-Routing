import streamlit as st
import os
import sys

# Add the parent directory to the path to import agent
# sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from agent.vrp_agent import get_vrp_agent

st.set_page_config(page_title="VRP AI Agent", page_icon="🤖", layout="wide")
st.title("🤖 VRP AI Agent")

# Check if VRP session exists
if 'vrp_data' not in st.session_state:
    st.warning("⚠️ No VRP session found. Please run optimization first.")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🚚 Go to Solver", use_container_width=True):
            st.switch_page("pages/01_🚚_Solver.py")
    with col2:
        if st.button("🏠 Go to Home", use_container_width=True):
            st.switch_page("app.py")
    st.stop()

# Display current session info
st.sidebar.header("Current VRP Session")
vrp_data = st.session_state.vrp_data
st.sidebar.info(f"📍 Waypoints: {len(vrp_data['waypoints'])}")
st.sidebar.info(f"🚛 Vehicles: {len(vrp_data['fleet'])}")
st.sidebar.info(f"⚙️ Solver: {vrp_data['solver_config']['solver']}")
st.sidebar.info(f"🔄 Modifications: {len(vrp_data.get('modification_history', []))}")

# Show modification history in sidebar
if vrp_data.get("modification_history"):
    with st.sidebar.expander("📋 Modification History"):
        history = vrp_data["modification_history"]
        
        st.write(f"**{len(history)} modifications made**")
        
        for i, record in enumerate(reversed(history[-5:])):  # Show last 5
            st.write(f"**{i+1}.** {record['action'].replace('_', ' ').title()}")
            st.write(f"⏰ {record['timestamp'][:19]}")
            st.write(f"📝 Changes: {len(record['changes'])} customers")
            
            if record['improvement']['distance_change'] > 0:
                st.success(f"↓ {record['improvement']['distance_change']:.1f}km saved")
            elif record['improvement']['distance_change'] < 0:
                st.error(f"↑ {abs(record['improvement']['distance_change']):.1f}km added")

# Warning about requirements
st.warning("⚠️ Requires Ollama (llama3.1:8b-instruct-q6_K) running on localhost:11434", icon="⚠️")

# Initialize agent
agent = get_vrp_agent()
if agent is None:
    st.error("❌ Failed to initialize VRP agent. Please check Ollama is running.")
    st.stop()

# Initialize chat session
if "agent_session_id" not in st.session_state:
    st.session_state.agent_session_id = os.urandom(16).hex()
    st.session_state.agent_messages = []

# Display chat history
for message in st.session_state.agent_messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Chat input
if prompt := st.chat_input("Ask me to modify waypoints, e.g., 'Move customer_5 to latitude 40.7128, longitude -74.0060'"):
    st.session_state.agent_messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        
        with st.spinner("Agent is processing your request..."):
            try:
                # Call agent
                result = agent(prompt, session_id=st.session_state.agent_session_id)
                
                # Handle different response types
                if hasattr(result, 'content'):
                    if hasattr(result.content, 'text'):
                        full_response = result.content.text
                    else:
                        full_response = str(result.content)
                else:
                    full_response = str(result)
                    
                message_placeholder.markdown(full_response)
                
            except Exception as e:
                full_response = f"An error occurred: {e}"
                st.error(full_response)
                
        st.session_state.agent_messages.append({"role": "assistant", "content": full_response})

# Quick action buttons
st.subheader("Quick Actions")
col1, col2, col3 = st.columns(3)

with col1:
    if st.button("📊 Show Route Summary", use_container_width=True):
        st.session_state.agent_messages.append({"role": "user", "content": "Show me the current route summary"})
        st.rerun()

with col2:
    if st.button("📈 Compare Solutions", use_container_width=True):
        st.session_state.agent_messages.append({"role": "user", "content": "Compare the original and current solutions"})
        st.rerun()

with col3:
    if st.button("🔄 Reset to Original", use_container_width=True):
        st.session_state.agent_messages.append({"role": "user", "content": "Reset all waypoints to original positions"})
        st.rerun()