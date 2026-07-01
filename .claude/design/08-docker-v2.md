# Design: Docker Full Containerization V2

## Summary
This plan covers turning the three tiers of the platform (Virtuoso, FastAPI backend, React/Vite frontend) into a single `docker compose up --build` experience, with Blender 5.0 + the Bonsai extension bundled inside the backend image, Mayo fully removed from every runtime path, and the browser talking to one origin through an nginx reverse proxy. It also covers a beginner-friendly README rewrite.

What this plan does **not** cover: any change to SPARQL query logic, the RDF schema, the assembly-tree data model, or the IFC property pipeline; production hardening beyond what is needed to run locally (no TLS, no auth, no secrets management — the app currently has none and this milestone does not add any); and publishing images to a registry.

Important assumptions made during planning (each expanded in **Open questions**):
1. The Bonsai extension, once installed and enabled in Blender's user preferences at build time, makes `import bonsai.tool` work in a later headless `blender --python` run — i.e. Linux behaves like the current working Windows setup. This is the single biggest technical risk.
2. **Mayo is still wired into `update_STEP.py`** (it imports `convert_with_mayo` and `MAYO_SERVICE_URL`). The spec's "remove Mayo" goal is therefore impossible without migrating that route to `occ_converter.export_gltf`. This plan treats that migration as in-scope and required, mirroring exactly what step 03 did to `mayo_and_gltf.py`.
3. A specific Blender 5.0 Linux point release and download URL will resolve at build time; the exact version string is a parameter to confirm.

## Implementation order
1. **Backend code decoupling from the host (no Docker yet).** Make `BLENDER_EXE` env-driven, add the absolute `BLENDER_SCRIPT_DIR` / `IMPORT_GLTF_SCRIPT` constants in `models.py`, switch `ifc_conversion.py` to those constants, and migrate `update_STEP.py` off Mayo onto `occ_converter.export_gltf`. Doing this first means the app still runs on the host (Windows, with `BLENDER_EXE` set) and is independently testable before any container exists.
2. **Mayo removal.** Once nothing calls `convert_with_mayo` or `MAYO_SERVICE_URL`, delete the Mayo wiring from `app.py`, remove the Mayo constants from `models.py`, and delete `mayo.py` (+ `mayo-gui.ini` if unreferenced). This comes after step 1 so the codebase never passes through a broken state.
3. **Frontend single-origin conversion.** Replace the four hardcoded `localhost:8000` references with same-origin URLs and make the Vite dev proxy target env-driven. This is independent of the backend work and can proceed in parallel, but is sequenced here because it is required before the nginx proxy is meaningful.
4. **Backend image (the hard part).** Author the conda-based Dockerfile that installs the Python stack, Blender 5.0, and the Bonsai extension, with a build-time import smoke check. Establish the `/app/backend` layout so `BASE_DIR` resolves to `/app`.
5. **Frontend image + nginx.** Make `production` the built target and add `nginx.conf` with SPA fallback, `/api/` proxy, WebSocket upgrade, large body size, and long timeouts.
6. **Compose orchestration.** Rewrite `docker-compose.yml`: fix the malformed virtuoso block, wire the three services, the `tmp` volume, service-name networking, and startup ordering.
7. **Ignore files & repo hygiene.** Add `backend/.dockerignore` (keeping `bonsai/`), `frontend/.dockerignore`, `backend/bonsai/.gitkeep`, and the `.gitignore` rule for the zip.
8. **README rewrite.** Last, so it documents the system as actually built.

## Database design
No database changes. Virtuoso's schema, graphs, and triples are untouched. The only DB-adjacent change is operational: the `tenforce/virtuoso` container is asked to auto-grant SPARQL update permission via the `SPARQL_UPDATE` environment variable, removing the manual Conductor step from the happy path. Persistence continues through the existing `virtuoso-data` named volume, so existing triples survive `docker compose down`/`up`.

## Route design
No routes are added, removed, or changed in method/path/payload. The HTTP and WebSocket surface is identical. What changes is **transport and origin**, summarised per affected endpoint below.

| Endpoint (unchanged) | Before (browser) | After (browser) | Server-side change |
|---|---|---|---|
| `POST /api/sparql-query` | absolute `http://localhost:8000/...` (in `fetchQuery.ts`) | relative `/api/sparql-query` via nginx | none |
| `WS /api/ws/convert` | `ws://localhost:8000/...` (UploadSTEPModal) | same-origin `ws(s)://<host>/api/ws/convert` via nginx | none |
| `WS /api/ws/update` | `ws://localhost:8000/...` (UpdateSTEPModal) | same-origin via nginx | **handler migrated off Mayo** (see Logic design) |
| `WS /api/ws/blender_run_scripts` | `ws://localhost:8000/...` (DownloadIFCButton) | same-origin via nginx | Blender now runs in-container |
| all other `/api/*` (already relative) | relative | relative (unchanged) | none |

Access level: the application has no authentication or authorisation today, so every route remains public/unauthenticated. This milestone deliberately does not add auth (see Security checklist for the rationale and the resulting exposure note).

Error flow for the proxied transport: if the backend container is down or still starting, nginx returns 502/504 for `/api/*`; the existing frontend message panels surface fetch/WebSocket failures as error states exactly as they do today when the host backend is down. No new error handling is required, but the README must tell users the first build is slow so they do not interpret an early 502 as a failure.

## Template design
This is a React SPA — there are no server-rendered templates. The equivalent artifacts are the nginx config and the frontend source edits.

### New: `frontend/nginx.conf`
- **Purpose / role:** the production web server. Serves the compiled SPA and reverse-proxies the API so the browser uses a single origin.
- **Behaviour it must encode (in prose, no config shown here):**
  - Document root is the nginx html directory that the build stage's `dist` output is copied into.
  - SPA history fallback: any path that is not a real file falls back to `index.html` so React Router deep links work on refresh.
  - A location block for the `/api/` prefix that forwards to the backend service by its compose name on port 8000.
  - WebSocket support on that proxy: HTTP/1.1, plus forwarding of the `Upgrade` and `Connection` headers, plus passing the original host. Without these, the three WebSocket flows (convert, update, IFC generation) will not upgrade and will fail.
  - A large maximum request body size (the STEP uploads can be hundreds of MB) — on the order of 512 MB.
  - Long read/send timeouts on the proxy, because IFC generation over WebSocket can run for minutes; default nginx timeouts would sever the connection mid-job.
- **Conditional sections:** none; one server block is sufficient for local use.

### Modified frontend source (transport only — no behavioural change)
For each, what exists and what changes:

- `frontend/src/utils/fetchQuery.ts`
  - **Exists:** a single `fetch` to the absolute URL `http://localhost:8000/api/sparql-query`.
  - **Change:** make it the relative path `/api/sparql-query`. Everything else (method, headers, body, response parsing via `parseSparqlBindings`) is unchanged.
- `frontend/src/pages/STEPPage/UploadSTEPModal.tsx`
  - **Exists:** opens `new WebSocket("ws://localhost:8000/api/ws/convert")`. (Its HTTP upload already uses the relative `/api/upload-step`, confirming relative paths are the house style.)
  - **Change:** derive the WebSocket origin from `window.location` — choose `wss` when the page is `https`, otherwise `ws`, and use `window.location.host` — targeting `/api/ws/convert`. No change to the JSON payload, the `onopen/onmessage/onerror` handlers, or the status-message contract.
- `frontend/src/pages/UpdateFilesPage/UpdateSTEPModal.tsx`
  - **Exists:** `new WebSocket("ws://localhost:8000/api/ws/update")`.
  - **Change:** same same-origin derivation, targeting `/api/ws/update`.
- `frontend/src/pages/IFCPage/NodeDetails/DownloadIFCButton.tsx`
  - **Exists:** `new WebSocket("ws://localhost:8000/api/ws/blender_run_scripts")`.
  - **Change:** same same-origin derivation, targeting `/api/ws/blender_run_scripts`.
- `frontend/vite.config.ts`
  - **Exists:** dev proxy hardcodes target `http://localhost:8000`.
  - **Change:** read the target from an environment variable (e.g. `VITE_API_TARGET`) defaulting to `http://localhost:8000`, so host `npm run dev` is unaffected and a containerized dev variant could point at the backend service name. Production does not use this proxy (nginx does the proxying).

A small shared helper that builds the WebSocket base URL from `window.location` is optional but recommended to avoid repeating the protocol/host logic in three files; the plan does not require it.

## Logic design
The substantive logic changes are in three backend modules plus the Dockerfile build logic.

### `backend/api/models/models.py`
- **Responsibility:** central constants. Three concerns change.
- **`BLENDER_EXE`:** becomes environment-driven, reading an env var (`BLENDER_EXE`) and defaulting to the bare name `blender` (resolved on `PATH` inside the container). On a Windows host the developer sets the env var to the full `blender.exe` path. Decision tree: env var present → use it; absent → use `blender`.
- **Blender script path constants:** introduce a `BLENDER_SCRIPT_DIR` derived from the existing `BASE_DIR` joined to `backend/api/services/ifc_conversion/blender_script`, and from it build absolute `IMPORT_GLTF_SCRIPT` (the existing `import_gltf.py`) and `CONVERT_IFC_SCRIPT`. Output type: plain strings (the subprocess layer expects strings). This removes the OS-specific backslash literals and the dependency on the process working directory.
- **Mayo constants:** remove `MAYO_EXE`, `MAYO_SERVICE_URL`, and `INI_FILE`. Side effect: any importer of these breaks — which is exactly why the `update_STEP.py` migration (below) must land in the same change set.
- **No side effects** beyond module-load-time path computation, which already happens.

### `backend/api/routes/ifc_conversion.py`
- **Responsibility:** the IFC-generation WebSocket handler. It currently defines local backslash constants `IMPORT_GLTF_SCRIPT`, `CONVERT_IFC_SCRIPT`, and a stale `GLTF_PATH` pointing at a hardcoded sample file.
- **Change:** import `IMPORT_GLTF_SCRIPT` (and `CONVERT_IFC_SCRIPT` if kept) from `models.py` instead of defining them locally; delete the local definitions and the unused `GLTF_PATH`. Decision tree / control flow is unchanged: it still runs only `IMPORT_GLTF_SCRIPT` via `run_blender_scripts`.
- **Note (carried to Open questions):** `CONVERT_IFC_SCRIPT` references `blender_script/ifc_conversion.py`, which **does not exist** in the repo, but the constant is never used at runtime. Keeping a constant that points at a missing file is harmless but misleading; the plan's recommendation is to drop the unused constant rather than create a stub.

### `backend/api/routes/update_STEP.py` (the migration the spec missed)
- **Responsibility:** the "replace a STEP file while preserving RDF links" WebSocket pipeline. It currently converts STEP→GLTF by calling `convert_with_mayo(input_file, output_file)` inside a `run_in_threadpool`, and imports `MAYO_SERVICE_URL` from `models.py`.
- **Change:** replace the conversion call with `occ_converter.export_gltf`, mirroring the step-03 migration of `mayo_and_gltf.py`:
  - Remove the `from ..services.importing_STEP.mayo import convert_with_mayo` import and the `MAYO_SERVICE_URL` name from the `models` import line.
  - Add the `export_gltf` import from `occ_converter`.
  - `export_gltf(step_path, output_path)` accepts an output path with or without the `.gltf` extension and returns the final path; the existing code already computes `output_file` as the `.gltf` path under the (possibly per-project) gLTF folder, so it can be passed through, and the returned path used downstream.
  - The surrounding `async with httpx.AsyncClient()` block exists only because Mayo was once a separate HTTP service; after migration it wraps nothing network-related. The plan's recommendation is to keep the inner logic but drop the now-pointless `httpx` client wrapper (and the `httpx` import if unused elsewhere in the file). This is a cleanup, not a behavioural change.
  - Update the user-facing status text "Conversion Done with Mayo" to "Conversion Done", matching what step 03 did for the upload pipeline.
  - The `safe_convert_with_mayo` helper becomes dead; remove it.
- **Inputs/outputs/side effects:** unchanged — same WebSocket message sequence, same JSON/RDF artifacts written to the same (per-project aware) folders, same DB import. Only the converter implementation changes.
- **Why this is mandatory:** without it, either the build breaks (missing `convert_with_mayo`/`MAYO_SERVICE_URL` after Mayo removal) or, if Mayo is left in, the Update-STEP feature silently cannot work in a Linux container that has no `mayo-conv.exe`.

### `backend/app.py`
- **Change:** remove the two Mayo lines — the `from api.services.importing_STEP import mayo` import and the `app.include_router(mayo.router, ...)` registration. Keep `mayo_and_gltf` (verified: it already imports `export_gltf` from `occ_converter`, so it is **not** Mayo-bound despite its legacy filename). No other router registration changes.

### `backend/api/services/ifc_conversion/blender.py`
- **No functional change.** It already reads `BLENDER_EXE` and absolutizes the script path. Once `BLENDER_EXE` is env-driven and the script constants are absolute, it works unchanged in-container. The only thing to confirm is that the subprocess inherits a `PATH` containing `blender` (it will, via the image's symlink into `/usr/local/bin`).

### Dockerfile build logic (backend) — decision points, described in prose
- **Base image choice:** a conda image (Miniconda) because `pythonocc-core` is a conda-forge package with no reliable PyPI wheel; the current `pip install -r requirements.txt` cannot satisfy it. The Python stack (FastAPI, uvicorn, requests, SPARQLWrapper, python-multipart, pygltflib, numpy, httpx, rdflib, ifcopenshell, pythonocc-core) installs from conda-forge, pinned to Python 3.12 to match the documented host environment.
- **Blender install:** install the minimal X/GL/utility shared libraries Blender needs even in background mode, then download the Blender 5.0 Linux x64 archive, extract it under `/opt/blender`, and symlink the executable onto `PATH`. Blender ships its own bundled Python; the conda env and Blender's Python are intentionally separate. The backend process (conda env) shells out to `blender`, which runs Bonsai inside Blender's own Python — the same split that exists on Windows today.
- **Bonsai install:** copy the bundled zip into the image, run Blender once in background mode to install the extension into the local `user_default` extensions repository and enable it so the preference persists into the image, then delete the zip to trim the layer.
- **Build-time smoke check (fail-fast):** run Blender in background mode executing a one-line import of `bonsai.tool`; a non-zero exit fails the build. This converts the riskiest runtime assumption into a build-time guarantee.
- **Layout:** copy the backend tree to `/app/backend` so that `models.py`'s `BASE_DIR = parents[3]` resolves to `/app`, making runtime files land in `/app/tmp` (where the compose volume mounts). The launch command runs uvicorn against `app:app` without `--reload`, with the app-dir/working-dir set so the module imports while `BASE_DIR` still points at `/app`. The conda environment must be active for that command (install into the base env, or invoke via the env's interpreter).

## Dependency and integration notes
- **No new Python packages** beyond the existing `requirements.txt` list. The Dockerfile changes only the *install mechanism* (conda for `pythonocc-core`/`ifcopenshell`, conda or pip for the rest), not the set.
- **Blender 5.0 (Linux x64):** new system dependency, fetched at build time from the official Blender download archive. Integration point: invoked as a subprocess by `blender.py`; communicates progress by printing `STATUS: ...` lines that the WebSocket handler relays.
- **Bonsai extension `add-on-bonsai-v0.8.4-linux-x64.zip`:** user-supplied, ~139 MB, must be present at `backend/bonsai/` in the build context (it is gitignored). Integration point: provides the `bonsai` and bundled `ifcopenshell` modules inside Blender's Python at IFC-generation time.
- **nginx (alpine):** already the frontend production base; now also an integration point as the reverse proxy between browser and backend, including WebSocket upgrade.
- **Service networking:** the backend reaches Virtuoso by the compose service name `virtuoso` (already supported via the `DB_HOST` env var in `models.py`); nginx reaches the backend by the service name `backend`. No host ports are required for inter-service traffic; only the frontend's `3000:80` (and optionally the backend's `8000:8000` for debugging) need publishing.

## Security checklist
- **Authentication on protected routes:** Not applicable — the application has no authentication today, and this infrastructure milestone does not introduce any. Every route remains open. **Exposure note:** publishing the frontend on `localhost:3000` (and optionally the backend on `8000`) binds to the host; on a shared or public network this exposes an unauthenticated app, an unauthenticated Virtuoso (`8890`/`1111`, credentials `dba`/`ddd`), and a Blender subprocess that executes a fixed in-repo script. The README should state this is intended for local/trusted use only. Adding auth is explicitly out of scope but should be flagged as the next security step.
- **Authorisation (own-data only):** Not applicable — no user model exists; data is partitioned only by project graph, not by user. Unchanged by this work.
- **Input validation and sanitisation:** Unchanged. The STEP filename sanitisation in `update_STEP.py` (`sanitize_filename`) and `mayo_and_gltf.py` is preserved. The migration to `export_gltf` passes the same already-sanitised paths. nginx's large `client_max_body_size` widens the upload size but not the input surface; the backend still controls where files are written (within `tmp/`).
- **SQL injection prevention:** Not applicable in the relational sense; the store is RDF/SPARQL. No query construction changes in this plan, so the existing SPARQL handling is unchanged. (The spec's "parameterised queries only / no ORM" rule is honoured trivially — no query code is touched.)
- **CSRF:** Not applicable — no cookie-based sessions or auth; requests are unauthenticated JSON/form/WebSocket calls. Moving to a single origin slightly *reduces* attack surface by eliminating cross-origin calls and the need for permissive CORS.
- **Sensitive data handling:** The only secret-like values are the Virtuoso credentials (`dba`/`ddd`), which are already hardcoded/committed and unchanged here. They remain in `docker-compose.yml` as before. The plan does not introduce new secrets. Recommendation (non-blocking): move DB credentials to a `.env` referenced by compose in a later milestone.
- **Container-specific considerations:** the Bonsai zip stays out of git (size + provenance); `.dockerignore` excludes `tmp/` and caches from the build context to avoid leaking local runtime files into images. Images run as their default user (root); running as a non-root user is a possible later hardening step but is out of scope for "make it run locally."

## Open questions
1. **Does enabling the Bonsai extension at build time make `import bonsai.tool` importable in a later headless `blender --python` run on Linux?**
   - *Assumption:* yes — it mirrors the working Windows setup, and the build-time smoke check will prove it.
   - *Impact if wrong:* IFC generation fails at runtime with an import error. Mitigation is built in: the fail-fast smoke check turns this into a build failure, and the fallback would be to load/enable the extension explicitly inside `import_gltf.py` (or pass an `--addons`/enable step on each Blender invocation) rather than relying on persisted preferences. This is the highest-risk item and should be validated first when implementation begins.
2. **`update_STEP.py` still depends on Mayo — is migrating it to `occ_converter` acceptable scope?**
   - *Assumption:* yes, and it is required (the spec's Mayo-removal goal is otherwise contradictory). Treated as in-scope.
   - *Impact if wrong / deferred:* if the team wants to keep Update-STEP on Mayo, then Mayo cannot be removed and that feature cannot run in the Linux container — the "full containerization" goal would be partial. Recommend confirming, but the plan proceeds with migration.
3. **Exact Blender 5.0 Linux version and download URL.**
   - *Assumption:* a concrete 5.0 point release exists and its archive URL resolves at build time; the version string is pinned in the Dockerfile.
   - *Impact if wrong:* build fails on download. Low effort to fix; just needs the confirmed URL. The Bonsai zip is built for `v0.8.4` and a Blender 5.x ABI, so the Blender major/minor must match what Bonsai 0.8.4 targets — confirm compatibility (Bonsai 0.8.x may target Blender 4.2+/5.0; verify the pairing).
4. **`tmp/` as a bind mount vs named volume.**
   - *Assumption:* bind-mount the host `./tmp` so users can see generated STEP/GLTF/GLB/IFC files directly (matches the README's "files appear in `tmp/`").
   - *Impact if wrong:* a named volume hides files from the host but is more portable. Choosing bind mount per the README's intent; trivially swappable.
5. **Does `tenforce/virtuoso` honour `SPARQL_UPDATE=true` to auto-grant, on the image version in use?**
   - *Assumption:* yes; the manual Conductor grant becomes an optional fallback in the README.
   - *Impact if wrong:* writes fail until the user runs the one-time grant; mitigated by keeping that step in the README clearly marked "usually not needed."
6. **Unused `CONVERT_IFC_SCRIPT` pointing at a non-existent `blender_script/ifc_conversion.py`.**
   - *Assumption:* drop the unused constant rather than create a stub file.
   - *Impact if wrong:* none at runtime (it is never executed); purely a code-cleanliness choice.

## Definition of done (design review)
Design-level criteria to satisfy before implementation starts (distinct from the spec's runtime DoD):
- [ ] The Mayo-dependency map is confirmed complete: `convert_with_mayo`/`MAYO_SERVICE_URL`/`MAYO_EXE`/`INI_FILE` consumers are exactly `app.py`, `models.py`, `mayo.py`, and `update_STEP.py` — and the plan addresses every one. (Verified during planning: a repo-wide search found no other consumers.)
- [ ] It is agreed that `update_STEP.py` migrates to `occ_converter.export_gltf` (Open question 2 resolved).
- [ ] The backend container layout is agreed such that `BASE_DIR` resolves to the directory above `backend/` and `tmp/` is the mounted runtime location.
- [ ] The plan for guaranteeing `import bonsai.tool` (build-time smoke check + documented fallback) is accepted as sufficient mitigation for the top risk (Open question 1).
- [ ] The single-origin approach (relative HTTP + `window.location`-derived WebSocket + nginx `/api/` proxy with WS upgrade, 512 MB body, long timeouts) is agreed, and the four frontend files plus `vite.config.ts` are confirmed as the complete edit set (`grep` for `localhost:8000` under `frontend/src` returns only those files).
- [ ] The Blender 5.0 ↔ Bonsai 0.8.4 version pairing is confirmed compatible (Open question 3).
- [ ] The unauthenticated-exposure note is acknowledged and the README will state "local/trusted use only."
- [ ] Decisions on `tmp/` mount type (bind vs named), Virtuoso auto-grant fallback, and dropping the unused `CONVERT_IFC_SCRIPT` are recorded.
- [ ] No code has been written during planning (this is a design artifact only).
