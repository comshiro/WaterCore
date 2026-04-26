# WaterCore - weilding Copernicus

WaterCore is a next-generation platform for insurance companies to transition from "Reactive" to "Proactive" disaster management. By leveraging Copernicus Sentinel data and Predictive AI, we provide hyper-local flood risk assessments for fair premium pricing and automated parametric insurance payouts.

## The Problem
Traditional flood insurance relies on outdated, coarse-grained maps. This leads to Unfair Pricing (neighbors in a low-risk house pay as much as those in a high-risk basin) and Delayed Payouts (claims taking months to verify via manual inspections).

## Core Features
1. AI Risk Profiler (Predictive ML)
Using a Random Forest Classifier trained on historical Copernicus data, we generate a 10m-resolution Flood Susceptibility Heatmap.

Inputs: Copernicus GLO-30 DEM (Elevation/Slope), ESA WorldCover (Land Use), and Historical NDWI Frequency.

Output: A personalized risk score that allows insurers to offer Fair, Data-Driven Premiums.

2. Parametric Claims Engine
An automated "Truth Witness" that monitors Sentinel-1 (Radar) feeds in real-time.

Logic: When a flood is detected via satellite images, the system intersects the flood mask with Galileo-verified property coordinates.

Result: Instant Payouts triggered as soon as the satellite passes over, removing the need for manual adjusters.

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
- POST /api/v1/flood/detect
- POST /api/v1/flood/track-area
- GET /api/v1/flood/tracked-areas
- POST /api/v1/flood/check-areas
- POST /api/v1/flood/simulate-alert
- DELETE /api/v1/flood/tracked-area/{area_id}
- POST /api/v1/risk/score
- GET /api/v1/risk/demo
- POST /api/v1/risk/scenes
- POST /api/v1/risk/derived-layer
- POST /api/v1/risk/climate-baseline

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
