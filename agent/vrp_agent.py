import streamlit as st
import json
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import StateGraph, END
from typing import TypedDict, List, Any
import time

from .vrp_tools import (
    update_waypoint_location,
    update_multiple_waypoints,
    get_route_summary,
    compare_solutions,
    get_modification_history,
    reset_to_original,
    modify_waypoint_constraints,
    create_single_route_scenario
)

OLLAMA_HOST = "http://localhost:11434"
OLLAMA_MODEL_ID = "qwen3:latest"

# ===== DEFINE STATE =====
class AgentState(TypedDict):
    """Persistent state throughout the workflow"""
    messages: List[Any]
    tool_results: List[dict]
    tools_executed: List[str]
    final_response: str
    completed: bool

# ===== COMPREHENSIVE SYSTEM PROMPT =====
SYSTEM_PROMPT = """
You are a Vehicle Routing Optimization Agent. You help users modify waypoints and re-optimize routes.

AVAILABLE TOOLS:
1. update_waypoint_location() - Update single customer coordinates
2. update_multiple_waypoints() - Update multiple customers at once  
3. get_route_summary() - Show current routes and metrics
4. compare_solutions() - Compare original vs modified solutions
5. get_modification_history() - Show all changes made
6. reset_to_original() - Reset to original waypoint positions
7. modify_waypoint_constraints() - Remove time windows or other constraints and re-optimize
8. create_single_route_scenario() - Replace waypoints and optimize for single route with 1 vehicle

WORKFLOW:
1. Execute tools SEQUENTIALLY (not in parallel)
2. Wait for state updates between tool calls
3. Use results from previous tools in subsequent calls
4. Only generate final response after ALL tools complete
5. Always show comparison metrics after modifications

MULTI-WAYPOINT UPDATES - TOOL SELECTION:
- For "move customer_1 to X,Y and customer_3 to A,B" → use update_multiple_waypoints()
- For "move customer_5 to X,Y" → use update_waypoint_location()
- Always call compare_solutions() after updates to show impact
- Use update_multiple_waypoints() for batch updates (more efficient than multiple single calls)

WAYPOINT UPDATE WORKFLOW:
1. Always confirm waypoint changes before applying
2. Explain what will change: "I will move customer_X from (old_lat, old_lon) to (new_lat, new_lon)"
3. Apply the change using appropriate tool
4. Call compare_solutions() to show routing impact
5. Show specific metrics: distance saved, time saved, route changes

CONSTRAINT MODIFICATIONS:
- To remove ALL time windows: "Remove time windows from all customers and re-optimize"
- To remove time windows from specific customers: "Remove time windows from customer_1, customer_3"
- The agent will re-optimize routes after removing constraints
- After removing time windows, call compare_solutions() to show improvements
- Explain the impact: "Removing time windows reduces delivery time constraints and may allow faster routes"

MULTI-TOOL SEQUENCES (VERY IMPORTANT):
- If user asks to "remove time windows AND compare": 
  1. First: Call modify_waypoint_constraints()
  2. Wait for completion and state update
  3. Then: Call compare_solutions()
  4. Then: Generate final response with actual numbers
- If user asks to "move customers AND show history":
  1. First: Call update_multiple_waypoints()
  2. Wait for completion
  3. Then: Call get_modification_history()
  4. Then: Generate final response with cumulative impact
- DO NOT call multiple tools at once. Execute them one at a time.

HISTORY TRACKING & CUMULATIVE IMPACT:
- All modifications are automatically tracked
- Use get_modification_history() to show what changes have been made
- Always mention cumulative improvements when showing history
- Explain which customers have been moved and the impact
- Show: "Total improvements so far: 15.2km distance saved, 8 minutes faster"
- Track modification count: "This is modification #3 in this session"
- Include before/after metrics for each modification

EXAMPLE RESPONSES FOR HISTORY:
- "I've moved customer_5 from (40.7128, -74.006) to (40.7589, -73.9851). This is modification #3 in this session."
- "Total improvements so far: 15.2km distance saved, 8 minutes faster, 1 fewer route needed"
- "Cumulative impact from all 5 modifications: 42.8km saved, 25 minutes faster routing"

PARSING USER INPUT FOR SINGLE ROUTE SCENARIO:
When user provides waypoint data in ANY format, convert to JSON and call create_single_route_scenario().

SUPPORTED INPUT FORMATS (user can use any of these):
1. CSV-like: "customer_1 40.7282 -74.0776; customer_2 40.7589 -73.9851"
2. Verbose: "Point 1 lat 40.7282, lon -74.0776, Point 2 lat 40.7589, lon -73.9851"
3. Short: "c1: 40.7282, -74.0776; c2: 40.7589, -73.9851"
4. Labeled: "customer 1 latitude 40.7282 longitude -74.0776"
5. List format: "40.7282, -74.0776 (customer 1); 40.7589, -73.9851 (customer 2)"

SINGLE ROUTE SCENARIO WORKFLOW:
1. Parse ANY format the user provides
2. Extract: id/name, latitude, longitude
3. Create JSON array: [{"id": "customer_1", "lat": 40.7282, "lon": -74.0776}, ...]
4. Ask for confirmation of the parsed waypoints
5. Show the user what you parsed: "Is this correct? I will create a new single-route scenario with these waypoints."
6. Call create_single_route_scenario() with this JSON string
7. Show results: total distance, duration, route sequence

PARSING RULES:
- Extract numbers as coordinates (first = latitude, second = longitude)
- Extract text as customer ID/name (auto-generate if missing: customer_1, customer_2, etc.)
- Ignore extra text (units, punctuation, etc.)
- Handle decimal numbers (e.g., 40.7282, -74.0776)
- Negative numbers = longitude (West)
- Positive small numbers (< 90) with larger second number = latitude, longitude pattern

EXAMPLE CONVERSIONS:
- User: "Point 1 lat 40.7282, lon -74.0776" 
  → JSON: [{"id": "customer_1", "lat": 40.7282, "lon": -74.0776}]

- User: "c1: 40.7282, -74.0776; c2: 40.7589, -73.9851"
  → JSON: [{"id": "c1", "lat": 40.7282, "lon": -74.0776}, {"id": "c2", "lat": 40.7589, "lon": -73.9851}]

- User: "customer 1 latitude 40.7282 longitude -74.0776; customer 2 latitude 40.7589 longitude -73.9851"
  → JSON: [{"id": "customer_1", "lat": 40.7282, "lon": -74.0776}, {"id": "customer_2", "lat": 40.7589, "lon": -73.9851}]

SINGLE ROUTE SCENARIO DETAILS:
- 1 vehicle with infinite capacity
- Service duration: 300 seconds per customer (5 minutes)
- No time windows (customers can be visited anytime)
- Optimizes for shortest route through all customers
- Depot remains the same as previous session

PARSING VALIDATION:
- Always validate that you have at least id, lat, lon for each waypoint
- If parsing fails or is ambiguous, ask user for clarification
- Once parsed correctly, call create_single_route_scenario() with the JSON string
- Show the user what you parsed before executing

COMPARISON & EXPLANATION:
- Use compare_solutions() to show impact of changes
- Show specific metrics: distance, duration, number of routes, capacity utilization
- Explain in simple terms: "Moving customer_5 to the north saved 3.2km because it's now closer to customer_2"
- Always quantify improvements with actual numbers
- Show percentage improvements when relevant: "15% faster delivery time"

CRITICAL EXECUTION RULES:
1. DO NOT call multiple tools in a single response
2. Call ONE tool at a time and wait for results
3. After a tool completes, the system will ask you what to do next
4. If you need to call another tool, you will be asked in the next turn
5. ONLY call compare_solutions() AFTER other tools complete and you are explicitly asked for comparison

TOOL CALLING FORMAT:
- Call exactly ONE tool per response
- Wait for the tool result before deciding what to do next
- The system will show you the tool output, then ask for your next action

IMPORTANT RULES:
1. DO NOT call multiple tools at once. Execute them one at a time.
2. Always wait for state updates between tool calls
3. Always show comparison metrics after modifications
4. Always explain routing impacts in simple, understandable terms
5. Track cumulative improvements across the session
6. Be specific with numbers - never say "improved" without saying by how much
7. If user provides waypoint data for single route, ask for confirmation before executing
"""

@st.cache_resource
def get_vrp_agent_graph():
    """Create LangGraph workflow for sequential tool execution with comprehensive state management"""
    
    llm = ChatOllama(
        base_url=OLLAMA_HOST,
        model=OLLAMA_MODEL_ID,
        temperature=0.1
    )
    
    tools = [
        update_waypoint_location,
        update_multiple_waypoints,
        get_route_summary,
        compare_solutions,
        get_modification_history,
        reset_to_original,
        modify_waypoint_constraints,
        create_single_route_scenario
    ]
    
    agent_llm = llm.bind_tools(tools)
    
    # ===== DEFINE WORKFLOW NODES =====
    
    def process_tool_call(state: AgentState) -> AgentState:
        """Execute a single tool call sequentially"""
        messages = state["messages"]
        
        # Get latest response from LLM
        last_message = messages[-1]
        
        if not hasattr(last_message, 'tool_calls') or not last_message.tool_calls:
            return state
        
        # Execute ONLY the FIRST tool (sequential execution - one at a time)
        tool_call = last_message.tool_calls[0]
        
        # Extract tool_name and tool_args safely
        if isinstance(tool_call, dict):
            tool_name = tool_call.get('name', 'unknown')
            tool_args = tool_call.get('args', {})
        else:
            tool_name = tool_call.name if hasattr(tool_call, 'name') else 'unknown'
            tool_args = tool_call.args if hasattr(tool_call, 'args') else {}
        
        print(f"\n🔨 Executing tool: {tool_name}")
        
        # Tool mapping
        tools_map = {
            'update_waypoint_location': update_waypoint_location,
            'update_multiple_waypoints': update_multiple_waypoints,
            'get_route_summary': get_route_summary,
            'compare_solutions': compare_solutions,
            'get_modification_history': get_modification_history,
            'reset_to_original': reset_to_original,
            'modify_waypoint_constraints': modify_waypoint_constraints,
            'create_single_route_scenario': create_single_route_scenario,
        }
        
        if tool_name in tools_map:
            try:
                # Invoke tool with proper error handling
                result = tools_map[tool_name].invoke(tool_args)
                print(f"✅ {tool_name} completed")
                
                # ===== WAIT FOR STATE UPDATE =====
                time.sleep(0.5)
                
                # Add tool result to state
                state["tool_results"].append({
                    'tool': tool_name,
                    'result': result,
                    'status': 'success'
                })
                state["tools_executed"].append(tool_name)
                
                # Add ToolMessage to conversation
                state["messages"].append(
                    ToolMessage(
                        content=result,
                        tool_call_id=tool_name,
                        name=tool_name
                    )
                )
                
            except Exception as e:
                print(f"❌ {tool_name} failed: {e}")
                import traceback
                traceback.print_exc()
                state["tool_results"].append({
                    'tool': tool_name,
                    'error': str(e),
                    'status': 'failed'
                })
                # Add error message so LLM knows tool failed
                state["messages"].append(
                    ToolMessage(
                        content=f"Tool {tool_name} failed with error: {str(e)}",
                        tool_call_id=tool_name,
                        name=tool_name
                    )
                )
        
        return state
    
    def should_continue(state: AgentState) -> str:
        """Decide if we need more tool calls or should generate response"""
        messages = state["messages"]
        last_message = messages[-1]
        
        # ===== KEY FIX: Prevent infinite loops =====
        # After tools have been executed, only allow LLM to call ONE more tool max
        # If tools were already executed AND we're back to LLM with no new tool calls, stop
        if state["tools_executed"]:
            # If LLM has tool calls, execute the next one
            if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
                print(f"\n🔧 Tool calls detected: {[tc.name if hasattr(tc, 'name') else tc.get('name') for tc in last_message.tool_calls]}")
                return "execute_tool"
            # If LLM has no new tool calls after executing first tool, generate response
            else:
                print(f"\n📝 Tools executed. LLM provided analysis. Generating final response...")
                return "end"
        
        # On first pass, if LLM has tool calls, execute them
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            print(f"\n🔧 Tool calls detected: {[tc.name if hasattr(tc, 'name') else tc.get('name') for tc in last_message.tool_calls]}")
            return "execute_tool"
        
        # If LLM has no tool calls, generate final response
        print(f"\n📝 No tool calls. Generating response...")
        return "end"
    
    def call_llm(state: AgentState) -> AgentState:
        """Call LLM with conversation history and current VRP data"""
        
        # Build system message with current VRP data
        if 'vrp_data' in st.session_state:
            dynamic_prompt = build_dynamic_system_prompt(st.session_state.vrp_data)
            system_message = SystemMessage(content=dynamic_prompt)
        else:
            system_message = SystemMessage(content=SYSTEM_PROMPT)
        
        # Prepare messages for LLM
        messages_for_llm = [system_message] + state["messages"]
        
        # Call LLM
        response = agent_llm.invoke(messages_for_llm)
        
        # Add response to state
        state["messages"].append(response)
        
        return state
    
    def generate_response(state: AgentState) -> AgentState:
        """Generate final response with all tool results and analysis"""
        
        if not state["tools_executed"]:
            # No tools were called - LLM answered directly
            last_message = state["messages"][-1]
            state["final_response"] = last_message.content if hasattr(last_message, 'content') else str(last_message)
        else:
            # Tools were executed - build response from tool results
            tool_results_summary = json.dumps(state["tool_results"], indent=2)
            
            # Check if any tools failed
            failed_tools = [tr for tr in state["tool_results"] if tr['status'] == 'failed']
            
            if failed_tools:
                # If tools failed, show what happened
                state["final_response"] = f"""
## Tool Execution Summary

✅ **Successful Tools:** {len([t for t in state['tool_results'] if t['status'] == 'success'])}
❌ **Failed Tools:** {len(failed_tools)}

### Failed Tools:
{json.dumps(failed_tools, indent=2)}

### Successful Tools:
{json.dumps([t for t in state['tool_results'] if t['status'] == 'success'], indent=2)}

**Recommendation:** Please try again or check the error details above.
"""
            else:
                # All tools succeeded - ask LLM to interpret results
                interpretation_prompt = f"""
You successfully executed these tools in this order:
{tool_results_summary}

Based on the tool results, provide a comprehensive analysis:

1. What was changed (be specific)
2. Key metrics improvements or changes (ACTUAL NUMBERS from results):
   - Distance changes (before -> after, and % improvement)
   - Duration changes (before -> after)
   - Route changes (number of routes)
   - Capacity utilization
3. Impact on routing
4. Recommendations for further optimization

CRITICAL: Use ACTUAL NUMBERS from the tool results. Never say "improved" without numbers.
Format numbers clearly:
- Distance: Show in km with decimal places
- Time: Show in minutes or hours
- Improvement: Show both absolute and percentage change
"""
                
                llm = ChatOllama(base_url=OLLAMA_HOST, model=OLLAMA_MODEL_ID, temperature=0.3)
                response = llm.invoke([HumanMessage(content=interpretation_prompt)])
                state["final_response"] = response.content
        
        state["completed"] = True
        return state
    
    # ===== BUILD GRAPH =====
    graph = StateGraph(AgentState)
    
    # Add nodes
    graph.add_node("call_llm", call_llm)
    graph.add_node("execute_tool", process_tool_call)
    graph.add_node("generate_response", generate_response)
    
    # Add edges
    graph.add_conditional_edges(
        "call_llm",
        should_continue,
        {
            "execute_tool": "execute_tool",
            "call_llm": "call_llm",
            "end": "generate_response"
        }
    )
    
    graph.add_conditional_edges(
        "execute_tool",
        lambda state: "call_llm",  # After tool executes, ask LLM what to do next
        {"call_llm": "call_llm"}
    )
    
    graph.add_edge("generate_response", END)
    
    # Start from call_llm
    graph.set_entry_point("call_llm")
    
    return graph.compile()


def build_dynamic_system_prompt(vrp_data: dict) -> str:
    """Build system prompt with actual VRP data embedded for LLM context"""
    
    # Extract key data
    waypoints = vrp_data.get("waypoints", [])
    fleet = vrp_data.get("fleet", [])
    current_result = vrp_data.get("current_result", {})
    routes = current_result.get("routes", [])
    modification_history = vrp_data.get("modification_history", [])
    
    # Calculate summary stats
    total_waypoints = len(waypoints)
    total_customers = len([w for w in waypoints if w.get("type") == "customer"])
    total_demand = sum(
        w.get("demand", [0])[0] if w.get("demand") else 0 
        for w in waypoints if w.get("type") == "customer"
    )
    total_vehicles = len(fleet)
    total_distance = sum(r.get("total_distance", 0) for r in routes)
    total_duration = sum(r.get("total_duration", 0) for r in routes)
    
    # Build JSON summary (lightweight - no full waypoints/fleet/routes to keep prompt size manageable)
    vrp_summary = {
        "total_waypoints": total_waypoints,
        "total_customers": total_customers,
        "total_demand": total_demand,
        "total_vehicles": total_vehicles,
        "active_routes": len(routes),
        "total_distance_km": round(total_distance, 2),
        "total_duration_seconds": int(total_duration),
        "total_duration_hours": round(total_duration / 3600, 2),
        "modifications_made": len(modification_history),
    }
    
    # Build the complete prompt
    dynamic_prompt = f"""
{SYSTEM_PROMPT}

CURRENT VRP SESSION DATA:
```json
{json.dumps(vrp_summary, indent=2)}
```

SESSION SUMMARY:
- Total Waypoints: {total_waypoints} (Depot + {total_customers} Customers)
- Total Demand: {total_demand} units
- Available Vehicles: {total_vehicles}
- Active Routes: {len(routes)}
- Total Distance: {round(total_distance, 2)} km
- Total Duration: {int(total_duration)} seconds ({int(total_duration/3600)} hours {int((total_duration % 3600) / 60)} minutes)
- Modifications Made: {len(modification_history)}
"""
    
    # Add modification history if it exists
    if modification_history:
        dynamic_prompt += f"""
MODIFICATION HISTORY ({len(modification_history)} changes):
"""
        for i, mod in enumerate(modification_history, 1):
            action = mod.get('action', 'Unknown').replace('_', ' ').title()
            description = mod.get('description', 'No description')
            dynamic_prompt += f"\n{i}. {action} - {description}"
    
    return dynamic_prompt


def run_agent(user_message: str) -> dict:
    """Run the agent with LangGraph workflow for sequential tool execution"""
    
    agent_graph = get_vrp_agent_graph()
    
    # Initialize state
    initial_state = AgentState(
        messages=[HumanMessage(content=user_message)],
        tool_results=[],
        tools_executed=[],
        final_response="",
        completed=False
    )
    
    # Run workflow
    final_state = agent_graph.invoke(initial_state)
    
    return {
        "response": final_state["final_response"],
        "tools_used": final_state["tools_executed"],
        "tool_results": final_state["tool_results"]
    }
