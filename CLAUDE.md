# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Industrial/Civil 3D Model Interoperability Platform that converts between CAD formats (STEP ↔ GLTF ↔ IFC), stores semantic data in a Virtuoso RDF triple store, and provides a web UI for browsing/editing 3D assembly hierarchies.

## Commands

### Frontend (React + TypeScript + Vite)
```bash
cd frontend
npm install
npm run dev          # Dev server at http://localhost:3000
npm run build        # Production build
npm run preview      # Preview built bundle
npm run generate:ifc-schema  # Regenerate IFC schema from web-ifc
```

### Backend (Python + FastAPI)
```bash
cd backend
pip install -r requirements.txt
python run.py        # Starts uvicorn at http://localhost:8000
```

### Infrastructure
```bash
docker-compose up    # Start Virtuoso RDF database (ports 8890 SPARQL, 1111 isql)
```

### Development Setup
The frontend Vite dev server proxies `/api/*` → `http://localhost:8000`. Running order: Virtuoso → backend → frontend.

External tools required on the host (paths hardcoded in `backend/api/models/models.py`):
- **Mayo** at `C:\Program Files\Fougue\Mayo\mayo-conv.exe` — STEP → GLTF conversion
- **Blender 5.0** at `C:\Program Files\Blender Foundation\Blender 5.0\blender.exe` — IFC generation

## Architecture

### Data Flow
1. User uploads STEP file → stored in `tmp/STEP/`
2. Mayo CLI converts STEP → GLTF → stored in `tmp/gLTF/` and `tmp/GLB/`
3. GLTF hierarchy is parsed and converted to RDF triples (rdflib) → uploaded to Virtuoso
4. User edits assembly hierarchy, adds IFC properties via the web UI
5. WebSocket-driven Blender script generates IFC from GLTF + RDF metadata → `tmp/IFC/`

### Backend (`backend/`)
- **`app.py`** — FastAPI instance; mounts 13 route modules from `api/routes/`
- **`api/models/models.py`** — All constants: executable paths, folder paths, Virtuoso endpoint (`http://localhost:8890/sparql`), RDF namespaces (`https://elettra2.0#`, X3D, IFC, PREMIS, PROV, FOAF)
- **`api/routes/`** — One file per domain: `upload_STEP.py`, `sparql_query.py`, `ifc_conversion.py` (WebSocket), `gltf_upload.py`, `add_child.py`, `add_ifc_prop.py`, `update_STEP.py`, `update_deletion.py`, `update_simplification.py`
- **`api/services/importing_STEP/`** — STEP processing pipeline: `mayo.py` (Mayo wrapper), `gltf.py` (GLTF parsing), `compess_gltf.py` (compression), `RDF_conversion.py` (hierarchy → RDF triples)
- **`api/services/ifc_conversion/`** — `blender.py` orchestrates Blender; `blender_script/` contains the Python scripts Blender executes
- **`api/services/db_requests/`** — Virtuoso SPARQL query helpers: `import_in_DB.py`, `existing_nodes.py`, `updatingSTEP/`, `substitution_file_query.py`

### Frontend (`frontend/src/`)
- **`App.tsx`** — Router and top-level state management; defines all routes
- **`pages/STEPPage/`** — Main CAD interface: `Hierarchy/` (assembly tree with `buildTree.ts` as core data model), `NodeDetails/` (metadata editor), `gLTFViewer/` (3D visualization via ThatOpen)
- **`pages/IFCPage/`** — IFC hierarchy browser (same structure as STEPPage)
- **`pages/IFCViewerPage/`** — 3D IFC viewer using ThatOpen Components
- **`pages/UpdateFilesPage/`** — Replace STEP files while preserving RDF links
- **`pages/InventoryProductPage/`** — Product catalog view
- **`components/Sidebar/`** — Navigation sidebar with messages

### Key Architecture Points
- All file paths and executable locations are centralized in `backend/api/models/models.py` — change here first when moving files or environments
- RDF graph namespace is `https://elettra2.0#`; SPARQL queries use this throughout
- IFC conversion uses a WebSocket (`WS /api/ws/blender_run_scripts`) for long-running Blender jobs
- `tmp/` directory holds all runtime files (STEP, GLTF, GLB, RDF, IFC, JSON) — gitignored except `.gitkeep` files
- ThatOpen Components (`@thatopen/components`, `@thatopen/ui`) handle all 3D rendering; `web-ifc` handles IFC parsing

### Key API Endpoints
| Endpoint | Purpose |
|---|---|
| `POST /api/upload-step` | Upload and process STEP file |
| `POST /api/sparql-query` | Execute SPARQL against Virtuoso |
| `POST /api/convert` | Trigger Mayo STEP→GLTF conversion |
| `WS /api/ws/blender_run_scripts` | IFC generation (WebSocket) |
| `POST /api/add-child` | Add child node to hierarchy |
| `POST /api/update-step` | Update STEP node data |
| `POST /api/gltf-upload` | Upload GLTF directly |
