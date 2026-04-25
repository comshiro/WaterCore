# WaterCore - weilding Copernicus

Scaffolding for a hackathon MVP focused on disaster risk monitoring for insurers using Copernicus and Galileo/EGNOS aligned workflows.

## Project Layout

- backend: FastAPI service with risk scoring endpoints
- frontend: lightweight static dashboard for demo
- data: sample inputs used for offline demos

## Quick Start

1. Create and activate a virtual environment.
2. Install dependencies from dependencies.txt.
3. Run the API server.
4. Open frontend/index.html in a browser.

## Backend Commands

```bash
pip install -r dependencies.txt
uvicorn backend.app.main:app --reload --port 8000
pytest backend/tests -q
```

## API Endpoints

- GET /api/v1/health
- POST /api/v1/risk/score
- GET /api/v1/risk/demo
- POST /api/v1/risk/scenes
- POST /api/v1/risk/derived-layer

### Scene Discovery Request Example

```json
{
	"collection": "sentinel-1-grd",
	"bbox": [20.9, 45.6, 21.4, 45.9],
	"start_datetime": "2026-03-01T00:00:00Z",
	"end_datetime": "2026-03-10T00:00:00Z",
	"limit": 10,
	"cloud_cover_lte": 30
}
```

Notes:
- Catalog search on Copernicus STAC is typically available without an API key.
- Keep `COPERNICUS_STAC_TOKEN` empty unless your environment or gateway requires authenticated requests.

### Derived Layer Request Example (Sentinel Hub)

```json
{
	"layer_type": "ndwi",
	"data_collection": "sentinel-2-l2a",
	"bbox": [20.9, 45.6, 21.4, 45.9],
	"start_datetime": "2026-03-01T00:00:00Z",
	"end_datetime": "2026-03-10T00:00:00Z",
	"width": 256,
	"height": 256,
	"output_mime": "image/png"
}
```

Notes:
- Sentinel Hub processing requires OAuth client credentials.
- Set `SENTINEL_HUB_CLIENT_ID` and `SENTINEL_HUB_CLIENT_SECRET` before using this endpoint.

## Environment

Copy .env.example to .env and adjust values as needed.
