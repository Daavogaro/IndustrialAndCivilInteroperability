# Spec: Docker Full Containerization V2

## Overview
Make the whole platform run with a single command — `docker compose up --build` — with **zero host installs except Docker itself**. Today only Virtuoso runs in Docker; the backend (FastAPI + STEP→GLTF + Blender/Bonsai IFC generation) and the frontend (React/Vite) are expected to run on the host with conda, Node, and a Windows install of Blender 5.0 + the Bonsai add-on. This spec containerizes all three tiers:

- **virtuoso** — RDF triple store (already containerized; fix the broken compose YAML).
- **backend** — FastAPI in a conda-based image that **also bundles Blender 5.0 (Linux) and the Bonsai extension** so IFC generation runs inside the container. Mayo is removed entirely (already superseded by the in-process `pythonocc-core` converter in step 03).
- **frontend** — production build served by nginx, which **reverse-proxies `/api/` (HTTP + WebSocket) to the backend**, so the browser talks to a single origin (`http://localhost:3000`).

It also rewrites `README.md` into dead-simple, baby-steps instructions for first-time start and everyday running. This is the final "everything in Docker" milestone after the converter swap (step 03) and multi-project work (step 04).

## Depends on
- **Step 03 (Change GLTF Converter)** — backend STEP→GLTF must already be `pythonocc-core`/`occ_converter.py` based, with no runtime dependency on `mayo-conv.exe`. This spec assumes Mayo is dead code.
- **Step 04 (Multiple Project)** — per-project `tmp/projects/<id>/...` layout in `models.py`. The compose `tmp/` volume must cover it.

## Routes
No new routes.

The set of HTTP and WebSocket endpoints is unchanged. The only behavioural change is **how the browser reaches them**: all calls become same-origin relative URLs proxied by nginx, instead of some calls hardcoding `http://localhost:8000` / `ws://localhost:8000`.

## Database changes
No database changes.

Operational note only: the Virtuoso `grant SPARQL_UPDATE to "SPARQL"` step should be driven by the `tenforce/virtuoso` image's `SPARQL_UPDATE=true` env var so the user does not have to do it by hand. If the image still requires the manual Conductor step, the README keeps it as a clearly-marked one-time step.

## Templates
This project has no server-side templates (React SPA). Frontend component changes instead:

- **Create:**
  - `frontend/nginx.conf` — nginx server config: serves the SPA with history-fallback and reverse-proxies `/api/` (incl. WebSocket upgrade) to `http://backend:8000`.
- **Modify:**
  - `frontend/src/pages/STEPPage/UploadSTEPModal.tsx` — WebSocket URL `ws://localhost:8000/api/ws/convert` → same-origin relative.
  - `frontend/src/pages/UpdateFilesPage/UpdateSTEPModal.tsx` — `ws://localhost:8000/api/ws/update` → same-origin relative.
  - `frontend/src/pages/IFCPage/NodeDetails/DownloadIFCButton.tsx` — `ws://localhost:8000/api/ws/blender_run_scripts` → same-origin relative.
  - `frontend/src/utils/fetchQuery.ts` — `http://localhost:8000/api/sparql-query` → relative `/api/sparql-query`.

## Files to change
- `docker-compose.yml` — rewrite: fix the malformed `virtuoso` env block (lines 31–33 are nested wrong), un-comment + correct `backend` and `frontend` services, add the shared `tmp` bind/volume, wire service-name networking (`DB_HOST=virtuoso`, frontend proxies to `backend`), add healthcheck/`depends_on` ordering.
- `backend/Dockerfile` — replace the `python:3.11-slim` + `pip install` image with a **conda-based image** (e.g. `continuumio/miniconda3`) that: installs the conda-forge deps incl. `pythonocc-core`; downloads & installs **Blender 5.0 Linux**; installs & enables the **Bonsai extension** from the bundled zip; sets `BLENDER_EXE`/`DB_HOST`; runs uvicorn **without** `--reload`. (See "Rules for implementation".)
- `backend/api/models/models.py` —
  - Make `BLENDER_EXE` env-driven: `BLENDER_EXE = os.getenv("BLENDER_EXE", "blender")` (default resolves on `PATH` in the container; Windows users override).
  - Remove `MAYO_EXE`, `MAYO_SERVICE_URL`, and `INI_FILE` (Mayo is gone).
  - Add absolute, OS-independent Blender script path constants (see below) so the IFC pipeline does not depend on the process working directory or Windows backslashes.
- `backend/api/routes/ifc_conversion.py` — replace the Windows-backslash relative constants `IMPORT_GLTF_SCRIPT`, `CONVERT_IFC_SCRIPT`, and `GLTF_PATH` with absolute paths built from `BASE_DIR` (import them from `models.py`). No logic change.
- `backend/api/services/ifc_conversion/blender.py` — no functional change required (it already reads `BLENDER_EXE` and `os.path.abspath`s the script); confirm it works once `BLENDER_EXE` is env-driven and script paths are absolute.
- `backend/app.py` — remove the Mayo wiring: delete `from api.routes import mayo_and_gltf` **only if** that module is itself Mayo-bound (verify against step 03 — if `mayo_and_gltf.py` now uses `occ_converter`, keep it); delete `from api.services.importing_STEP import mayo` (line 15) and `app.include_router(mayo.router, prefix="/api")` (line 44). Do not remove any non-Mayo router.
- `backend/requirements.txt` — keep as the canonical dependency list; the Dockerfile installs `pythonocc-core` and `ifcopenshell` via conda (they are not reliably pip-installable) and the rest via pip or conda. Leave the file readable; the Dockerfile decides the install mechanism.
- `frontend/Dockerfile` — keep the multi-stage layout but make the **default/built target** `production` (nginx) and `COPY` the new `nginx.conf` into the nginx image. Keep the `development` stage available.
- `frontend/vite.config.ts` — make the dev proxy target configurable via env (`process.env.VITE_API_TARGET ?? "http://localhost:8000"`) so local `npm run dev` still works and a containerized dev variant could point at `backend:8000`. (Production path uses nginx, not this proxy.)
- `README.md` — full rewrite of install/run sections into baby-step Docker-only instructions (see "Rules for implementation").
- `.gitignore` — add `backend/bonsai/*.zip` (the 139 MB Bonsai extension must not be committed) while keeping the folder tracked (e.g. add a `backend/bonsai/.gitkeep`).

## Files to create
- `frontend/nginx.conf` — see Templates.
- `backend/.dockerignore` — exclude `__pycache__`, `db/`, `tmp/`, `*.blend`, local venvs; **must NOT exclude** `bonsai/` (the build needs the zip).
- `frontend/.dockerignore` — exclude `node_modules`, `dist`, `.vite`.
- `backend/bonsai/.gitkeep` — keep the folder in git without the large zip.

## New dependencies
No new **Python** packages beyond what `requirements.txt` already lists. New **system/build** dependencies are introduced in the backend image only:
- **Blender 5.0 (Linux x64)** — downloaded in the Dockerfile from the official Blender release archive and extracted to `/opt/blender`, symlinked onto `PATH` as `blender`.
- **Bonsai extension `add-on-bonsai-v0.8.4-linux-x64.zip`** — supplied by the user at `backend/bonsai/add-on-bonsai-v0.8.4-linux-x64.zip`; installed into Blender at build time. (Gitignored; must be present in the build context.)
- conda-forge packages (incl. `pythonocc-core`, `ifcopenshell`) installed in the image.

## Rules for implementation

### General
- No SQLAlchemy or ORMs.
- Parameterised queries only (no SPARQL/query logic changes in this spec).
- Do not change any API contract, route path, or WebSocket message protocol — only transport/origin and deployment change.
- Keep local (non-Docker) dev working: env-driven `BLENDER_EXE`, env-driven Vite proxy target, and relative frontend URLs all degrade gracefully on the host.

### backend/Dockerfile (Blender + Bonsai + conda)
- Base on a conda image (`continuumio/miniconda3` recommended) because **`pythonocc-core` is distributed on conda-forge, not PyPI** — the current `pip install -r requirements.txt` cannot succeed.
- Install Python deps from `conda-forge`: at minimum `pythonocc-core`, `ifcopenshell`, plus `fastapi uvicorn requests SPARQLWrapper python-multipart pygltflib numpy httpx rdflib` (mirror `requirements.txt`). Pin `python=3.12` to match the README env.
- Install Blender 5.0 Linux:
  - `apt-get install` the minimal runtime libs Blender needs headless (e.g. `libxi6 libxxf86vm1 libxfixes3 libxrender1 libgl1 libsm6 xz-utils wget`).
  - Download `blender-5.0.x-linux-x64.tar.xz`, extract to `/opt/blender`, and `ln -s /opt/blender/blender /usr/local/bin/blender`.
- Install + enable the Bonsai extension headlessly so `import bonsai.tool` works at runtime (the existing `import_gltf.py` imports `bonsai` as a top-level module, exactly as the current Windows setup does):
  - `COPY bonsai/add-on-bonsai-v0.8.4-linux-x64.zip /tmp/bonsai.zip`
  - Install via Blender's extension CLI at build time, e.g.
    `blender --background --command extension install-file --repo user_default --enable /tmp/bonsai.zip`
    (use the exact Blender 5.0 extension-CLI syntax; verify the enable step actually persists to the image's user prefs so a later `blender --python import_gltf.py` can `import bonsai`).
  - Add a build-time smoke check that fails the build if Bonsai is not importable, e.g. run a tiny headless script: `blender --background --python-expr "import bonsai.tool"`.
  - Remove `/tmp/bonsai.zip` after install to keep the layer smaller.
- Set env: `ENV BLENDER_EXE=blender` and `ENV DB_HOST=virtuoso`.
- Container layout: arrange `WORKDIR`/`COPY` so that `models.py`'s `BASE_DIR = Path(__file__).resolve().parents[3]` resolves to the directory **above `backend/`** and `tmp/` lives under it. Concretely, copy the backend tree to `/app/backend` so `BASE_DIR == /app` and runtime files land in `/app/tmp` (the compose volume mounts there).
- `CMD` runs uvicorn on `0.0.0.0:8000` **without `--reload`** (production). Ensure it can import `app:app` given the chosen layout (set `--app-dir` or `WORKDIR` accordingly), while `BASE_DIR` still points at `/app`.

### Blender script paths (must be absolute, cross-platform)
- In `models.py`, add (built from `BASE_DIR`):
  - `BLENDER_SCRIPT_DIR = BASE_DIR / "backend" / "api" / "services" / "ifc_conversion" / "blender_script"`
  - `IMPORT_GLTF_SCRIPT = str(BLENDER_SCRIPT_DIR / "import_gltf.py")`
  - `CONVERT_IFC_SCRIPT = str(BLENDER_SCRIPT_DIR / "ifc_conversion.py")`
- In `ifc_conversion.py`, import those constants instead of the local `r"backend\api\..."` strings, and remove the stale hardcoded `GLTF_PATH` Windows path (replace with a `BASE_DIR`-relative path or delete if unused).
- Rationale: `run_blender_script` does `os.path.abspath(script)`, which is relative to the process CWD and uses `\` — both are wrong on Linux/in-container. Absolute `BASE_DIR` paths fix it on every OS.

### Mayo removal
- Remove `MAYO_EXE`, `MAYO_SERVICE_URL`, `INI_FILE` from `models.py`.
- Remove the `mayo` service-route wiring from `app.py` (`import ... mayo` and `include_router(mayo.router)`).
- Verify `backend/api/services/importing_STEP/mayo.py` is not imported anywhere else before deleting it; deleting it is optional but preferred (dead code). The `mayo-gui.ini` file may also be removed if nothing references it.
- Do **not** touch the STEP→GLTF pipeline that step 03 built around `occ_converter.py`.

### frontend networking (single origin via nginx)
- `nginx.conf` must:
  - serve `/usr/share/nginx/html` with SPA fallback: `try_files $uri $uri/ /index.html;`
  - proxy `location /api/ { proxy_pass http://backend:8000; }` with the standard headers AND WebSocket upgrade support:
    `proxy_http_version 1.1; proxy_set_header Upgrade $http_upgrade; proxy_set_header Connection "upgrade"; proxy_set_header Host $host;`
  - set a generous `client_max_body_size` (STEP uploads can be large, e.g. `512m`) and a long `proxy_read_timeout`/`proxy_send_timeout` (Blender IFC jobs are long-running over WebSocket).
- Frontend code: replace all four hardcoded `localhost:8000` references with **same-origin** URLs:
  - HTTP: relative path, e.g. `fetch("/api/sparql-query", …)`.
  - WebSocket: derive from the page, e.g.
    ```ts
    const proto = window.location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${proto}://${window.location.host}/api/ws/convert`);
    ```
  - These keep working under `npm run dev` (Vite proxies `/api`) and under nginx (which proxies `/api`).
- `app.py` CORS currently allows only `http://localhost:3000`; since the browser now hits the same origin (`:3000`) and the backend is reached only via the nginx proxy, this stays valid. Do not broaden CORS unless a concrete cross-origin need appears.

### docker-compose.yml
- `virtuoso`: image `tenforce/virtuoso`, ports `8890:8890` and `1111:1111`, env `DBA_PASSWORD: ddd` and `SPARQL_UPDATE: "true"`, named volume `virtuoso-data:/data`. Remove the broken nested env lines.
- `backend`: `build: ./backend`, `depends_on: [virtuoso]`, env `DB_HOST=virtuoso` (and `BLENDER_EXE=blender`), bind/volume the host `./tmp` (or a named volume) to the in-container `tmp` path so generated STEP/GLTF/GLB/IFC files persist and are visible. Optionally publish `8000:8000` for direct API debugging.
- `frontend`: `build: { context: ./frontend, target: production }`, `ports: ["3000:80"]`, `depends_on: [backend]`.
- Add a `virtuoso` healthcheck (or `depends_on` with `condition: service_started`) so the backend does not race the DB on first boot.
- Keep one top-level `volumes:` block (`virtuoso-data`, and the tmp volume if named).

### README.md (write it for a complete beginner)
Rewrite so a first-time user needs **only Docker**. Required content, in order, in plain numbered baby steps:
1. **What you need first:** install Docker Desktop (link), start it, verify with `docker --version`.
2. **Get the Bonsai file in place:** explain that `backend/bonsai/add-on-bonsai-v0.8.4-linux-x64.zip` must exist (it is large and not stored in git); tell them exactly where to put it.
3. **First-time start:** open a terminal in the project folder and run `docker compose up --build`. Warn that the first build is slow (Blender + Bonsai download/install) and that's normal.
4. **Open the app:** go to `http://localhost:3000`. That's it — frontend, backend, database, and Blender are all inside Docker.
5. **(If needed) one-time Virtuoso permission:** only if `SPARQL_UPDATE=true` did not auto-grant — show the Conductor login (`dba`/`ddd`) and the `grant SPARQL_UPDATE to "SPARQL"` step, clearly marked "usually not needed".
6. **Everyday running:** `docker compose up` to start, `Ctrl+C` then `docker compose down` to stop; `docker compose up --build` after code changes.
7. **Where files go:** note that uploaded/generated files appear in `tmp/`.
- Remove the now-obsolete host-install sections (Conda, host Node, host Blender, Mayo) or move them to a clearly-labelled "Advanced: run without Docker" appendix. Do not leave Mayo instructions in the primary path.

## Definition of done
- [ ] `docker compose up --build` from a clean checkout (with the Bonsai zip present at `backend/bonsai/add-on-bonsai-v0.8.4-linux-x64.zip`) builds all three images with no errors.
- [ ] The backend image build **fails loudly** if Bonsai is not importable (the `import bonsai.tool` smoke check passes when it succeeds).
- [ ] `docker compose ps` shows `virtuoso`, `backend`, and `frontend` all running.
- [ ] Visiting `http://localhost:3000` loads the SPA with no console errors about `localhost:8000` or CORS.
- [ ] Uploading a STEP file completes the full pipeline over the WebSocket (proxied through nginx) and an assembly tree renders — no Mayo involved.
- [ ] Triggering IFC generation runs Blender **inside the backend container** (using bundled Bonsai) and produces an `.ifc` file visible under `tmp/IFC/`.
- [ ] A SPARQL query from the UI (e.g. the inventory/hierarchy pages) returns data from the `virtuoso` container.
- [ ] No code path references `MAYO_EXE`, `mayo-conv.exe`, `INI_FILE`, or `mayo.router`; `grep -rn "mayo" backend/app.py backend/api/models/models.py` returns nothing.
- [ ] No source file contains a hardcoded `localhost:8000`; `grep -rn "localhost:8000" frontend/src` returns nothing.
- [ ] `models.py` `BLENDER_EXE` is env-driven and the Blender script paths are absolute (no `\` literals); `python backend/run.py` still works on a Windows host with `BLENDER_EXE` set.
- [ ] `backend/.dockerignore` does **not** exclude `bonsai/`; `.gitignore` excludes `backend/bonsai/*.zip`.
- [ ] `README.md` first-time instructions are Docker-only, in numbered baby steps, and contain no Mayo references in the primary path.
- [ ] `docker compose down` stops everything cleanly and `docker compose up` restarts it with `tmp/` data intact.
