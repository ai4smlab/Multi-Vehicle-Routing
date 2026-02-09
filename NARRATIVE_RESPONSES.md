# Human-Friendly Narrative Responses

## Overview

The VRP AI Agent now provides conversational, narrative responses instead of raw JSON data.

## How It Works

### Two-Step Process:

**Step 1: Tool Execution**
```python
# Agent decides which tool to call
response = agent.invoke([HumanMessage(content=prompt)])

# Execute the tool
if response.tool_calls:
    result = tools_map[tool_name].invoke(tool_args)
```

**Step 2: Narrative Generation**
```python
# LLM interprets the tool results
interpretation_prompt = f"""
You are a helpful VRP assistant.

User asked: "{prompt}"
Tool returned: {result}

Provide a clear, conversational summary focusing on:
- Number of waypoints and vehicles
- Route sequences (depot → customer_1 → customer_2 → depot)
- Total distance and duration in readable format
- Important details about the solution

Be concise and friendly. Use natural language, not JSON.
"""

narrative_response = llm.invoke([HumanMessage(content=interpretation_prompt)])
```

## Example Transformation

### Before (Raw JSON):
```json
{
  "session_info": {
    "total_waypoints": 3,
    "total_vehicles": 2,
    "solver": "ortools"
  },
  "routes": [
    {
      "vehicle_id": "vehicle_2",
      "waypoint_ids": ["0", "1", "2", "0"],
      "total_distance": 20.200083763625912,
      "total_duration": 1816
    }
  ]
}
```

### After (Narrative):
```
Your VRP solution has been optimized! Here's what I found:

📍 **Waypoints**: 3 locations (1 depot + 2 customers)
🚛 **Fleet**: 2 vehicles available
⚙️ **Solver**: OR-Tools

**Route for vehicle_2:**
depot → customer_1 → customer_2 → depot

📏 **Total Distance**: 20.2 km
⏱️ **Total Duration**: 30 minutes 16 seconds

The route successfully visits all customers and returns to the depot.
```

## Benefits

✅ **User-Friendly**: Natural language instead of technical JSON  
✅ **Contextual**: LLM understands the user's question  
✅ **Informative**: Highlights key metrics and patterns  
✅ **Conversational**: Feels like talking to a human expert  

## Configuration

The narrative generation uses:
- **Model**: qwen3:latest (same as agent)
- **Temperature**: 0.3 (slightly creative for natural language)
- **Prompt**: Structured to extract key VRP insights

## Customization

To adjust the narrative style, modify the `interpretation_prompt` in the AI Agent page:

```python
interpretation_prompt = f"""
[Your custom instructions here]
- Adjust tone (formal/casual)
- Add/remove details
- Change formatting style
"""
```

## Performance

- **Latency**: +1-2 seconds for narrative generation
- **Accuracy**: LLM interprets data correctly
- **Consistency**: Structured prompt ensures reliable output
