# Industrial Knowledge Brain

**ET AI Hackathon 2026 — Problem Statement 8: AI for Industrial Knowledge Intelligence**
Team rajsahay1721

An AI-powered knowledge graph platform that ingests heterogeneous industrial documents — maintenance worklogs, P&ID drawings, inspection reports, and safety procedures — and connects entities across them, even when the same physical asset is named differently in each document.

**Core proof point:** `TANK-01` is automatically linked across three separate source documents (a maintenance worklog, a facility P&ID, and a compressor inspection report) into one traversable graph — verified end-to-end.

---

## Architecture

```
Ingestion Layer          Type-aware parsers (PDF / CSV / OCR / field-block)
      ↓
Entity Extraction        Hermes LLM (via OpenRouter)
      ↓
Entity Resolution        Deterministic blocking + fuzzy matching + LLM validation
      ↓
Knowledge Graph          Neo4j — cross-document entities resolved to single nodes
      ↓
Retrieval Layer          Schema-conditioned graph traversal + vector/keyword fallback
      ↓
API Layer                FastAPI — REST endpoints for frontend consumption
```

See `Industrial_Knowledge_Brain_Build_Guide.pdf` for full technical detail.

---

## Project Structure

```
industrial-knowledge-brain/
├── ingestion/              # Parsers, entity extraction, entity resolution
│   ├── config.py           # Tesseract/Poppler paths (Windows)
│   ├── schemas.py          # Pydantic data models
│   ├── pdf_parser.py
│   ├── table_parser.py
│   ├── ocr_parser.py
│   ├── drawing_parser.py
│   ├── inspection_parser.py
│   ├── entity_extractor.py
│   ├── entity_resolution.py
│   └── run_pipeline.py
├── graph/
│   └── load_to_neo4j.py    # Loads extracted entities into Neo4j
├── retrieval/
│   ├── graph_schema.py     # Valid entity/relationship schema
│   ├── schema_planner.py   # LLM proposes traversal plan, code validates it
│   ├── schema_executor.py  # Executes validated plan as Cypher
│   └── router.py           # Routes queries: graph / vector / keyword
├── sample_docs/            # Source documents + extracted entity JSON
├── main.py                 # FastAPI application (API layer)
├── db_config.py            # Neo4j credentials, loaded from .env
├── verify_tank01_query.py  # Verification script for the core demo proof
├── build_fallback_cache.py # Generates offline demo fallback data
└── requirements.txt
```

---

## Setup

### 1. Prerequisites
- Python 3.11+ (tested on 3.14)
- [Neo4j Desktop](https://neo4j.com/download/) (or Neo4j via Docker)
- [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki) (Windows build)
- [Poppler for Windows](https://github.com/oschwartz10612/poppler-windows/releases)
- An [OpenRouter](https://openrouter.ai/) API key with credit

### 2. Clone and create a virtual environment
```bash
git clone https://github.com/yourusername/industrial-knowledge-brain.git
cd industrial-knowledge-brain
python -m venv venv
venv\Scripts\Activate.ps1        # Windows PowerShell
# source venv/bin/activate       # macOS/Linux
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure environment variables
Create a `.env` file in the project root (never commit this file):
```
OPENROUTER_API_KEY=your_openrouter_key
NEO4J_URI=neo4j://127.0.0.1:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_neo4j_password
```

### 5. Configure Tesseract/Poppler paths (Windows only)
Edit `ingestion/config.py` and set `TESSERACT_CMD_PATH` and `POPPLER_PATH` to match your install locations.

### 6. Start Neo4j
Open Neo4j Desktop, start your local DBMS, confirm it's reachable at `http://localhost:7474`.

---

## Running the Pipeline

**1. Run ingestion + entity extraction:**
```bash
python ingestion/run_pipeline.py
```

**2. Load extracted entities into Neo4j:**
```bash
python graph/load_to_neo4j.py
```

**3. Verify the core cross-document proof:**
```bash
python verify_tank01_query.py
```
Expected: a path from `TANK-01` to `SN-2053474` crossing multiple source documents.

**4. Build the offline demo fallback (safety net for live demos):**
```bash
python build_fallback_cache.py
```

**5. Start the API server:**
```bash
python -m uvicorn main:app --reload --port 8000
```
API docs available at `http://localhost:8000/docs`.

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Backend + Neo4j connectivity check |
| GET | `/entity/{value}/neighborhood` | Direct connections of an entity, e.g. `/entity/TANK-01/neighborhood` |
| GET | `/entity/{from}/path-to/{to}` | Cross-document path between two entities |
| GET | `/graph/snapshot` | Bounded graph snapshot for visualization |
| POST | `/query` | Natural-language question, routed through schema-conditioned retrieval |
| GET | `/demo/fallback` | Pre-cached proof data for offline demo mode |

---

## Demo Questions

1. *"What maintenance was performed on TANK-01, and how does it relate to the compressor inspection findings?"*
2. *"What instrumentation is associated with TANK-01 according to the facility P&ID?"*

Both are verified working against the live knowledge graph, crossing worklog → P&ID and worklog → inspection report documents respectively.

---

## Documents Used

- OISD-STANDARD-144 (LPG Installations) — safety procedure
- Maintenance worklog (CSV, 41 records)
- Facility P&ID drawing
- Mycom 200SUD-HE compressor inspection report (2 units)

---

## What's Built vs. Planned

**Built and verified:**
- Multi-format ingestion (PDF, CSV, drawing OCR, field-block PDF)
- LLM-based entity extraction with error handling and fail-safe defaults
- Hybrid entity resolution (blocking + fuzzy matching + LLM-in-the-loop validation, with a trailing-identifier safety guard)
- Neo4j knowledge graph with cross-document entity resolution
- Schema-conditioned graph traversal (LLM proposes a plan, code validates every hop against the schema before execution)
- REST API layer

**Planned / not yet implemented:**
- Vector search (Qdrant/pgvector) — currently a stub in `router.py`
- Full answer-generation layer with inline citations
- Verification/repair pass against hard graph constraints

---

## License

Built for ET AI Hackathon 2026. Not licensed for external use without permission from Team rajsahay1721.
