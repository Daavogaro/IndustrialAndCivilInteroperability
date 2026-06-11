# Design: Multiple Project

## Summary
This plan covers turning the platform's single hardcoded Virtuoso named graph (`http://localhost:8890/Elettra2/`) into a first-class, user-managed **Project** concept. It designs: (1) a backend `projects.py` router backed by a flat `projects.json` file (list / create / delete, with a Virtuoso `DROP GRAPH` on delete); (2) the removal of the hardcoded graph URI from the four backend routes that still bake it in (`update_deletion`, `update_simplification`, `product_inventory`, `product_hierarchy`); (3) a React `ProjectContext` that owns the active project and persists it to `localStorage`; (4) a `ProjectsPage` management UI; and (5) propagation of the active project's graph URI through **every** frontend call that talks to a graph.

It does **NOT** cover: per-project file isolation in `tmp/` (STEP/GLTF/GLB/IFC artifacts stay shared — graph-level isolation only, per the spec); authentication or per-user ownership of projects; renaming projects; or migrating/copying triples between graphs.

The single most important finding from reading the codebase — and the thing this plan corrects relative to the spec — is that **the hardcoded graph string is scattered across ~10 frontend files, not the 6 the spec's "Files to change" lists**. Several of those are non-obvious (the central `refreshStepHierarchy` loader, `FundamentalNodeButton`, the two upload WebSocket modals, `IFCNodeDetails`, `AddChildModal`). If any one is missed, the corresponding feature silently keeps writing to / reading from `Elettra2/` regardless of the active project, and several Definition-of-Done items fail. This plan enumerates all of them.

A second key finding: **the spec is internally inconsistent about where the graph value comes from.** Its route design has the client send the `graph` URI (query param / body field), but its "Rules for implementation → General" security note states "graph URI always originates from `projects.json` on the server side." Those cannot both be literally true. This plan resolves the contradiction explicitly (see *Open questions* #1 and *Security checklist*): the client sends the graph URI (consistent with the existing `add-child` / `add-ifc` pattern), and the server **validates it against the known project list** before interpolating it into any SPARQL string — which honours the *intent* of the security rule without a larger route redesign.

Note: this project has **no** `database/db.py` and **no** server-side templates — persistence is RDF in Virtuoso plus the new `projects.json`, and the UI is React. The skill's "Database design" and "Template design" sections are therefore adapted to "Persistence design" and "Frontend component design", consistent with how design `01-product-inventory.md` handled the same mismatch.

## Implementation order
1. **Backend `projects.py` + `projects.json` seeding.** Build the project registry first so the data contract (`id`, `name`, `graphUri`, `createdAt`) and the seed-on-first-read behaviour are fixed before anything consumes them. Verifiable in isolation by hitting the three endpoints. Critical detail: the seed entry's `graphUri` must be the **existing** `http://localhost:8890/Elettra2/`, not a value derived from its id, so existing Virtuoso data stays reachable.
2. **Backend graph-parameterisation.** Update `update_deletion`, `update_simplification`, `product_inventory`, `product_hierarchy` to accept the graph from the request and validate it against `projects.json`. This must land before the frontend starts sending the parameter, so the contract is stable.
3. **Frontend `ProjectContext` + provider.** Build the context (projects list, active project, setter, loader, `localStorage` persistence) and wrap the app. Everything downstream reads from it, so it comes before the consuming pages.
4. **Frontend `ProjectsPage` + sidebar wiring.** Build the management page and add the nav link + active-project label. This gives a way to exercise create/activate/delete and to see the active project, which makes the remaining propagation work testable.
5. **Frontend graph propagation sweep.** Replace every hardcoded `"http://localhost:8890/Elettra2/"` with the active project's `graphUri` from context, across all ~10 files. This comes last because it depends on the context existing and is the highest-risk, broadest-touch step; doing it after the page exists means each change can be verified against a real active project.

## Persistence design

### New file: `backend/projects.json`
- **Purpose:** the authoritative registry of projects. Replaces the implicit single-graph assumption.
- **Shape:** a JSON array of objects, each: `id` (string, slug), `name` (string, human label), `graphUri` (string, full Virtuoso named-graph URI), `createdAt` (string, ISO-8601 UTC).
- **Location:** at `BASE_DIR / "backend" / "projects.json"` using the same `pathlib`/`BASE_DIR` convention as `models.py`. It must **not** be committed with real data — it is created on first read if absent. (Add it to `.gitignore` if a broad ignore doesn't already cover it; confirm during review.)
- **Seeding:** on the first read where the file is absent or contains an empty array, the backend writes a single seed entry:
  - `id`: a stable slug for the legacy project (e.g. `elettra2`).
  - `name`: `"Elettra 2.0"`.
  - `graphUri`: **`http://localhost:8890/Elettra2/`** — hardcoded to the legacy value, deliberately *not* derived from the id, so all pre-existing triples remain visible under the seeded project.
  - `createdAt`: the seed timestamp.
- **Concurrency:** all reads and writes go through a single module-level `threading.Lock` to prevent torn writes when two requests mutate the file at once. Writes are full-file rewrites (read array → mutate in memory → write whole array), which is safe and simple at this scale.
- **No indexes / migrations** in the relational sense. The only "migration" is the idempotent seed-on-first-read, which is non-destructive (it only writes when the file is missing/empty).

### Virtuoso named graphs
- No schema change to existing graphs. A new project owns a new empty named graph `http://localhost:8890/{id}/`; it becomes populated the first time a STEP file is uploaded while that project is active.
- **Deletion** issues `DROP SILENT GRAPH <graphUri>` to `VIRTUOSO_URL` via `requests.post(..., data={"update": ...})` (mirroring the existing `update_deletion.py` POST pattern), then removes the entry from `projects.json`. `SILENT` makes dropping an empty/absent graph a no-op rather than an error.

## Route design

### `GET /api/projects` (new)
- **Purpose / behaviour:** list all projects for the management page and the context loader.
- **Inputs:** none.
- **Validation:** none.
- **Access level:** public on the local network (matches every existing route; no auth layer exists).
- **Success flow:** read `projects.json` under the lock (seeding it first if absent), return the full array with `200`. If absent/empty after seeding, the seeded array is returned — so callers always get at least the legacy project. (The spec's DoD also requires that a *genuinely* empty file returns `[]` rather than an error; seeding satisfies the "no error" requirement, and an empty array is returned only if seeding is intentionally skipped — see Open question #4.)
- **Error flow:** unreadable/corrupt JSON → `HTTPException(500)` with a descriptive detail.

### `POST /api/projects` (new)
- **Purpose / behaviour:** create a new project; on success the frontend makes it active.
- **Inputs:** JSON body with `name` (string).
- **Validation:**
  - `name` trimmed; empty/whitespace-only → `HTTPException(422)` (or `400`) with a clear message → surfaced inline on the form.
  - Derive `id` from `name`: lowercase, spaces → hyphens, strip characters outside `a-z0-9-`, collapse repeats, trim leading/trailing `-`, cap at 40 chars. If the derived id is empty after stripping (e.g. name was all punctuation), reject with `422`.
  - If the derived id collides with an existing project id, append a numeric suffix (`-1`, `-2`, …) until unique. (The spec also mentions returning `409` on duplicate id; see Open question #2 — this plan prefers auto-suffixing for a smoother UX and treats `409` as the fallback only if auto-suffix is explicitly rejected in review.)
- **Access level:** public.
- **Success flow:** build the object (`id`, `name`, `graphUri = http://localhost:8890/{id}/`, `createdAt` = ISO-8601 UTC stamped *in the route*, not in any model default), append under the lock, persist, return the created object with `200`/`201`. No Virtuoso write occurs at creation — the graph springs into existence on first triple insert.
- **Error flow:** validation failures as above; file write failure → `500`.

### `DELETE /api/projects/{project_id}` (new)
- **Purpose / behaviour:** remove a project and drop its graph.
- **Inputs:** `project_id` path param.
- **Validation:** if no project with that id exists → `HTTPException(404)`.
- **Access level:** public.
- **Success flow:** look up the project, issue `DROP SILENT GRAPH <graphUri>` to Virtuoso, remove the entry under the lock, persist, return `{"status": "success"}`.
- **Error flow:** not found → `404`; Virtuoso unreachable → `500` (and the entry is **not** removed, so the user can retry — decide in review whether to remove the JSON entry even if the DROP fails; this plan keeps them transactional: only remove on a successful DROP). Deleting the active project is **not** blocked server-side; the frontend disables that button, and re-activation of a remaining project is the client's responsibility.

### `POST /api/update-deletion` (modified)
- **Change:** add `graph: str` to `UpdateDeletionRequest`; replace the two literal `http://localhost:8890/Elettra2/` occurrences with the request's graph.
- **Validation (new):** the supplied graph must match a known project's `graphUri` (allowlist check against `projects.json`); on mismatch → `HTTPException(400)`. See Security checklist.
- Everything else (metadata-driven DELETE/INSERT of `x3d:visible`) unchanged.

### `POST /api/update-simplification` (modified)
- Identical treatment to `update-deletion`, operating on `x3d:bboxDisplay`.

### `GET /api/product-inventory` (modified)
- **Change:** add a required `graph` query parameter (FastAPI `Query(...)`). Remove the module-level `GRAPH` constant. Crucially, the existing `_QUERY` is a module-level f-string baked at import time with `GRAPH` already interpolated — query construction must move **inside** the request handler (or a function that takes `graph`) so the active graph is interpolated per request.
- **Validation:** missing `graph` → FastAPI returns `422` automatically; present-but-unknown graph → allowlist check → `400`.
- Success/error flow otherwise unchanged (still `run_in_threadpool`, still `[]` on empty, `500` on Virtuoso failure).

### `GET /api/product-hierarchy/{label}` (modified)
- **Change:** add a required `graph` query parameter; remove the module-level `GRAPH` constant; the per-request `_run_all` already builds its four queries inside a function, so it gains a `graph` argument that the four f-strings use. The `label` path-param handling (URL-decode, `404` on empty / not-found) is unchanged.
- **Validation:** as above — `422` if missing, `400` if not in the allowlist, `404` if the label matches no Fundamental Node in that graph.

### Routes deliberately **not** changed
`add_child`, `add_fundamental_node`, `add_ifc_prop` already accept `graph` in their request body. `mayo_and_gltf` (STEP→GLTF→RDF WebSocket) and `update_STEP` already read `graph_name` from the incoming WebSocket message. These backend routes are correct as-is; only their **frontend callers** hardcode the value and must change (see Frontend component design). They should still gain the same allowlist validation if it's cheap to add, but that is optional and out of this spec's stated scope.

## Frontend component design

### New: `frontend/src/context/ProjectContext.tsx`
- **Role:** single source of truth for the active project across the SPA.
- **Exports:** `ProjectContext`, `ProjectProvider`, and a `useProject()` hook.
- **State shape:** `{ projects: Project[]; activeProject: Project | null; setActiveProject(p: Project): void; loadProjects(): Promise<void> }`, where `Project = { id: string; name: string; graphUri: string; createdAt: string }`.
- **On mount:** call `loadProjects()` → `GET /api/projects`. Then resolve the active project: read `localStorage["activeProjectId"]`; if that id exists in the fetched list, activate it; otherwise activate the first project (and write its id back to `localStorage`).
- **`setActiveProject(p)`:** update state and persist `p.id` to `localStorage["activeProjectId"]`.
- **`loadProjects()`:** refetch and reconcile the active project (if the currently active one was deleted, fall back to the first remaining; if none remain, set `activeProject` to `null`).
- **Edge cases:** while loading, `activeProject` is `null` — consumers must guard (disable graph-dependent actions). Network failure on load surfaces via an `error`-style state (optional) or a console error plus an empty list; the page still renders.

### New: `frontend/src/pages/ProjectsPage/ProjectsPage.tsx`
- **Layout:** `<Topbar title="Projects" />` at top; a "New Project" form; a responsive card grid of projects (`var(--background-100)`, `generalButton`, matching design 01's grid idiom).
- **Dynamic data:** `projects`, `activeProject` from `useProject()`.
- **New Project form:** one text input (project name) + submit button. On submit → `POST /api/projects` → on success call `loadProjects()` and `setActiveProject(created)`; on failure show an inline error (empty name, server `422`/`409`). Form does not navigate away.
- **Per-card content:** project name; graph URI; created date formatted `DD/MM/YYYY`; an **Activate** button (disabled + visually highlighted when this card is the active project); a **Delete** button (disabled when this card is the active project).
- **Activate flow:** `setActiveProject(project)` → sidebar label updates immediately; no navigation required.
- **Delete flow:** show a confirmation; on confirm → `DELETE /api/projects/{id}` → on success `loadProjects()`; if the deleted project happened to be active (shouldn't be, since the button is disabled, but defensively) re-activate the first remaining project. If zero projects remain, render an empty-state prompting creation.
- **Conditional sections:** empty-state when no projects; inline error region for create/delete failures.

### Modified: `frontend/src/App.tsx`
- **Currently:** renders `Sidebar` + `Routes` (`/`, `/IFCHierarchy`, `/FileUpdate`, `/ProductInventory`, `/product/:label`), owns shared `message`, `tree`, `nodeUri` state.
- **Changes:** wrap the returned JSX in `<ProjectProvider>` so context is available to `Sidebar` and all pages. Add `<Route path="/Projects" element={<ProjectsPage />} />`. No change to existing routes or shared state.

### Modified: `frontend/src/components/Sidebar/Sidebar.tsx`
- **Currently:** logos + nav links (STEP Hierarchy, IFC Hierarchy, Product Inventory, File Update) + `MessagePanel`.
- **Changes:** add a "Projects" nav link (`folder` material icon) → `/Projects`. Below the logos, render the active project name (small text, e.g. an `active-project-label` span) read via `useProject()`. When `activeProject` is `null`, render a muted placeholder ("No project").

### The graph-propagation sweep (the critical, under-specified part)
Every file below currently hardcodes `const graphName = "http://localhost:8890/Elettra2/"` (or embeds it in a SPARQL `FROM` clause / WebSocket body). Each must instead obtain the active project's `graphUri` from `useProject()` and pass it onward. **All ten must be changed for the feature to work end-to-end; the spec's file list names only some of them.**

| File | How the graph is used today | Required change |
|---|---|---|
| `pages/STEPPage/STEPPage.tsx` | local `graphName`, displayed, and drives `refreshStepHierarchy` (via effect) | read `activeProject.graphUri`; display it; pass into the new `refreshStepHierarchy` signature |
| `pages/STEPPage/Hierarchy/HierarchyButtons/buttons/UpdateHierarchyButton.tsx` (`refreshStepHierarchy`) | free function; `graphName` baked into 4 SPARQL `FROM` clauses | **change signature to accept `graphUri`** and interpolate it into all four queries; update the `UpdateHierarchyButton` component to source it from context |
| `pages/STEPPage/AddChildModal.tsx` | sends `graph` in `/api/add-child` body (already a param) | source `graph` from context instead of the literal |
| `pages/STEPPage/UploadSTEPModal.tsx` | sends `graph_name` in the convert WebSocket message | source from context |
| `pages/STEPPage/gLTFViewer/FundamentalNodeButton.tsx` | sends `graph` to `/api/add-fundamental-node` **and** calls `/api/update-deletion` (without graph today) | source `graph` from context; add `graph` to the `update-deletion` body (now required by the backend) |
| `pages/ProductDetailPage/NodeDetails/NodeDetails.tsx` | calls `/api/update-deletion` and `/api/update-simplification` without graph | add `graph` (from context) to both bodies |
| `pages/IFCPage/IFCHierarchyPage.tsx` | local `graphName`, displayed, drives `refreshStepHierarchy` | source from context; pass into `refreshStepHierarchy` |
| `pages/IFCPage/NodeDetails/IFCNodeDetails.tsx` | sends `graph` in `/api/add-ifc-properties` body | source from context |
| `pages/UpdateFilesPage/UpdateFilesPage.tsx` | `graphName` embedded in a SPARQL `FROM` clause | source from context; interpolate into the query |
| `pages/UpdateFilesPage/UpdateSTEPModal.tsx` | sends `graph_name` in the update WebSocket message | source from context |
| `pages/InventoryProductPage/InventoryProductPage.tsx` + `useProductInventory.ts` | `GET /api/product-inventory` (no graph today) | hook takes `graphUri`, appends `?graph=<encoded>`, adds it to the effect dependency so switching projects refetches |
| `pages/ProductDetailPage/ProductDetailPage.tsx` + `useProductHierarchy.ts` | `GET /api/product-hierarchy/{label}` (no graph today) | hook takes `graphUri`, appends `?graph=<encoded>`, refetch on change |

**`refreshStepHierarchy` is the highest-leverage change.** It is a plain async function (not a hook) called from four places: the `STEPPage` mount effect, `IFCHierarchyPage`, the `UpdateHierarchyButton` component, and `FundamentalNodeButton`'s `onUpdated` callback. Threading `graphUri` as its first argument is the cleanest fix (single signature change; every caller already has, or can get, context access). The alternative — a module-level "active graph" holder the provider writes to so free functions can read it without a signature change — is noted in *Open questions* #3 but not recommended, because hidden global state here would make the data-loading path harder to reason about.

## Logic design

### Backend: `slugify_project_name(name) -> id`
- **Responsibility:** derive a URL/graph-safe id from a human name.
- **Input:** `name` (string). **Output:** slug (string, ≤40 chars).
- **Decision tree:** trim → lowercase → spaces to hyphens → drop chars outside `[a-z0-9-]` → collapse repeated hyphens → strip leading/trailing hyphens → truncate to 40. If empty result → signal invalid (caller returns `422`).
- **Side effects:** none.

### Backend: `ensure_unique_id(id, existing_ids) -> id`
- **Responsibility:** guarantee uniqueness by suffixing.
- **Decision tree:** if `id` not in `existing_ids`, return it; else append `-1`, `-2`, … until free.
- **Side effects:** none.

### Backend: `read_projects()` / `write_projects(list)`
- **Responsibility:** locked file I/O for `projects.json`, with seed-on-first-read inside `read_projects`.
- **Side effects:** may create/overwrite `projects.json`. Always called under the module lock.

### Backend: `assert_known_graph(graph)`
- **Responsibility:** allowlist validation — confirm a client-supplied graph URI matches some project's `graphUri`.
- **Input:** `graph` (string). **Output:** none (raises `HTTPException(400)` on mismatch).
- **Decision tree:** load projects; if `graph` ∈ `{p.graphUri}` → pass; else → raise.
- **Side effects:** reads `projects.json`. This is the bridge that satisfies the spec's "graph originates server-side" security intent while still letting the client pass the URI.

### Frontend: `ProjectProvider` reconciliation
- **Responsibility:** keep `activeProject` consistent with the fetched list and `localStorage`.
- **Decision tree:** after each load — if stored id present in list → activate it; else if list non-empty → activate first + persist; else → `activeProject = null`.
- **Side effects:** writes `localStorage["activeProjectId"]`.

## Dependency and integration notes
- **No new packages**, backend or frontend. Backend reuses `requests` / `SPARQLWrapper` (already used) and stdlib `json`, `pathlib`, `threading`, `datetime`, `re`. Frontend reuses React context + `react-router-dom` + `fetch`, all already present.
- **Integration points:** Virtuoso SPARQL endpoint (`VIRTUOSO_URL`) for `DROP GRAPH` and all reads/writes; the Vite `/api` proxy (use relative `/api/...` paths in new code — note `fetchQuery.ts` currently uses an absolute `http://localhost:8000` URL, which is pre-existing and out of scope to change here). No third-party services.

## Security checklist
- **Authentication on protected routes:** not applicable — the entire app is unauthenticated local-network tooling; the new project routes match that posture. Worth stating in review that project create/delete is therefore unauthenticated and anyone on the network can drop a graph.
- **Authorisation (own-data only):** not applicable — no user/ownership model. All projects are visible to all clients by design.
- **Input validation / sanitisation:** project `name` is trimmed and slugified to `[a-z0-9-]` before forming an id or graph URI, so a malicious name cannot inject SPARQL or path characters into the constructed `graphUri`. The `graph` parameter now arriving from clients on `update-deletion`, `update-simplification`, `product-inventory`, and `product-hierarchy` is **validated against the `projects.json` allowlist** (`assert_known_graph`) before being interpolated into any SPARQL string — this is the core mitigation for the new client-supplied-graph attack surface and resolves the spec's internal contradiction (Open question #1).
- **SQL/SPARQL injection prevention:** the existing routes already interpolate `metadata` and `graph` into SPARQL via f-strings without parameterisation — a pre-existing characteristic of this codebase, not introduced here. This plan does not worsen it for the graph value (allowlist-validated) and leaves the existing `metadata` interpolation untouched (unchanged behaviour). True SPARQL parameter binding is not available through the current `requests`/`SPARQLWrapper` usage; the allowlist is the pragmatic equivalent for the graph value. Flag for review if stricter binding is desired.
- **CSRF:** not applicable — no cookies/sessions; CORS is already restricted to `http://localhost:3000`. The new `POST`/`DELETE` routes are state-changing but unauthenticated and same-posture as existing mutating routes (`add-child`, `update-deletion`).
- **Sensitive data handling:** none — projects contain only a name and a graph URI. The destructive operation (`DROP GRAPH` on delete) is the main risk; it is gated behind a frontend confirmation and a disabled-for-active-project button, but **not** server-side (anyone calling the API directly can delete any non-protected project). Recorded as an accepted limitation for a local tool.

## Open questions
1. **Client-supplied graph vs. server-resolved graph (the spec's contradiction).** The route design sends `graph`; the security rule says it originates server-side from `projects.json`.
   - *Assumption:* client sends the `graphUri` (consistent with existing `add-child`/`add-ifc` behaviour), and the server validates it against the `projects.json` allowlist before use.
   - *Impact if wrong:* if the reviewer wants strict server-side resolution, the routes should instead accept a `project_id` and look up the `graphUri` server-side. That changes every route signature and every frontend caller to pass an id instead of a URI — a larger but more defensible refactor. The allowlist approach is chosen as the minimal change that still satisfies the security intent.
2. **Duplicate-name handling: auto-suffix vs. 409.** The spec mentions both an `id` collision suffix rule *and* a `409` on duplicate id.
   - *Assumption:* auto-suffix the id (`elettra2`, `elettra2-1`) so creation always succeeds; reserve `409` only if review prefers hard rejection.
   - *Impact if wrong:* trivial to flip to `409` + inline "name already exists" error; isolated to the create route and the form's error branch.
3. **Threading `graphUri` into `refreshStepHierarchy` vs. a global holder.**
   - *Assumption:* change the function signature to take `graphUri` (explicit, no hidden state).
   - *Impact if wrong:* if signature churn across the four callers is judged too invasive, a module-level active-graph holder updated by the provider is the fallback; it reduces signature changes but introduces global mutable state and a subtle ordering dependency (the holder must be set before any loader runs).
4. **Seed-on-read vs. truly-empty `[]`.** The DoD says `GET /api/projects` returns `[]` when `projects.json` is absent, but also that the seeded "Elettra 2.0" project appears on first load.
   - *Assumption:* seeding wins — first load returns the seeded array (never a bare `[]` in normal operation); the `[]` case is interpreted as "no error / valid empty array semantics," satisfied because seeding produces a valid array. The literal empty-array case only occurs if seeding is deliberately disabled.
   - *Impact if wrong:* if the reviewer wants a genuinely empty start (no legacy project), drop the seed; but then pre-existing `Elettra2/` data is invisible until a project pointing at it is manually created — likely undesirable.
5. **`projects.json` location and git.** Placing it in `backend/` risks it being committed.
   - *Assumption:* it is generated at runtime and git-ignored; not committed.
   - *Impact if wrong:* a committed file with machine-specific projects would leak into other environments; ensure `.gitignore` covers it (or relocate under `tmp/`, which is already ignored — worth considering in review since `tmp/` is the established home for runtime state).
6. **Per-project file isolation.** `tmp/STEP|gLTF|GLB|IFC` remain shared across projects; uploading the same filename under two projects overwrites artifacts.
   - *Assumption:* out of scope (spec says graph-level isolation only).
   - *Impact if wrong:* if file collisions matter, a later spec must namespace `tmp/` subfolders by project id.

## Definition of done (design review)
- [ ] The full list of ~10 graph-hardcoded frontend files (the propagation table) is acknowledged as the real change surface, not just the 6 in the spec.
- [ ] The client-sends-graph + server-side-allowlist resolution to the spec's contradiction is accepted (or strict server-side `project_id` resolution is chosen instead).
- [ ] The seed entry's `graphUri` is agreed to be the legacy `http://localhost:8890/Elettra2/`, independent of its derived id, so existing data stays reachable.
- [ ] `refreshStepHierarchy`'s signature change to accept `graphUri` (vs. a global holder) is agreed, and all four call sites are identified.
- [ ] The `projects.json` location and git-ignore status are decided (`backend/` ignored vs. relocate under `tmp/`).
- [ ] Duplicate-name behaviour (auto-suffix vs. `409`) is decided.
- [ ] The allowlist validation (`assert_known_graph`) is agreed as the SPARQL-injection mitigation for the new client-supplied `graph` parameter, and the accepted limitation (unauthenticated `DROP GRAPH`) is recorded.
- [ ] Confirmed that `product_inventory.py`'s module-level baked `_QUERY` and `product_hierarchy.py`'s `_run_all` are restructured so the graph is interpolated per-request, not at import time.
- [ ] Confirmed the WebSocket/body routes (`add-child`, `add-fundamental-node`, `add-ifc`, `mayo_and_gltf`, `update_STEP`) need **frontend-only** changes (their backends already parameterise the graph).
