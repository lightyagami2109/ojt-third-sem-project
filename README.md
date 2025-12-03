# Catalog Image Processing Pipeline (Async)

A Vercel-compatible serverless image processing pipeline with idempotency, perceptual hashing, and inline rendition generation.

## Features

- **Idempotency**: Content-hash (SHA256) based deduplication - same image returns existing asset
- **Perceptual Hashing**: aHash-based near-duplicate detection with configurable hamming distance threshold
- **Inline Rendition Generation**: Generates thumb, card, and zoom presets inline (no external workers)
- **Storage Adapter**: S3-style interface with local filesystem implementation (easily swappable for S3)
- **Safe Purge**: Dry-run support and confirmation token for destructive operations
- **Multi-tenant**: Tenant-based asset organization

## Project Structure

```
.
├── api/
│   └── index.py              # Vercel serverless entry point
├── src/
│   ├── app.py                # FastAPI application
│   ├── settings.py            # Configuration (Pydantic BaseSettings)
│   ├── db.py                  # Database connection and session
│   ├── models.py              # SQLAlchemy async models
│   ├── schemas.py             # Pydantic request/response schemas
│   ├── storage.py             # Storage adapter interface + local implementation
│   ├── image_utils.py         # Image processing utilities
│   ├── endpoints.py           # API route handlers
│   └── cli_create_tables.py   # Script to create database tables
├── tests/
│   ├── fixtures/
│   │   ├── sample.jpg         # Test image (generated if missing)
│   │   └── generate_sample.py # Script to generate test image
│   └── test_upload_idempotency.py  # Pytest tests
├── requirements.txt           # Python dependencies
├── vercel.json                # Vercel configuration
└── README.md                  # This file
```

## API Endpoints

### `POST /v1/images`
Upload an image and generate renditions.

**Request:**
- `multipart/form-data`:
  - `tenant` (string): Tenant name
  - `file` (file): Image file (max 10MB)

**Response:**
```json
{
  "id": 1,
  "tenant_id": 1,
  "content_hash": "abc123...",
  "original_filename": "image.jpg",
  "original_size_bytes": 12345,
  "original_width": 1920,
  "original_height": 1080,
  "in_use_count": 0,
  "renditions": [
    {
      "id": 1,
      "preset": "thumb",
      "url": "renditions/abc123/thumb.jpg",
      "size_bytes": 5432,
      "width": 200,
      "height": 200,
      "quality": 85
    },
    ...
  ]
}
```

### `GET /v1/images/{asset_id}`
Get asset by ID with renditions.

### `POST /v1/compare`
Compare image against presets and return metrics.

**Request:**
- `multipart/form-data`:
  - `file` (file): Image file

**Response:**
```json
{
  "results": [
    {
      "preset": "thumb",
      "size_bytes": 5432,
      "width": 200,
      "height": 200,
      "quality_metric": 0.1358
    },
    ...
  ],
  "recommended": "zoom"
}
```

### `POST /v1/purge`
Purge unused assets (in_use_count == 0).

**Request:**
```json
{
  "dry_run": true,
  "confirm_token": "DELETE_CONFIRMED"  // Required if dry_run=false
}
```

**Response:**
```json
{
  "dry_run": true,
  "candidates": ["abc123...", "def456..."],
  "deleted_count": 0
}
```

### `GET /v1/metrics`
Get usage metrics.

**Response:**
```json
{
  "tenant_counts": {
    "tenant1": 10,
    "tenant2": 5
  },
  "bytes_per_preset": {
    "thumb": 543200,
    "card": 1234000,
    "zoom": 5678000
  }
}
```

## Local Development

### Prerequisites
- Python 3.11+
- Virtual environment (recommended)

### Setup

1. **Create virtual environment:**
```bash
python3.11 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. **Install dependencies:**
```bash
pip install -r requirements.txt
```

3. **Create database tables:**
```bash
python src/cli_create_tables.py
```

4. **Run development server:**
```bash
uvicorn src.app:app --reload --host 0.0.0.0 --port 8000
```

5. **Run tests:**
```bash
pytest tests/ -v
```

The API will be available at `http://localhost:8000`

## Vercel Deployment

1. **Install Vercel CLI:**
```bash
npm i -g vercel
```

2. **Deploy:**
```bash
vercel
```

3. **Set environment variables (if needed):**
```bash
vercel env add DATABASE_URL
vercel env add STORAGE_TYPE
# etc.
```

## Configuration

Configuration is managed via `src/settings.py` using Pydantic BaseSettings. You can override settings via environment variables or a `.env` file.

**Key settings:**
- `DATABASE_URL`: Database connection string (default: SQLite)
- `STORAGE_TYPE`: Storage adapter type (`local` or `s3`)
- `STORAGE_BASE_PATH`: Local storage base path
- `MAX_UPLOAD_BYTES`: Maximum upload size (default: 10MB)
- `PRESETS`: Image preset configurations
- `PHASH_HAMMING_THRESHOLD`: Perceptual hash similarity threshold
- `PURGE_CONFIRM_TOKEN`: Token required for purge operations

## Production Considerations

The code includes comments marking areas where production changes are recommended:

1. **Storage**: Implement S3 adapter in `src/storage.py` for production
2. **Background Workers**: Move rendition generation to external worker (Render/Railway) for heavy workloads
3. **Retry/Backoff**: Add retry logic for storage operations and external API calls
4. **Security**: Use secure token generation for `PURGE_CONFIRM_TOKEN`
5. **Database**: Use PostgreSQL or other production database instead of SQLite
6. **CORS**: Configure allowed origins in `src/app.py` CORS middleware

## Testing

Tests cover:
- Idempotency: Same file upload returns existing asset
- Perceptual hash reuse: Near-duplicate images reuse renditions
- Purge: Dry-run and confirmation token validation
- Rendition generation: All presets are generated correctly
- Compare endpoint: Returns metrics for all presets

## Notes

- **No Docker**: This project is designed for Vercel serverless deployment
- **Inline Renditions**: Rendition generation happens inline in the upload request. For production with heavy workloads, move to an external worker.
- **Local Storage**: Default storage adapter uses local filesystem. For production, implement S3 adapter.

---

**This repo is Vercel-ready: no Docker; serverless inline renditions; for heavy workloads move renditions to an external worker (Render/Railway).**

