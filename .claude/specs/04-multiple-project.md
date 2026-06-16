# Spec: Multiple Project

## Overview
The platform currently manages a single hardcoded project whose RDF data lives in the Virtuoso named graph `http://localhost:8890/Elettra2/`. This spec introduces a first-class **Project** concept: users can create, switch between, and delete projects from a dedicated management page. Each project owns a distinct Virtuoso named graph. All API routes that previously hardcoded the graph URI are updated to accept it as a parameter. A React Context propagates the active project throughout the frontend so every API call automatically targets the correct graph. File storage (`tmp/`) remains shared between projects in this spec; graph-level isolation is the primary goal.

## Depends on
No previous spec is strictly required. Specs 01–03 are assumed complete; the product-inventory and product-hierarchy routes modified here were added in specs 01–02.

## Routes

### New routes
- `GET /api/projects` — list all projects (returns array of project objects) — public
- `POST /api/projects` — create a new project (`name` in body) — public
- `DELETE /api/projects/{project_id}` — delete project and drop its Virtuoso named graph — public

### Modified routes (add `graph` parameter)
- `POST /api/update-deletion` — add `graph: str` to `UpdateDeletionRequest`
- `POST /api/update-simplification` — add `graph: str` to `UpdateSimplificationRequest`
- `GET /api/product-inventory` — add `graph` as a query parameter (replaces hardcoded constant)
- `GET /api/product-hierarchy/{label}` — add `graph` as a query parameter (replaces hardcoded constant)

Routes that already accept `graph` in the body (add_child, add_fundamental_node, add_ifc_prop, mayo_and_gltf, update_STEP) are unchanged.

## Database changes
No Virtuoso schema changes. Projects are stored in `backend/projects.json` — a flat JSON array written and read by the backend. Each entry:
```json
{
  "id": "elettra2",
  "name": "Elettra 2.0",
  "graphUri": "http://localhost:8890/Elettra2/",
  "createdAt": "2026-01-01T00:00:00"
}
```

On first startup (file absent or empty), the backend initialises `projects.json` with one seed entry for `"Elettra 2.0"` so the existing data in Virtuoso remains accessible.

When a project is deleted, the backend issues:
```sparql
DROP SILENT GRAPH <{graphUri}>
```
to Virtuoso using `requests.post(VIRTUOSO_URL, data={"update": ...})`, then removes the entry from `projects.json`.

## Templates / Components

**Create:**
- `frontend/src/context/ProjectContext.tsx` — React Context + provider that holds `{ projects, activeProject, setActiveProject, loadProjects }`. Persists `activeProjectId` to `localStorage`.
- `frontend/src/pages/ProjectsPage/ProjectsPage.tsx` — management page: project list + create form + delete button per project
- `backend/api/routes/projects.py` — FastAPI router for the three project routes

**Modify:**
- `frontend/src/App.tsx` — wrap app in `<ProjectProvider>`; pass `activeProject` down where needed (or rely on context)
- `frontend/src/components/Sidebar/Sidebar.tsx` — show active project name under the logos; add "Projects" nav link
- `frontend/src/pages/STEPPage/STEPPage.tsx` — read `activeProject` from context; pass `graphUri` to API calls that need it
- `frontend/src/pages/IFCPage/IFCHierarchyPage.tsx` — same as STEPPage
- `frontend/src/pages/UpdateFilesPage/UpdateFilesPage.tsx` — same
- `frontend/src/pages/InventoryProductPage/InventoryProductPage.tsx` — pass `?graph=` query param
- `frontend/src/pages/ProductDetailPage/ProductDetailPage.tsx` — pass `?graph=` query param
- `frontend/src/pages/STEPPage/NodeDetails/` (whichever component calls `/api/update-deletion` and `/api/update-simplification`) — include `graph` in request body
- `backend/api/routes/update_deletion.py` — add `graph` field, remove hardcoded URI
- `backend/api/routes/update_simplification.py` — add `graph` field, remove hardcoded URI
- `backend/api/routes/product_inventory.py` — replace `GRAPH` constant with `graph` query param
- `backend/api/routes/product_hierarchy.py` — replace `GRAPH` constant with `graph` query param
- `backend/app.py` — register `projects.router`

## Files to change
- `backend/app.py`
- `backend/api/routes/update_deletion.py`
- `backend/api/routes/update_simplification.py`
- `backend/api/routes/product_inventory.py`
- `backend/api/routes/product_hierarchy.py`
- `frontend/src/App.tsx`
- `frontend/src/components/Sidebar/Sidebar.tsx`
- `frontend/src/pages/STEPPage/STEPPage.tsx` (and child components that call update-deletion / update-simplification)
- `frontend/src/pages/IFCPage/IFCHierarchyPage.tsx`
- `frontend/src/pages/UpdateFilesPage/UpdateFilesPage.tsx`
- `frontend/src/pages/InventoryProductPage/InventoryProductPage.tsx`
- `frontend/src/pages/ProductDetailPage/ProductDetailPage.tsx`

## Files to create
- `backend/api/routes/projects.py`
- `backend/projects.json` (seeded at first request if absent — do not commit a real file)
- `frontend/src/context/ProjectContext.tsx`
- `frontend/src/pages/ProjectsPage/ProjectsPage.tsx`

## New dependencies
No new Python packages. No new npm packages.

## Rules for implementation

### projects.py
- Project `id` is derived from the name: lowercase, spaces→hyphens, strip non-alphanumeric except `-`, max 40 chars; collisions get a numeric suffix (`elettra2-1`, etc.)
- `graphUri` = `http://localhost:8890/{id}/`
- `createdAt` is the ISO-8601 UTC timestamp at creation time (injected by the route, not the model)
- Read/write `projects.json` using `pathlib.Path` relative to `BASE_DIR` (same pattern as models.py); use a file-level lock (`threading.Lock`) to prevent concurrent write corruption
- `GET /api/projects` returns the full array; 200 with empty array if file absent
- `POST /api/projects` returns the created project object; 409 if a project with the same id already exists
- `DELETE /api/projects/{project_id}` returns `{"status": "success"}`; 404 if not found; drop the Virtuoso graph silently even if empty
- No SQLAlchemy or ORMs
- Parameterised queries only — graph URI comes from `projects.json`, never from raw user input in SPARQL strings

### update_deletion.py / update_simplification.py
- Add `graph: str` to the Pydantic model
- Replace the two hardcoded `http://localhost:8890/Elettra2/` strings in each file with `{request.graph}`
- No other changes

### product_inventory.py / product_hierarchy.py
- Add `graph: str = Query(...)` parameter to the route function (import `Query` from `fastapi`)
- Replace the module-level `GRAPH` constant references inside the SPARQL strings with `{graph}`
- Remove the module-level `GRAPH = "..."` constant
- Return HTTP 422 automatically if `graph` is missing (FastAPI default)

### ProjectContext.tsx
- Exports `ProjectContext`, `ProjectProvider`, and `useProject` hook
- On mount, `loadProjects()` fetches `GET /api/projects`; sets `activeProject` to the stored `localStorage` entry (by id) if it exists in the fetched list, otherwise defaults to the first project
- `setActiveProject(project)` updates state and writes `project.id` to `localStorage` under key `"activeProjectId"`
- Shape: `{ projects: Project[], activeProject: Project | null, setActiveProject, loadProjects }`
- `Project` type: `{ id: string, name: string, graphUri: string, createdAt: string }`

### ProjectsPage.tsx
- Renders `<Topbar title="Projects" />` at the top
- Lists all projects in a card grid (same CSS variable `var(--background-100)`, `generalButton` style)
- Each card shows: project name, graph URI, created date (formatted `DD/MM/YYYY`), an **Activate** button (disabled/highlighted when already active), and a **Delete** button (disabled for the active project)
- A "New Project" form at the top: one text input for the project name + submit button; on success the list refreshes and the new project becomes active
- Delete shows a confirmation before calling `DELETE /api/projects/{id}`; on success reloads list; if the deleted project was active, activates the first remaining one
- If no projects exist after deletion, shows an empty-state message prompting the user to create one

### Sidebar.tsx
- Add a "Projects" nav link (icon: `folder` material icon) pointing to `/Projects`
- Below the logos, render the active project name in small text (e.g. `<span class="active-project-label">{activeProject?.name}</span>`) using `useProject()`

### App.tsx
- Wrap the existing JSX with `<ProjectProvider>`; the context is then available to all pages
- Add `<Route path="/Projects" element={<ProjectsPage />} />`

### Graph parameter propagation
- In all frontend components that call routes now requiring `graph`:
  - Obtain `activeProject?.graphUri` from `useProject()`
  - Pass it in the request body (`graph: activeProject.graphUri`) or as a query string parameter (`?graph=<uri>`)
  - If `activeProject` is `null` (projects still loading), disable the relevant actions (grey out buttons)

### General
- No SQLAlchemy or ORMs
- Parameterised queries only — graph URI always originates from `projects.json` on the server side; `metadata` values in deletion/simplification queries already use parameterised f-strings (no change needed there)
- Keep styling consistent with the rest of the app: `panel-scroll`, `generalButton`, `var(--background-100)`, `Topbar`

## Definition of done
- [ ] Navigating to `/Projects` renders the project management page with a list of projects and a "New Project" form
- [ ] The seeded "Elettra 2.0" project appears in the list on first load (even before `projects.json` is committed)
- [ ] Creating a project with a valid name adds it to the list; the new project becomes active immediately
- [ ] Creating a project with an empty or duplicate name shows an inline error, not a page crash
- [ ] Clicking **Activate** on a non-active project updates the active project label in the sidebar
- [ ] The active project name is persisted across page reloads (localStorage)
- [ ] Deleting a non-active project removes it from the list and drops its Virtuoso graph; no other data is affected
- [ ] The **Delete** button is disabled for the currently active project
- [ ] The sidebar shows the active project name under the logos
- [ ] Uploading a STEP file and converting it stores triples in the active project's Virtuoso graph (not always `Elettra2/`)
- [ ] The STEP Hierarchy page renders the assembly tree from the active project's graph
- [ ] The Product Inventory page shows only products from the active project's graph
- [ ] The Product Detail page loads hierarchy data from the active project's graph
- [ ] Marking a node as "to be deleted" calls `/api/update-deletion` with the active project's graph URI; Virtuoso is updated in the correct graph
- [ ] Marking a node as "to be simplified" calls `/api/update-simplification` with the active project's graph URI
- [ ] Switching the active project and reloading the STEP Hierarchy page shows the new project's data (or an empty tree if the graph has no triples)
- [ ] `GET /api/projects` returns an empty array (not an error) when `projects.json` is absent
- [ ] `DELETE /api/projects/{id}` returns 404 for a non-existent project id
- [ ] Starting `python backend/run.py` succeeds with no import errors from the new `projects.py` route
