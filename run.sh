#!/bin/bash
# Quick start script for Catalog Image Processing Pipeline

echo "🚀 Starting Catalog Image Processing Pipeline..."

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3.11 -m venv venv
fi

# Activate virtual environment
echo "🔌 Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "📥 Installing dependencies..."
pip install -r requirements.txt

# Create database tables
echo "🗄️  Creating database tables..."
python src/cli_create_tables.py

# Create storage directory
echo "📁 Creating storage directory..."
mkdir -p storage

# Start server
echo "✅ Starting server on http://localhost:8000"
echo "📖 API docs available at http://localhost:8000/docs"
echo ""
uvicorn src.app:app --reload --host 0.0.0.0 --port 8000

