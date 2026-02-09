# Migration from AWS Strands to LangChain

## Summary
Successfully migrated the VRP AI Agent from AWS Strands to LangChain. LangChain provides better session context management through Streamlit's native session state.

## Changes Made

### 1. **agent/vrp_tools.py**
- Replaced `from strands.tools import tool` with `from langchain.tools import tool`
- Removed global session storage (`_vrp_sessions`, `_session_lock`)
- Removed helper functions: `set_vrp_session_data()`, `get_vrp_session_data()`, `clear_vrp_session_data()`
- Updated `get_route_summary()` to use `st.session_state.vrp_data` directly (no session_id parameter)
- All tools now access session context via Streamlit's session state

### 2. **agent/vrp_agent.py**
- Replaced Strands imports with LangChain:
  - `from strands import Agent` → `from langchain.agents import AgentExecutor, create_react_agent`
  - `from strands.models.ollama import OllamaModel` → `from langchain_community.chat_models import ChatOllama`
  - Added `from langchain.prompts import PromptTemplate`
- Converted `SYSTEM_PROMPT` to `AGENT_PROMPT` with LangChain ReAct format
- Updated `get_vrp_agent()` to create LangChain agent:
  - Uses `ChatOllama` instead of `OllamaModel`
  - Creates `PromptTemplate` for agent prompt
  - Uses `create_react_agent()` to build agent
  - Returns `AgentExecutor` instead of Strands `Agent`

### 3. **streamlit-app/requirements.txt**
- Removed AWS Strands dependencies:
  - `strands-agents`
  - `strands-agents-tools`
- Added LangChain dependencies:
  - `langchain>=0.1.0`
  - `langchain-community>=0.0.10`
- Kept `ollama` for LLM backend

### 4. **streamlit-app/pages/02_🤖_AI_Agent.py**
- Removed import: `from agent.vrp_tools import set_vrp_session_data`
- Updated agent invocation:
  - Removed `set_vrp_session_data()` call (no longer needed)
  - Changed `agent(prompt, session_id=...)` to `agent.invoke({"input": prompt})`
  - Updated response extraction to use `result.get("output", str(result))`
- Session context now automatically passed via `st.session_state.vrp_data`

### 5. **Cleanup**
- Removed duplicate file: `agent/vrp_agent_langchain.py` (no longer needed)
- Single source of truth: `agent/vrp_agent.py` now uses LangChain

## Key Benefits

### 1. **Simplified Session Management**
- No need for global session storage with thread locks
- Direct access to Streamlit's session state
- Tools automatically have access to current VRP data

### 2. **Better Integration**
- LangChain is designed for conversational AI with built-in memory
- Native support for tool calling and agent workflows
- Easier to extend with additional LangChain features (memory, chains, etc.)

### 3. **Cleaner Code**
- Removed ~30 lines of session management boilerplate
- Tools are simpler without session_id parameters
- More maintainable architecture

## How Session Context Works Now

1. **VRP Data Storage**: When optimization runs, data is stored in `st.session_state.vrp_data`
2. **Tool Access**: All tools directly access `st.session_state.vrp_data` 
3. **Agent Invocation**: Agent is called with `agent.invoke({"input": prompt})`
4. **Context Persistence**: Streamlit maintains session state across interactions
5. **Tool Execution**: Tools read/write to session state, changes persist automatically

## Installation

```bash
cd streamlit-app
pip install -r requirements.txt
```

## Usage

The agent usage remains the same from the user's perspective:

```python
# Initialize agent (cached)
agent = get_vrp_agent()

# Invoke with user input
result = agent.invoke({"input": "Show me the route summary"})
response = result["output"]
```

## Testing

After migration, test the following:
1. ✅ Agent initialization with Ollama
2. ✅ Route summary retrieval
3. ✅ Single waypoint updates
4. ✅ Multiple waypoint updates
5. ✅ Solution comparison
6. ✅ Modification history
7. ✅ Reset to original

## Notes

- Ensure Ollama is running: `ollama serve`
- Model required: `ollama pull qwen3:latest`
- Backend must be running on `http://localhost:8000`
- All existing VRP functionality preserved
