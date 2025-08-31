# Project Setup Guide

This repo contains:
- **backend**: FastAPI service (ports `8000`) with solvers, distance-matrix adapters, OSM utilities, and dataset loaders.
- **frontend**: Next.js (ports `3000`) Map UI with VRP tools.

## 1) Prerequisites

- **Python** 3.10–3.12
- **Node.js** ≥ 18 (LTS recommended)
- **git**, **curl**
- (Optional) API keys if you plan to call commercial adapters:
  - `OPENROUTESERVICE_API_KEY`
  - `MAPBOX_TOKEN` (for Mapbox adapter; MapLibre tiles work without)
  - `GOOGLE_API_KEY` (if you enable Google adapters)
- Internet access for Overpass/Nominatim when using OSM search.

## 2) Clone

```bash
git clone <your-repo-url> vrp-lab
cd vrp-lab
```

## 3) Backend

Create a virtualenv and install deps:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate           # Windows: .venv\Scripts\activate
pip install -U pip
pip install -r requirements.txt
```

Environment (create `.env` in `backend/`):

```env
# CORS (allow the frontend)
CORS_ORIGINS=http://localhost:3000

# Optional API keys for online adapters
OPENROUTESERVICE_API_KEY=
MAPBOX_TOKEN=
GOOGLE_API_KEY=

# Overpass throttling (defaults are safe)
OVERPASS_RATE_LIMIT_SLEEP=1.0
OVERPASS_TIMEOUT=120
```

Run:

```bash
uvicorn main:app --reload --port 8000
# Swagger: http://localhost:8000/docs
# Health:  http://localhost:8000/health
```

Quick checks:

```bash
curl -s http://localhost:8000/status
curl -s "http://localhost:8000/benchmarks/files?dataset=solomon&limit=5"
```

## 4) Frontend

```bash
cd ../frontend
npm i
# optionally set the backend URL; defaults to http://localhost:8000
echo 'NEXT_PUBLIC_BACKEND_URL=http://localhost:8000' > .env.local
# optional Mapbox token if you use the mapbox page:
echo 'NEXT_PUBLIC_MAPBOX_TOKEN=' >> .env.local

npm run dev
# http://localhost:3000/map/maplibre  (primary)
# http://localhost:3000                (landing)
```

## 5) Running tests (backend)

```bash
cd backend
pytest -q
```

## 6) Common trouble

- **CORS errors**: ensure `CORS_ORIGINS` includes `http://localhost:3000`, restart backend.
- **Overpass 400/429**: reduce query **limit**, prefer **bbox** mode, or increase `OVERPASS_RATE_LIMIT_SLEEP`.
- **“Field required: origins/destinations”**: some adapters need `origins[]` & `destinations[]`; `osm_graph` uses `coordinates[]` instead—see the API section in the User Manual.
