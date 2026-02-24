# AI Agent LLM Provider Switch - Setup Instructions

## Overview
The VRP AI Agent now supports switching between **Ollama (local)** and **Claude API (cloud)** models directly from the Streamlit UI.

## Features
- 🔄 **Dynamic Provider Switching**: Toggle between Ollama and Claude from the sidebar
- 🎯 **Model Selection**: Choose from multiple models within each provider
- ✅ **Connection Validation**: Automatic checks for API keys and service availability
- 💾 **Session Persistence**: Your selection is remembered during the session

## Setup

### Option 1: Ollama (Local - Default)
No additional setup required if you already have Ollama running.

**Required:**
- Ollama running on `localhost:11434`
- At least one model installed (e.g., `qwen3:latest`, `llama3.1:8b-instruct`)

**Start Ollama:**
```bash
ollama serve
```

**Install models (if not already installed):**
```bash
ollama pull qwen3:latest
ollama pull qwen2.5:7b-instruct
ollama pull llama3.1:8b-instruct
```

### Option 2: Claude API (Cloud)

**Required:**
- Anthropic API key
- `langchain-anthropic` package installed

**Step 1: Get API Key**
1. Go to https://console.anthropic.com/
2. Sign up or log in
3. Create a new API key
4. Copy the key

**Step 2: Set API Key**

Add to your `.env` file in the backend directory:
```bash
ANTHROPIC_API_KEY=sk-ant-api03-xxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

Or set as environment variable:
```bash
export ANTHROPIC_API_KEY=sk-ant-api03-xxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

**Step 3: Install langchain-anthropic**
```bash
cd /Users/zishanyusuf/Documents/Dr-Ala-Khamis/Multi-Vehicle-Routing/backend
pip install langchain-anthropic
```

Or add to requirements:
```bash
echo "langchain-anthropic" >> requirements.txt
```

## Usage

### 1. Navigate to AI Agent Page
Go to: `http://localhost:8501/pages/02_🤖_AI_Agent.py`

### 2. Select LLM Provider (Sidebar)
In the left sidebar, you'll see:
```
🤖 AI Model Configuration

Select LLM Provider:
  ○ OLLAMA
  ○ CLAUDE
```

### 3. Choose Model

**For Ollama:**
- `qwen3:latest` (default, recommended)
- `qwen2.5:7b-instruct` (faster, less accurate)
- `qwen2.5:14b` (balanced)
- `llama3.1:8b-instruct` (alternative)

**For Claude:**
- `claude-sonnet-4-20250514` (default, recommended)
- `claude-3-5-sonnet-20241022` (excellent balance)
- `claude-3-opus-20240229` (most powerful)
- `claude-3-haiku-20240307` (fastest, cheapest)

### 4. Verify Connection
The sidebar will show:
- ✅ Green checkmark if connected/configured
- ❌ Red error if there's an issue

### 5. Chat with AI Agent
Use the chat interface as normal. The agent will use your selected model.

## Available Models Comparison

### Ollama Models (Local, Free)
| Model | Speed | Quality | RAM Usage | Best For |
|-------|-------|---------|-----------|----------|
| qwen3:latest | Medium | High | ~8GB | General use |
| qwen2.5:7b-instruct | Fast | Good | ~6GB | Quick iterations |
| qwen2.5:14b | Medium | Very Good | ~12GB | Complex tasks |
| llama3.1:8b-instruct | Fast | Good | ~8GB | Alternative |

### Claude Models (API, Paid)
| Model | Speed | Quality | Cost | Best For |
|-------|-------|---------|------|----------|
| claude-sonnet-4 | Fast | Excellent | $$ | General use |
| claude-3-5-sonnet | Fast | Excellent | $$ | Balanced |
| claude-3-opus | Medium | Best | $$$$ | Complex reasoning |
| claude-3-haiku | Very Fast | Good | $ | Quick tasks |

## Troubleshooting

### Ollama Issues

**Error: "Ollama not running on localhost:11434"**
```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Start Ollama if not running
ollama serve
```

**Error: "model not found"**
```bash
# Pull the model
ollama pull qwen3:latest
```

### Claude Issues

**Error: "ANTHROPIC_API_KEY not set"**
1. Check your `.env` file exists
2. Verify the API key is correct
3. Restart the Streamlit app

**Error: "langchain-anthropic not installed"**
```bash
pip install langchain-anthropic
```

**Error: "Invalid API key"**
1. Go to https://console.anthropic.com/
2. Regenerate your API key
3. Update your `.env` file

## Technical Details

### Files Modified
1. `agent/vrp_agent.py` - Added multi-provider support
2. `streamlit-app/pages/02_🤖_AI_Agent.py` - Added UI selector

### How It Works
1. User selects provider/model in sidebar
2. Selection stored in `st.session_state`
3. `run_agent()` receives provider/model parameters
4. `get_vrp_agent_graph()` initializes appropriate LLM
5. Cache cleared when provider changes
6. Agent uses selected model for all operations

### Cache Management
The system automatically clears the LLM cache when you switch providers to ensure the new model is properly loaded.

## Cost Considerations

### Ollama
- **Cost**: Free (uses your own hardware)
- **Privacy**: All data stays local
- **Speed**: Depends on your hardware

### Claude API
- **Cost**: Pay per token (check Anthropic pricing)
- **Privacy**: Data sent to Anthropic servers
- **Speed**: Generally fast, depends on API load

**Estimated Cost per Session** (approximate):
- Simple query: ~$0.01-0.05
- Complex multi-tool workflow: ~$0.10-0.50
- Heavy usage session: ~$1-5

## Best Practices

1. **Use Ollama for development** - Free, fast iterations
2. **Use Claude for complex tasks** - Better reasoning, more reliable tool use
3. **Switch based on task complexity**:
   - Simple waypoint updates → Ollama
   - Multi-step optimizations → Claude
4. **Monitor API usage** - Check Anthropic console for usage stats
5. **Keep API key secure** - Never commit `.env` to git

## Future Enhancements

Potential improvements:
- [ ] Add GPT-4 support
- [ ] Model auto-selection based on task complexity
- [ ] Cost tracking and alerts
- [ ] Hybrid mode (use both for different tasks)
- [ ] Response time comparison
- [ ] Model performance analytics

## Support

If you encounter issues:
1. Check this guide's troubleshooting section
2. Verify your setup matches requirements
3. Check console logs for detailed errors
4. Ensure all dependencies are installed
