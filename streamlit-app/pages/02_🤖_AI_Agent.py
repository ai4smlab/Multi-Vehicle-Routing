from datetime import datetime
import streamlit as st
import os
import sys
import speech_recognition as sr
from io import BytesIO


# Add the parent directory to the path to import agent
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from agent.vrp_agent import get_vrp_agent
from agent.vrp_tools import (
    update_waypoint_location,
    update_multiple_waypoints,
    get_route_summary,
    compare_solutions,
    get_modification_history,
    reset_to_original
)

# Debug: Check session state
st.write("DEBUG - Session state keys:", list(st.session_state.keys()))
if 'vrp_data' in st.session_state:
    st.write("DEBUG - vrp_data exists with keys:", list(st.session_state.vrp_data.keys()))

# Debug: Check session state
# Debug: Check session state
st.write("DEBUG - Session state keys:", list(st.session_state.keys()))
if 'vrp_data' in st.session_state:
    st.write("DEBUG - vrp_data contents:")
    for key, value in st.session_state.vrp_data.items():
        if key in ['waypoints', 'original_waypoints']:
            st.write(f"  {key}: {len(value)} items")
            st.json(value[:3])  # Show first 2 waypoints
        elif key == 'fleet':
            st.write(f"  {key}: {len(value)} vehicles")
            st.json(value)
        elif key in ['original_result', 'current_result']:
            st.write(f"  {key}:")
            st.write(f"    Full structure:")
            st.json(value)  # Show complete result structure
        elif key == 'modification_history':
            st.write(f"  {key}: {len(value)} modifications")
        elif key == 'session_id':
            st.write(f"  {key}: {value}")
        else:
            st.write(f"  {key}:")
            st.json(value)







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

# ===== ADD THIS: Show current waypoints in expandable section =====
with st.sidebar.expander("📍 Current Waypoints"):
    for wp in vrp_data['waypoints']:
        wp_type = wp.get('type', 'unknown').upper()
        wp_id = wp.get('id')
        time_window = wp.get('time_window')
        
        status = "✅" if time_window is None else "⏱️"
        st.write(f"{status} **{wp_id}** ({wp_type})")
        
        if time_window:
            start_hr = time_window.get('start', 0) // 3600
            end_hr = time_window.get('end', 0) // 3600
            st.caption(f"   Time Window: {start_hr}:00 - {end_hr}:00")
        else:
            st.caption(f"   Time Window: None (No constraint)")
        
        demand = wp.get('demand', [0])[0] if wp.get('demand') else 0
        st.caption(f"   Demand: {demand} units")
# ===== END NEW CODE =====

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
st.warning("Requires Ollama (qwen3) running on localhost:11434", icon="⚠️")

# Initialize agent
agent = get_vrp_agent()
if agent is None:
    st.error("❌ Failed to initialize VRP agent. Please check Ollama is running.")
    st.stop()

# Initialize chat session
if "agent_session_id" not in st.session_state:
    st.session_state.agent_session_id = os.urandom(16).hex()
    st.session_state.agent_messages = []
    st.session_state.processing_message = None
    st.session_state.voice_transcript = None  # ⭐ Store voice transcript for review

# Display chat history
for message in st.session_state.agent_messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Check if we're waiting for a response
if st.session_state.processing_message is not None:
    with st.chat_message("assistant"):
        with st.spinner("Agent is processing your request..."):
            try:
                from langchain_core.messages import HumanMessage, SystemMessage
                from langchain_ollama import ChatOllama
                
                prompt = st.session_state.processing_message
                
                # Call agent with tool binding
                response = agent.invoke([HumanMessage(content=prompt)])
                
                # Check if tools were called
                if hasattr(response, 'tool_calls') and response.tool_calls:
                    # Execute tool calls
                    tool_results = []
                    
                    for tool_call in response.tool_calls:
                        tool_name = tool_call['name']
                        tool_args = tool_call['args']
                        
                        # Find and execute the tool
                        tools_map = {
                            'update_waypoint_location': update_waypoint_location,
                            'update_multiple_waypoints': update_multiple_waypoints,
                            'get_route_summary': get_route_summary,
                            'compare_solutions': compare_solutions,
                            'get_modification_history': get_modification_history,
                            'reset_to_original': reset_to_original
                        }
                        
                        if tool_name in tools_map:
                            result = tools_map[tool_name].invoke(tool_args)
                            tool_results.append(f"Tool: {tool_name}\nResult: {result}")
                    
                    # Now ask LLM to interpret the results in human-friendly format
                    llm = ChatOllama(base_url="http://localhost:11434", model="qwen3:latest", temperature=0.3)
                    
                    interpretation_prompt = f"""You are a helpful Vehicle Routing Problem (VRP) assistant. 
                    
The user asked: "{prompt}"

The system executed tools and returned this data:
{chr(10).join(tool_results)}

Please provide a clear, conversational summary of this information. Focus on:
- Number of waypoints and vehicles
- Route sequences (e.g., depot → customer_1 → customer_2 → depot)
- Total distance and duration in readable format
- Any important details about the solution

Be concise and friendly. Use natural language, not JSON."""
                    
                    narrative_response = llm.invoke([HumanMessage(content=interpretation_prompt)])
                    full_response = narrative_response.content

                    # # Display tools used (minimal, clean)
                    # tool_names = [tc['name'] for tc in response.tool_calls]
                    # st.markdown(f"**🔧 Tools Used:** {', '.join(tool_names)}")

                     # Add tools used to the response message
                    tool_names = [tc['name'] for tc in response.tool_calls]
                    full_response = f"**🔧 Tools Used:** {', '.join(tool_names)}\n\n{full_response}"

                else:
                    # No tools called, use direct response
                    full_response = response.content if hasattr(response, 'content') else str(response)
                
                st.session_state.agent_messages.append({"role": "assistant", "content": full_response})
                st.session_state.processing_message = None
                st.rerun()
                
            except Exception as e:
                import traceback
                full_response = f"An error occurred: {e}\n\n{traceback.format_exc()}"
                st.error(full_response)
                st.session_state.agent_messages.append({"role": "assistant", "content": full_response})
                st.session_state.processing_message = None
                st.rerun()

# ⭐ CHANGED - Display editable voice transcript if available
if st.session_state.voice_transcript is not None:
    st.info("🎤 **Voice Transcript - Edit Below and Send**", icon="ℹ️")
    edited_transcript = st.text_area(
        "Edit your voice message:",
        value=st.session_state.voice_transcript,
        height=100,
        key="edited_voice_input"
    )
    
    col_a, col_b = st.columns(2)
    
    with col_a:
        if st.button("✅ Send Message", use_container_width=True, type="primary"):
            if edited_transcript.strip():
                st.session_state.agent_messages.append({"role": "user", "content": edited_transcript})
                st.session_state.processing_message = edited_transcript
                st.session_state.voice_transcript = None
                st.rerun()
    
    with col_b:
        if st.button("🗑️ Discard", use_container_width=True):
            st.session_state.voice_transcript = None
            st.rerun()

# Chat input with voice option
if st.session_state.processing_message is None and st.session_state.voice_transcript is None:
    col1, col2 = st.columns([3, 1])  # 2-column layout
    
    with col1:
        prompt = st.chat_input("Ask me to modify waypoints, e.g., 'Move customer_5 to latitude 40.7128, longitude -74.0060'")
    
    with col2:  # Voice input column
        audio_data = st.audio_input("🎤 Record voice input")
        
        if audio_data is not None:
            try:
                # Convert audio bytes to text
                recognizer = sr.Recognizer()
                audio_bytes = BytesIO(audio_data.getvalue())
                
                with sr.AudioFile(audio_bytes) as source:
                    audio = recognizer.record(source)
                    voice_text = recognizer.recognize_google(audio)
                    st.session_state.voice_transcript = voice_text  # ⭐ Store transcript
                    st.rerun()  # ⭐ Rerun to show editable textarea
                    
            except sr.RequestError:
                st.error("❌ Speech recognition service unavailable")
            except sr.UnknownValueError:
                st.warning("⚠️ Could not understand audio - please try again")
            except Exception as e:
                st.error(f"❌ Error processing audio: {e}")
    
    if prompt:
        # Text input from chat_input
        st.session_state.agent_messages.append({"role": "user", "content": prompt})
        st.session_state.processing_message = prompt
        st.rerun()

# Quick action buttons
st.subheader("Quick Actions")
col1, col2, col3 = st.columns(3)

with col1:
    if st.button("📊 Show Route Summary", use_container_width=True):
        st.session_state.agent_messages.append({"role": "user", "content": "Show me the current route summary"})
        st.session_state.processing_message = "Show me the current route summary"
        st.rerun()

with col2:
    if st.button("📈 Compare Solutions", use_container_width=True):
        st.session_state.agent_messages.append({"role": "user", "content": "Compare the original and current solutions"})
        st.session_state.processing_message = "Compare the original and current solutions"
        st.rerun()

with col3:
    if st.button("🔄 Reset to Original", use_container_width=True):
        st.session_state.agent_messages.append({"role": "user", "content": "Reset all waypoints to original positions"})
        st.session_state.processing_message = "Reset all waypoints to original positions"
        st.rerun()