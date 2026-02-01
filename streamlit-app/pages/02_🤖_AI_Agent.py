import streamlit as st
import os
import sys
import speech_recognition as sr
from io import BytesIO

# Add the parent directory to the path to import agent
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
st.warning("Requires Ollama (llama3.1:8b-instruct-q6_K) running on localhost:11434", icon="⚠️")

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
                prompt = st.session_state.processing_message
                
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
                
                st.session_state.agent_messages.append({"role": "assistant", "content": full_response})
                st.session_state.processing_message = None
                st.rerun()
                
            except Exception as e:
                full_response = f"An error occurred: {e}"
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