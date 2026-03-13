# C9 Analytics API

Backend for **C9 Analytics**, an esports analytics suite for Cloud9 covering **League of Legends** and **VALORANT**. It is a single FastAPI service that powers three tools:

| Module | What it does |
| --- | --- |
| **Assistant Coach** | Player and team insights, form trends, player/team comparison, match timelines, macro review, what-if scenario prediction |
| **Scouting Report** | Opponent reports, threat rankings, map stats, counter-strategies, an "ask the coach" chat |
| **Draft Assistant** | Draft board with live recommendations, win-probability, draft simulation, meta champions, draft history |

Frontend: [C9-Analytics-UI](https://github.com/AvishKaushik/C9-Analytics-UI)

## Data source

The project was built for a hackathon on top of the [GRID](https://grid.gg) esports data API. That access has since expired, so the API now serves **built-in sample data** by default.

- Sample data lives in `shared/grid_client/fallback.py`. It generates 14 teams per game (including Cloud9), rosters, best-of-3 series, per-game stats, picks, maps and sides.
- It is **synthetic**. Team names are real organisations, but players, results and stats are invented. Data is deterministic, so the same request always returns the same result.
- The GRID client is still in the code. Set `GRID_MODE=live` with a valid `GRID_API_KEY` to try the real API first (it falls back to sample data if the key is rejected).
- `GET /health` reports which source is active: `"data_source": "sample"` or `"live"`.

## Quick start

Requires Python 3.10+.

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env               # optional, see below
uvicorn app.main:app --reload --port 8000
```

Open http://localhost:8000/docs for the interactive API docs.

## Configuration

All settings are environment variables (a local `.env` file is loaded automatically; it is git-ignored).

| Variable | Default | Purpose |
| --- | --- | --- |
| `GRID_MODE` | `sample` | `sample` = built-in data only. `live` = try GRID first |
| `GRID_API_KEY` | – | Only used when `GRID_MODE=live` |
| `GRID_FALLBACK` | `true` | In live mode, fall back to sample data on auth errors |
| `GROQ_API_KEY` | – | Enables AI-written text (coach chat, what-if, reviews). Free key at console.groq.com |
| `LLM_PROVIDER` | `groq` | `groq`, `anthropic` or `ollama` |
| `ANTHROPIC_API_KEY` | – | Needed only if `LLM_PROVIDER=anthropic` |
| `CORS_ORIGINS` | `*` | Comma-separated allowed origins |

Everything except the AI-written text works without any API key.

## API overview

All routes are under `/api/v1`.

| Prefix | Module |
| --- | --- |
| `/insights` | Coach: player/team insights, roster, matches, timelines, comparisons, trends |
| `/macro-review`, `/what-if` | Coach: macro review and scenario prediction |
| `/report` | Scouting: report generation, team search, maps, threats, counter-strategy |
| `/coach/chat` | Scouting: AI coach chat |
| `/draft`, `/recommendations` | Draft: sessions, simulation, history, champion recommendations |

Cloud9's team IDs are `47351` (LoL) and `79` (VALORANT), matching the UI.

## Project structure

```
app/
  main.py            FastAPI app, CORS, routers, /health
  routers/           HTTP endpoints for the three modules
  services/          Analytics logic (pattern detection, counters, synergy, win-rate, ...)
  models/schemas.py  Pydantic request/response models
shared/
  grid_client/       GraphQL client for GRID + sample-data fallback
  utils/llm.py       LLM wrapper (Groq / Anthropic / Ollama)
```

## Deployment (Render)

- **Build command:** `pip install -r requirements.txt`
- **Start command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- **Env vars:** set `GROQ_API_KEY` (optional) and `CORS_ORIGINS` in the Render dashboard. Never commit keys.
- The free tier sleeps when idle, so the first request can take 30–60 seconds.

## Tech stack

FastAPI, Pydantic v2, httpx, gql, Groq / Anthropic SDKs, Uvicorn.
