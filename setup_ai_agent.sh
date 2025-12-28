#!/bin/bash

# AI Agent Setup Script for Multi-Vehicle-Routing

echo "🤖 Setting up AI Agent for Multi-Vehicle-Routing..."

# Check if Ollama is installed
if ! command -v ollama &> /dev/null; then
    echo "❌ Ollama not found. Please install Ollama first:"
    echo "   macOS: brew install ollama"
    echo "   Linux: curl -fsSL https://ollama.ai/install.sh | sh"
    exit 1
fi

echo "✅ Ollama found"

# Start Ollama service (if not running)
echo "🚀 Starting Ollama service..."
ollama serve &
OLLAMA_PID=$!
sleep 3

# Pull the required model
echo "📥 Pulling llama3.1:8b-instruct-q6_K model..."
ollama pull llama3.1:8b-instruct-q6_K

if [ $? -eq 0 ]; then
    echo "✅ Model downloaded successfully"
else
    echo "❌ Failed to download model"
    exit 1
fi

# Install Python dependencies
echo "📦 Installing Python dependencies..."
cd streamlit-app
pip install strands-agents strands-agents-tools

if [ $? -eq 0 ]; then
    echo "✅ Python dependencies installed successfully"
else
    echo "❌ Failed to install Python dependencies"
    exit 1
fi

echo ""
echo "🎉 AI Agent setup complete!"
echo ""
echo "To use the AI Agent:"
echo "1. Start the FastAPI backend: cd backend && uvicorn main:app --reload"
echo "2. Start the Streamlit app: cd streamlit-app && streamlit run app.py"
echo "3. Run optimization in the Solver page"
echo "4. Click 'Launch AI Agent' to start chatting"
echo ""
echo "Example commands for the AI Agent:"
echo "- 'Move customer_1 to latitude 40.7589, longitude -73.9851'"
echo "- 'Move customer_1 to 40.7589, -73.9851 and customer_2 to 40.7282, -74.0776'"
echo "- 'Show me the current route summary'"
echo "- 'Compare the original and current solutions'"