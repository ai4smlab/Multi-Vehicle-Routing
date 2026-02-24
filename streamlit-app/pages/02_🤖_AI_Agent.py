from datetime import datetime
import streamlit as st
import os
import sys
import speech_recognition as sr
from io import BytesIO
import json
from dotenv import load_dotenv

# Load environment variables from .env file
dotenv_path = os.path.join(os.path.dirname(__file__), '..', '..', 'backend', '.env')
load_dotenv(dotenv_path=dotenv_path)
print(f"DEBUG: Loaded .env from {dotenv_path}")
print(f"DEBUG: ANTHROPIC_API_KEY set: {bool(os.getenv('ANTHROPIC_API_KEY'))}")

# Add the parent directory to the path to import agent
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

# ===== NEW: Import run_agent from LangGraph =====
from agent.vrp_agent import run_agent
# ===== END NEW =====

# ===== KEEP: Debug code from original =====
st.write("DEBUG - Session state keys:", list(st.session_state.keys()))
if 'vrp_data' in st.session_state:
    st.write("DEBUG - vrp_data exists with keys:", list(st.session_state.vrp_data.keys()))

# Debug: Check session state
st.write("DEBUG - Session state keys:", list(st.session_state.keys()))
if 'vrp_data' in st.session_state:
    st.write("DEBUG - vrp_data contents:")
    for key, value in st.session_state.vrp_data.items():
        if key in ['waypoints', 'original_waypoints']:
            st.write(f"  {key}: {len(value)} items")
            st.json(value[:3])  # Show first 3 waypoints
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
# ===== END DEBUG CODE =====

st.set_page_config(page_title="VRP AI Agent", page_icon="🤖", layout="wide")
st.title("🤖 VRP AI Agent")

# ===== LLM MODEL SELECTION =====
st.sidebar.header("🤖 AI Model Configuration")

# Initialize LLM settings in session state if not present
if "llm_provider" not in st.session_state:
    st.session_state.llm_provider = "ollama"
if "llm_model" not in st.session_state:
    st.session_state.llm_model = None

# LLM Provider Selection
llm_provider = st.sidebar.radio(
    "Select LLM Provider:",
    options=["ollama", "claude"],
    index=0 if st.session_state.llm_provider == "ollama" else 1,
    format_func=lambda x: x.upper(),
    help="Choose between local Ollama or Claude API"
)

# Update session state
if llm_provider != st.session_state.llm_provider:
    st.session_state.llm_provider = llm_provider
    st.session_state.llm_model = None  # Reset model when provider changes
    st.rerun()

# Model selection based on provider
if llm_provider == "ollama":
    ollama_models = ["qwen3:latest", "qwen2.5:7b-instruct", "qwen2.5:14b", "llama3.1:8b-instruct"]
    selected_model = st.sidebar.selectbox(
        "Ollama Model:",
        options=ollama_models,
        index=0,
        help="Select which Ollama model to use"
    )
    st.session_state.llm_model = selected_model
    
    # Check Ollama connection
    import requests
    try:
        requests.get("http://localhost:11434/api/tags", timeout=2)
        st.sidebar.success("✅ Ollama is running")
    except Exception as e:
        st.sidebar.error("❌ Ollama not running on localhost:11434")
        
elif llm_provider == "claude":
    claude_models = [
        "claude-sonnet-4-20250514",
        "claude-3-5-sonnet-20241022",
        "claude-3-opus-20240229",
        "claude-3-haiku-20240307"
    ]
    selected_model = st.sidebar.selectbox(
        "Claude Model:",
        options=claude_models,
        index=0,
        help="Select which Claude model to use"
    )
    st.session_state.llm_model = selected_model
    
    # Check Claude API key
    if os.getenv("ANTHROPIC_API_KEY"):
        st.sidebar.success("✅ Claude API key configured")
    else:
        st.sidebar.error("❌ ANTHROPIC_API_KEY not set")
        st.sidebar.info("💡 Set it in .env file or environment variables")

# Display current model info
st.sidebar.divider()
st.sidebar.write(f"**Active Model:** `{st.session_state.llm_provider}/{st.session_state.llm_model or 'default'}`")
# ===== END LLM MODEL SELECTION =====

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
st.sidebar.header("📊 Current VRP Session")
vrp_data = st.session_state.vrp_data
st.sidebar.info(f"📍 Waypoints: {len(vrp_data['waypoints'])}")
st.sidebar.info(f"🚛 Vehicles: {len(vrp_data['fleet'])}")
st.sidebar.info(f"⚙️ Solver: {vrp_data['solver_config']['solver']}")
st.sidebar.info(f"🔄 Modifications: {len(vrp_data.get('modification_history', []))}")

# ===== KEEP: Show current waypoints in expandable section =====
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
# ===== END WAYPOINTS SECTION =====

# Show modification history in sidebar
if vrp_data.get("modification_history"):
    with st.sidebar.expander("📋 Modification History"):
        history = vrp_data["modification_history"]
        
        st.write(f"**{len(history)} modifications made**")
        
        for i, record in enumerate(reversed(history[-5:])):  # Show last 5
            st.write(f"**{i+1}.** {record.get('action', 'Unknown').replace('_', ' ').title()}")
            if 'timestamp' in record:
                st.write(f"⏰ {record['timestamp'][:19]}")
            
            if 'changes' in record:
                st.write(f"📝 Changes: {len(record['changes'])} customers")
            
            if 'improvement' in record and 'distance_change' in record['improvement']:
                if record['improvement']['distance_change'] > 0:
                    st.success(f"↓ {record['improvement']['distance_change']:.1f}km saved")
                elif record['improvement']['distance_change'] < 0:
                    st.error(f"↑ {abs(record['improvement']['distance_change']):.1f}km added")

# Dynamic status message based on selected LLM provider
if st.session_state.llm_provider == "ollama":
    import requests
    try:
        requests.get("http://localhost:11434/api/tags", timeout=2)
        st.success("✅ Ollama is running on localhost:11434", icon="✅")
    except Exception as e:
        st.error("❌ Ollama not running on localhost:11434", icon="❌")
        st.info("💡 Start Ollama with: `ollama serve`")
elif st.session_state.llm_provider == "claude":
    if os.getenv("ANTHROPIC_API_KEY"):
        st.success("✅ Claude API key is configured", icon="✅")
    else:
        st.error("❌ ANTHROPIC_API_KEY not set", icon="❌")
        st.info("💡 Get your API key from https://console.anthropic.com/ and set it in .env or environment variables")

# Initialize chat session
if "agent_session_id" not in st.session_state:
    st.session_state.agent_session_id = os.urandom(16).hex()
    st.session_state.agent_messages = []
    st.session_state.processing_message = None
    st.session_state.voice_transcript = None  # Store voice transcript for review

# Display chat history
for message in st.session_state.agent_messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# ===== NEW: Process message with LangGraph workflow =====
if st.session_state.processing_message is not None:
    with st.chat_message("assistant"):
        with st.spinner("Agent is processing your request..."):
            try:
                prompt = st.session_state.processing_message
                
                # Run agent with LangGraph (sequential tool execution)
                # Pass the selected LLM provider and model from session state
                result = run_agent(
                    prompt,
                    llm_provider=st.session_state.get("llm_provider"),
                    llm_model=st.session_state.get("llm_model")
                )
                
                # Display tools used
                if result["tools_used"]:
                    tools_display = ", ".join([f"`{t}`" for t in result["tools_used"]])
                    st.markdown(f"**🔧 Tools Used:** {tools_display}")
                    st.divider()
                
                # Display final response
                st.markdown(result["response"])
                
                # Add to chat history with tools info
                full_response = f"**🔧 Tools Used:** {', '.join(result['tools_used']) if result['tools_used'] else 'None'}\n\n{result['response']}"
                st.session_state.agent_messages.append({
                    "role": "assistant",
                    "content": full_response
                })
                
                # ===== NEW: Show debug info in expander =====
                with st.expander("🔍 Debug Information"):
                    st.write("**Tools Executed:**")
                    for tool in result["tools_used"]:
                        st.write(f"✅ {tool}")
                    
                    if result["tool_results"]:
                        st.write("\n**Tool Results:**")
                        for tool_result in result["tool_results"]:
                            st.write(f"**{tool_result['tool']}:**")
                            if tool_result['status'] == 'success':
                                # Try to parse JSON for pretty display
                                try:
                                    result_json = json.loads(tool_result['result'])
                                    st.json(result_json)
                                except:
                                    st.code(tool_result['result'], language="json")
                            else:
                                st.error(tool_result.get('error', 'Unknown error'))
                # ===== END DEBUG INFO =====
                
                st.session_state.processing_message = None
                st.rerun()
                
            except Exception as e:
                import traceback
                error_msg = f"❌ Error: {str(e)}"
                st.error(error_msg)
                
                # Show full traceback in expander
                with st.expander("📋 Error Details"):
                    st.code(traceback.format_exc())
                
                st.session_state.agent_messages.append({
                    "role": "assistant",
                    "content": error_msg
                })
                st.session_state.processing_message = None
                st.rerun()
# ===== END NEW =====

# ===== KEEP: Voice transcript editing section =====
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
# ===== END VOICE TRANSCRIPT SECTION =====

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
                    st.session_state.voice_transcript = voice_text  # Store transcript
                    st.rerun()  # Rerun to show editable textarea
                    
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
st.subheader("⚡ Quick Actions")
col1, col2, col3, col4 = st.columns(4)

with col1:
    if st.button("📊 Show Routes", use_container_width=True):
        st.session_state.agent_messages.append({"role": "user", "content": "Show me the current routes and metrics"})
        st.session_state.processing_message = "Show me the current routes and metrics"
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

with col4:
    if st.button("📝 Show History", use_container_width=True):
        st.session_state.agent_messages.append({"role": "user", "content": "Show modification history"})
        st.session_state.processing_message = "Show modification history"
        st.rerun()

# Export results
st.divider()
st.subheader("📥 Export Results")

col1, col2 = st.columns(2)

with col1:
    if st.button("📄 Export as JSON", use_container_width=True):
        json_data = json.dumps(vrp_data, indent=2)
        st.download_button(
            label="Download JSON",
            data=json_data,
            file_name=f"vrp_session_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json"
        )

with col2:
    if st.button("📊 Export as CSV", use_container_width=True):
        import csv
        from io import StringIO
        
        # Create CSV with routes
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(["Route", "Vehicle", "Waypoint", "Distance", "Duration"])
        
        for route in vrp_data.get('current_result', {}).get('routes', []):
            vehicle_id = route.get('vehicle_id')
            for wp_id in route.get('waypoint_ids', []):
                writer.writerow([
                    vehicle_id,
                    vehicle_id,
                    wp_id,
                    route.get('total_distance', 0),
                    route.get('total_duration', 0)
                ])
        
        st.download_button(
            label="Download CSV",
            data=output.getvalue(),
            file_name=f"vrp_routes_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )

# Add session info at bottom
with st.expander("ℹ️ Session Information"):
    col1, col2 = st.columns(2)
    
    with col1:
        st.metric("Session ID", st.session_state.agent_session_id[:8])
        st.metric("Messages", len(st.session_state.agent_messages))
    
    with col2:
        st.metric("Total Customers", len([w for w in vrp_data['waypoints'] if w.get('type') == 'customer']))
        st.metric("Total Demand", sum(w.get('demand', [0])[0] if w.get('demand') else 0 for w in vrp_data['waypoints']))