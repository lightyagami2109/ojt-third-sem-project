# Quick Start Guide

## Option 1: Using the Run Script (Easiest)

```bash
./run.sh
```

This script will:
- Create a virtual environment (if needed)
- Install all dependencies
- Create database tables
- Start the server

## Option 2: Manual Setup

### Step 1: Create Virtual Environment
```bash
python3.11 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### Step 2: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 3: Create Database Tables
```bash
python src/cli_create_tables.py
```

### Step 4: Create Storage Directory
```bash
mkdir -p storage
```

### Step 5: Start the Server
```bash
uvicorn src.app:app --reload --host 0.0.0.0 --port 8000
```

## Access the API

Once running, you can access:

- **API Server**: http://localhost:8000
- **Interactive API Docs**: http://localhost:8000/docs
- **Alternative Docs**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/health

## Test the API

### Upload an Image
```bash
curl -X POST "http://localhost:8000/v1/images" \
  -F "tenant=test_tenant" \
  -F "file=@/path/to/your/image.jpg"
```

### Get Asset by ID
```bash
curl "http://localhost:8000/v1/images/1"
```

### Compare Image
```bash
curl -X POST "http://localhost:8000/v1/compare" \
  -F "file=@/path/to/your/image.jpg"
```

### Get Metrics
```bash
curl "http://localhost:8000/v1/metrics"
```

### Purge (Dry Run)
```bash
curl -X POST "http://localhost:8000/v1/purge" \
  -H "Content-Type: application/json" \
  -d '{"dry_run": true}'
```

## Run Tests

```bash
pytest tests/ -v
```

## Stop the Server

Press `Ctrl+C` in the terminal where the server is running.

