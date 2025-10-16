#!/bin/bash

# Launch script for QueenAI Chat UI
# This script starts the Streamlit application with proper configuration

echo "🚀 Launching QueenAI Chat UI..."
echo ""

# Check if virtual environment is activated
if [[ -z "$VIRTUAL_ENV" ]]; then
    echo "⚠️  Warning: Virtual environment not activated"
    echo "   Consider running: source venv/bin/activate"
    echo ""
fi

# Check if Streamlit is installed
if ! command -v streamlit &> /dev/null; then
    echo "❌ Error: Streamlit is not installed"
    echo "   Run: pip install streamlit"
    exit 1
fi

# Check if .env file exists
if [ ! -f .env ]; then
    echo "⚠️  Warning: .env file not found"
    echo "   Create .env with AWS credentials"
    echo ""
fi

# Check AWS credentials
if ! aws sts get-caller-identity &> /dev/null; then
    echo "⚠️  Warning: AWS credentials not configured"
    echo "   Run: aws configure"
    echo ""
fi

echo "✅ Starting Streamlit application..."
echo ""
echo "The app will open in your browser at http://localhost:8501"
echo "Press Ctrl+C to stop the server"
echo ""

# Determine the correct path to app.py
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
APP_PATH="$SCRIPT_DIR/app.py"

# Start Streamlit
streamlit run "$APP_PATH" \
    --server.port 8501 \
    --server.headless false \
    --browser.gatherUsageStats false \
    --theme.base light \
    --theme.primaryColor "#1f77b4"
