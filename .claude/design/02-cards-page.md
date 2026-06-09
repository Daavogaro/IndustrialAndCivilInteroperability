# Design: Cards Page (Product Detail)

## Summary
This plan covers turning the `/product/:label` stub into a three-zone product workspace: a left zone that mounts the existing `NodeDetails` component scoped to one product instance, a top-right collapsible 3D viewer that isolates and centres that product's geometry inside the shared GLB, and a bottom-right collapsible zone that mounts the existing `IFCNodeDetails` editor for the currently selected node. It also covers one new read-only backend route (`GET /api/product-hierarchy/{label}`) that returns the product's subtree in the exact shape `buildTree()` already consumes. It does **not** cover: any change to `NodeDetails` or `IFCNodeDetails` themselves (they are reused verbatim), real provenance, write operations beyond the already-existing delete/simplify/IFC endpoints those components call, or multi-instance editing (the page deliberately works on the *first* instance only). 

Several integration realities discovered while reading the code drive the plan and are called out where they bite: (1) `NodeDetails` calls `setTree` with the **functional-updater** form, so the page's tree setter must be the raw `useState` dispatcher; (2) `NodeDetails` only renders its child-navigation tabs when the node is a `CADAssembly`, and has no built-in "navigate back up", so a root-reset affordance is needed; (3) the `FundamentalNodeButton` embedded in `NodeDetails` triggers `refreshStepHierarchy`, which rebuilds the **entire global** STEP tree from Virtuoso and would clobber our product-scoped tree; (4) `IFCNodeDetails` is built around a `uris: string[]` array and applies properties by **metadata**, so passing a single-element array is correct and naturally affects all instances; (5) product isolation in the viewer depends on GLB node names carrying the `.1` instance suffix. As with the 01 design, this project has **no** `database/db.py` and **no** server-side templates, so the skill's "Database design" and "Template design" sections are adapted to "RDF / data-source design" and "Frontend component design".

## Implementation order
1. **Backend route first.** Build and register `product_hierarchy.py` so the data contract (roots + edges + ifcData + ifcPsetData + rootUri) is fixed and independently verifiable by hitting the endpoint before any UI exists. Everything downstream consumes this shape.
2. **Data hook.** Build `useProductHierarchy.ts` against the live endpoint: fetch, run `buildTree()`, expose `{ rootUri, tree, setTree, loading, error, refresh }` where `setTree` is the raw state dispatcher. This isolates fetch/parse concerns and gives the page a typed source before layout work.
3. **CollapsiblePanel.** Build the pure presentational `CollapsiblePanel` wrapper next, since both right-column zones depend on it and it carries the flex-based space-sharing behaviour that the viewer's resize handling relies on.
4. **ProductGLTFViewer.** Adapt `gLTFViewer.tsx` into the isolating viewer. This is the highest-risk piece (scene traversal, visibility filtering, camera centring), so it comes after the cheaper scaffolding but before final composition, allowing focused iteration.
5. **Page composition.** Replace the `ProductDetailPage.tsx` stub: wire the hook, the shared `selectedNodeUri`/`hoveredUri`/`localMessage` state, the left `NodeDetails`, and the two right panels (`ProductGLTFViewer`, `IFCNodeDetails`). This is last because it depends on every other piece existing.

## RDF / data-source design
No schema changes. The feature is read-only against the existing named graph `http://localhost:8890/Elettra2/`. The spec already contains the four SPARQL query bodies; this section covers correctness concerns rather than restating them.

**Predicates relied upon (all produced by the existing import pipeline):**
- `x3d:hasMetadata` — groups instance nodes under a shared metadata URI (`https://elettra2.0#<label>`).
- `x3d:attrib = "Fundamental_Node"` — marks the product root. Must be matched defensively with `FILTER(STR(?attrib) = "Fundamental_Node")` because the literal is stored `^^xsd:string` (this exact concern was settled in the 01 design; reuse that decision for consistency).
- `x3d:name` — the per-instance integer; the basis for "first instance" (`ORDER BY ?num … LIMIT 1`).
- `x3d:children` — parent→child edges; traversed with the `x3d:children*` zero-or-more property path to gather the whole subtree.
- `rdf:type` (`a`) — separates X3D type (`CADPart`/`CADAssembly`) from IFC type via namespace-prefix filters.
- IFC predicates (`ifc:globalId_IfcRoot`/`rdf:value`, `ifc:predefinedType_*`, `ifc:objectType_IfcObject`) and the property-set chain — reused verbatim from the existing `ifcQuery`/`ifcPsetQuery` in `UpdateHierarchyButton.tsx`.

**Correctness notes to fold into the implementation:**
- **First-instance selection** must be deterministic: order by the integer `x3d:name` and take one. If `x3d:name` is ever stored as a string rather than an `xsd:integer`, lexical ordering could pick the wrong instance (e.g. "10" before "2"); the import writes it as `xsd:integer` (confirmed in `RDF_conversion.py`), so numeric ordering holds — but this is an assumption to verify.
- **Subtree scoping** uses `<ROOT_URI> x3d:children* ?parent` for edges and the `{…children*…} UNION {BIND(<ROOT_URI> AS ?node)}` idiom for the IFC queries so the root node itself is included, not just its descendants.
- **`rdf:` prefix**: the existing IFC queries rely on Virtuoso's built-in `rdf:` namespace without declaring it. Mirror the existing code for consistency, but prefer declaring `PREFIX rdf:` explicitly in the new route to remove the implicit dependency.
- **`fileUrl` normalisation**: strip the `file:///` prefix server-side, matching `refreshStepHierarchy` (which does `.replace("file:///","")` on the client today). Doing it on the server keeps the hook simple and the contract clean.
- **Empty vs missing**: a label that resolves to no fundamental-node root is a 404 (`{"detail": "Product not found"}`); a label that resolves to a root with no children is **not** an error — it returns a single-root tree with an empty edges array.

**Migration strategy:** none — read-only, no triples written.

## Route design

### `GET /api/product-hierarchy/{label}`
- **Method / path:** `GET /api/product-hierarchy/{label}`, registered with the `/api` prefix in `backend/app.py`, consistent with every other router.
- **Purpose / behaviour:** returns the first-instance subtree of one Fundamental Node product type, pre-shaped for `buildTree()`.
- **Request inputs:** one path param, `label` (the human product label, e.g. `SomePart`). No query params, no body.
- **Validation rules:**
  - `label` is URL-decoded with `urllib.parse.unquote` before use, then composed into the metadata URI `https://elettra2.0#<decoded>`. The composed value is **only** interpolated into SPARQL by the server; the client never sends a raw URI or query fragment.
  - If `label` is empty/whitespace after decoding → treat as not found (404) rather than running a malformed query.
- **Auth / access-level:** public on the local network, matching the entire app (no auth layer exists). No CORS change needed (`localhost:3000` already allowed).
- **Success flow:** the handler runs all four queries sequentially inside a single `run_in_threadpool` call, assembles `{ rootUri, roots, edges, ifcData, ifcPsetData }`, and returns `200`. The frontend hook feeds `roots/edges/ifcData/ifcPsetData` into `buildTree()`.
- **Error flow:**
  - Root query returns zero rows → `HTTPException(404, "Product not found")`.
  - Virtuoso unreachable / timeout / malformed response → `HTTPException(500)` with a descriptive `detail`, mirroring `sparql_query.py` and `product_inventory.py`.
  - Root found but no edges → `200` with `edges: []` (valid single-node product).

### `GET /product/:label` (frontend route — already registered)
- The React Router route already exists in `App.tsx`; only the page body changes. `label` is read via `useParams` (React Router decodes it automatically; navigation from the inventory already `encodeURIComponent`s it). The page passes the decoded label both to `<Topbar>` and to the hook (which re-encodes for the fetch path).

## Frontend component design

### Modified: `ProductDetailPage.tsx`
- **Currently:** a stub rendering `<Topbar title={label} />` and a "coming soon" paragraph.
- **Becomes:** the orchestrator. Responsibilities:
  - Read `label` from `useParams`; call `useProductHierarchy(label)`.
  - Own the shared state listed in the spec: `selectedNodeUri`, `hoveredUri`, `localMessage`, `viewerCollapsed`, `ifcCollapsed`. `tree`/`setTree`/`rootUri`/`loading`/`error` come from the hook.
  - Initialise `selectedNodeUri` to `rootUri` once the fetch resolves (a `useEffect` on `rootUri`).
  - Render four regions in a `grid-template-rows: auto auto 1fr` shell: `<Topbar>`, a back-navigation bar, the two-column body, and a slim `localMessage` status bar.
  - Left column (≈40% width, scrollable): `<NodeDetails>` with the props in the spec.
  - Right column (flex column): `<CollapsiblePanel title="Product Viewer">` wrapping `<ProductGLTFViewer>`, then `<CollapsiblePanel title="IFC Properties">` wrapping `<IFCNodeDetails>`.
  - Loading branch: show a loading indicator instead of the body. Error branch: show the error message plus a "Retry" action calling the hook's `refresh`.
- **Conditional sections:** loading / error / loaded; within loaded, the bottom-right zone shows `IFCNodeDetails` only when `selectedNodeUri` is set (otherwise `IFCNodeDetails`'s own "No node selected" guard renders, since `uris` is `[]`).

### New: `useProductHierarchy.ts`
- **Role:** data hook. Fetches `/api/product-hierarchy/${encodeURIComponent(label)}` via the relative path (Vite proxy — no hard-coded host, consistent with the 01 design's decision and unlike the older `fetchQuery` util which hard-codes `localhost:8000`).
- **Behaviour:** on `label` change (and on `refresh`), set loading, fetch, and on success map the JSON arrays through `buildTree(edges, roots, ifcData, ifcPsetData)` to produce `TreeNode[]`; store both `rootUri` and the built `tree`.
- **Exposes:** `{ rootUri, tree, setTree, loading, error, refresh }`.
- **Critical detail:** `setTree` must be the **raw** `useState` dispatcher (not a wrapper), because `NodeDetails` invokes it with the functional-updater form `setTree(prev => …)`. Exposing a value-only wrapper would break delete/simplify toggling.
- **States:** `loading` true during fetch; `error` set on non-2xx (including 404) or network failure; `tree` is `[]` until the first successful build.

### New: `CollapsiblePanel.tsx`
- **Role:** pure presentational wrapper; holds **no** state.
- **Props:** `title: string`, `collapsed: boolean`, `onToggle: () => void`, `children: ReactNode`.
- **Markup:** a clickable title bar (styled like the existing `toogle-view`/header chrome) showing the title and a chevron (`▼` expanded / `▶` collapsed), plus a body container.
- **Space-sharing behaviour (the important part):** when expanded the panel uses `flex: 1; min-height: 0` and its body uses `overflow: hidden`; when collapsed the panel shrinks to the title-bar height (e.g. `flex: 0 0 36px`) and the body is hidden via `height: 0; overflow: hidden` — **not** `display: none`. Keeping the body in layout (rather than unmounting/`display:none`) ensures the Three.js canvas continues to receive resize events and the renderer's `resizeViewer` keeps the viewport correct when the sibling panel toggles. Two expanded panels each get `flex: 1` → equal split; collapsing one lets the other's `flex: 1` absorb the freed space automatically.

### New: `ProductGLTFViewer.tsx` (adapted from `gLTFViewer.tsx`)
- **Props:** `productLabel: string`, `hoveredUri?: string | null`.
- **Reused verbatim from the original:** scene/camera/renderer/lights setup, `OrbitControls`, pointer hover-highlight, right-click `focusOnObject`, Escape-to-reset, the `normalizeName` helper, `applyUriHighlight`, and the `POST /api/gltf-upload` → load `/api/glb/<name>` loading flow.
- **Changed from the original:**
  - **Container id** becomes `product-viewer-container` (the original uses `viewer-container`). The original reads the container by a fixed `getElementById`, so a distinct id avoids any DOM collision and makes the component self-contained.
  - **File-list overlay removed.** The checkbox list of loaded GLBs is dropped — this viewer shows a single isolated product, not a file switcher.
  - **Product isolation added** after each model finishes loading (detailed in Logic design): hide everything outside the product's first-instance subtree, then centre the camera on what remains.
  - **Hover highlight** is driven by the `hoveredUri` prop (wired from the left `NodeDetails`' `setHoveredUri`), reusing the existing `applyUriHighlight` effect.
- **Container sizing:** the original hard-codes `height: 50vh`. Inside a flex `CollapsiblePanel`, the viewer container should instead fill its panel (`height: 100%`) so it grows when the sibling collapses; the existing `resizeViewer` (already bound to `window resize`) handles the dimension change.

### Reused without modification
- **`NodeDetails.tsx`** (left zone) and **`IFCNodeDetails.tsx`** (bottom-right zone) are imported and rendered as-is. `buildTree`, `TreeNode`, `getDescendantsWithDimensions`, `findNode`, `FundamentalNodeView`, `AssemblyView`, `DownloadIFCButton`, and the IFC schema JSON are all transitively reused unchanged.

## Logic design

### Backend: subtree assembly (inside `product_hierarchy.py`)
- **Responsibility:** run the four queries and assemble the response dict.
- **Inputs:** decoded `label` → metadata URI.
- **Outputs:** `{ rootUri, roots[], edges[], ifcData[], ifcPsetData[] }`.
- **Decision tree:**
  - Run root query. **Zero rows → raise 404** (short-circuit; skip the other three queries).
  - Otherwise bind `ROOT_URI` to the returned `?root` URI and run the three subtree queries.
  - Transform each binding set into the documented field shapes; strip `file:///` from `fileUrl`; pass through `cadType`/`metadata`/`attrib`/etc. as full URIs/literals exactly as `buildTree` expects (note: `buildTree` itself does the `#`-splitting for display, so the route should **not** pre-split those).
- **Side effects:** none (read-only). Runs entirely within one `run_in_threadpool` call to avoid blocking the event loop, matching `product_inventory.py`.

### Frontend: tree construction (inside `useProductHierarchy.ts`)
- **Responsibility:** convert the four arrays into `TreeNode[]` via the existing `buildTree`.
- **Inputs:** the JSON response. **Output:** `{ rootUri, tree }`.
- **Note:** `buildTree`'s `roots` argument expects objects keyed `uri/cadType/metadata/…`; the route returns `roots` already in that shape, so the hook maps 1:1 with no reshaping. `edges` likewise maps directly to `buildTree`'s edge shape.

### Frontend: product isolation (inside `ProductGLTFViewer.tsx`)
- **Responsibility:** after a GLB loads, show only the geometry belonging to the product's first instance and centre the camera on it.
- **Inputs:** the loaded scene graph; `productLabel`.
- **Decision tree:**
  1. Compute the match target as `normalizeName(productLabel + ".1")` using the existing `normalizeName` (strips `_ . space -`, lowercases). Rationale: GLB instance nodes carry the instance suffix (`SomePart.1`), and the metadata label is suffix-free, so the first instance is `label + ".1"`.
  2. **First pass — collect the product set:** traverse the scene; an object is "in the product" if its own normalised `userData.name` equals the target, OR it has an ancestor whose normalised name equals the target (reuse the same ancestor-walk logic already present in `applyUriHighlight`'s `hasNamedAncestor`).
  3. **Second pass — hide the rest:** set `visible = false` on every object that is neither in the product set nor an **ancestor** of a product-set member. Ancestors must stay `visible = true`, otherwise Three.js will not render their (visible) descendants. Hiding (not removing) is reversible and cheap.
  4. **Centre the camera:** build a `Box3` union over the visible product-set members and call the existing `focusOnObject` against a proxy object placed at the box centre (or pass the union box directly into the same framing maths `focusOnObject` already uses). Also update the stored "initial" camera pose so Escape-to-reset returns to the product-framed view rather than the whole-scene view.
- **Edge cases:**
  - **No match** (target not found among GLB node names): leave the scene fully visible and log a warning, rather than hiding everything and showing a blank viewer. (See Open Question 1.)
  - **Multiple `.1` matches** (shouldn't happen within one product, but possible across unrelated products that happen to normalise identically): the spec says show the first instance; framing the union box is acceptable, but this is a known fuzziness of name-based matching.
- **Side effects:** mutates `object.visible` flags and camera state on the live scene; no network, no React state beyond what the original already tracks.

### Frontend: selection + message plumbing (inside `ProductDetailPage.tsx`)
- **`selectedNodeUri`**: initialised to `rootUri`; updated when `NodeDetails` calls `setNodeUri`. Drives both `NodeDetails` (`uri`) and `IFCNodeDetails` (`uris={[selectedNodeUri]}`).
- **`onClearSelection` for IFCNodeDetails**: resets `selectedNodeUri` back to `rootUri` after IFC properties are applied (rather than to `null`, so the page stays anchored on the product).
- **`hoveredUri`**: set by `NodeDetails`' `setHoveredUri` (fired from row hover in `FundamentalNodeView`/`AssemblyView`); passed to the viewer for highlight.
- **`localMessage`**: `{ status, text } | null`; set by both child components' `setMessage` prop; auto-cleared by a `setTimeout(…, 8000)` in a `useEffect` (mirroring `App.tsx`'s 10s pattern); rendered as a slim page-scoped bar. **Not** propagated to `App`'s global sidebar.

## Dependency and integration notes
- **No new packages**, backend or frontend. Backend reuses `SPARQLWrapper`; the viewer reuses the already-present `three`, `OrbitControls`, `GLTFLoader`, and `MeshoptDecoder`; the page reuses `react-router-dom`.
- **Integration points:** Virtuoso SPARQL endpoint (`VIRTUOSO_URL`) on the backend; the `/api/gltf-upload` listing route and the `/api/glb` static mount for GLB files; the existing `/api/update-deletion`, `/api/update-simplification`, and `/api/add-ifc-properties` routes (called by the reused child components, unchanged). No third-party services.
- **Registration:** add `from api.routes import product_hierarchy` and `app.include_router(product_hierarchy.router, prefix="/api")` to `backend/app.py`, alongside the existing `product_inventory` registration.

## Security checklist
- **Authentication on protected routes:** not applicable — the whole app is unauthenticated local-network tooling; this route matches that posture and is read-only.
- **Authorisation (own-data only):** not applicable — no user/ownership model; the single graph is shared by design.
- **Input validation / sanitisation:** the only untrusted input is the `label` path param. It is URL-decoded then composed into a metadata URI and interpolated **only** server-side into SPARQL; the client cannot inject a query fragment. The label is rendered as plain text (Topbar, never `dangerouslySetInnerHTML`), so no XSS surface. An empty/whitespace label is rejected as 404 before any query runs.
- **SPARQL injection prevention:** the queries are server-composed; the single interpolated value is a label that becomes part of an angle-bracketed IRI. Risk is low but non-zero (a label containing `>` or whitespace could in theory break out of the IRI). **Mitigation to apply:** validate the decoded label against an allowed pattern (the same character set produced by metadata URIs — no `>`, no whitespace, no control chars) and 404 on violation; this is stronger than relying on IRI escaping. This mirrors the spirit of the project's "parameterised/sanitised only" rule even though SPARQL has no bind-parameter for IRIs here.
- **CSRF:** not applicable — `GET`, read-only, no cookies/sessions. (The write routes invoked by the reused components are pre-existing and out of scope.)
- **Sensitive data handling:** none — the response exposes component labels, CAD/IFC types, dimensions, and property sets already visible elsewhere in the UI.

## Open questions
1. **GLB node naming / the `.1` assumption.** Product isolation matches `normalizeName(productLabel + ".1")` against GLB `userData.name`. This assumes (a) the GLB carries per-instance names suffixed with the instance number and (b) the first instance is `.1`.
   - *Assumption for this plan:* the Mayo-produced GLB preserves STEP node names (which the RDF stores as `label + "." + number`), so `<label>.1` exists. If `userData.name` isn't populated by the loader, matching falls back to whatever `applyUriHighlight` already relies on (it reads `userData.name` too, so behaviour is consistent with the existing highlight feature).
   - *Impact if wrong:* the viewer would find no match and (per the chosen edge-case handling) show the **whole** scene instead of an isolated product — degraded, not broken. If names are present but lack the `.1` suffix, isolation should match on the bare `productLabel` instead; this is a one-line change to the target computation. **Worth verifying against a real GLB early in step 4.**
2. **`FundamentalNodeButton` inside `NodeDetails` rebuilds the global tree.** Its `onUpdated` callback runs `refreshStepHierarchy(setTree, setMessage)`, which queries **all** roots and replaces the tree — clobbering our product-scoped subtree.
   - *Assumption:* acceptable for v1 because toggling fundamental-node status from the product page is an edge action; if pressed, the tree simply repopulates with the global hierarchy until the user navigates back. 
   - *Impact if wrong / better option:* if this is jarring, the page can pass a `setTree`/refresh that re-fetches the **product** hierarchy instead of the global one. But `NodeDetails` hard-codes the `refreshStepHierarchy` import, so honouring "reuse `NodeDetails` verbatim" means we cannot intercept it without editing the component. Recommend confirming whether the button should be present here at all.
3. **No "navigate up" once a `CADPart` is selected.** `NodeDetails` only renders child-navigation tabs for `CADAssembly` nodes; selecting a leaf `CADPart` shows terminal detail with no way back to the product root from within `NodeDetails`.
   - *Assumption:* add a small "↩ Product root" affordance in the left column header (outside `NodeDetails`) that resets `selectedNodeUri` to `rootUri`. This keeps `NodeDetails` unmodified while closing the navigation dead-end.
   - *Impact if wrong:* without it, users can get "stuck" on a part and must use the browser back button or re-enter the page.
4. **Product root that is itself a `CADPart`.** If a Fundamental Node is a single part (not an assembly), the left zone shows only minimal detail and no descendants, and the viewer isolates a single mesh.
   - *Assumption:* this is valid and acceptable — the page still works, just with a trivial hierarchy.
   - *Impact if wrong:* none functionally.
5. **First-instance ordering depends on `x3d:name` being numeric.** Confirmed `xsd:integer` in `RDF_conversion.py`, so `ORDER BY ?num` is numeric.
   - *Assumption:* holds. *Impact if wrong:* lexical ordering could pick instance "10" before "2"; mitigated by an explicit `xsd:integer` cast in the query if ever needed.

## Definition of done (design review)
- [ ] The `product-hierarchy` route contract (field names, full-URI vs short-name semantics, `rootUri`, 404-on-missing, 200-with-empty-edges) is agreed before frontend work begins.
- [ ] It is confirmed that `buildTree` consumes the route's `roots`/`edges`/`ifcData`/`ifcPsetData` arrays **without reshaping**, and that the route returns full URIs (not pre-split `#` fragments).
- [ ] The decision on label sanitisation (allowed-pattern validation + 404 on violation) is accepted as the SPARQL-injection mitigation.
- [ ] It is confirmed that `useProductHierarchy` exposes the **raw** `useState` setter as `setTree` (so `NodeDetails`' functional updates work).
- [ ] The `CollapsiblePanel` space-sharing approach (flex `1`/`0 0 auto`, body hidden via `height:0` not `display:none`) is accepted, and the rationale (Three.js resize) understood.
- [ ] The product-isolation algorithm (target = `normalizeName(label + ".1")`, keep matches + ancestors, hide rest, frame union box) is accepted, **and** the `.1`-suffix assumption (Open Question 1) is scheduled for early verification against a real GLB.
- [ ] A decision is recorded on the `FundamentalNodeButton`-rebuilds-global-tree behaviour (Open Question 2): leave as-is, or hide the button.
- [ ] A decision is recorded on the "Product root" reset affordance for the leaf-node navigation dead-end (Open Question 3).
- [ ] It is confirmed the page uses a **local** message bar and does not touch `App`'s global sidebar message.
- [ ] It is confirmed both `NodeDetails` and `IFCNodeDetails` are used verbatim (no edits), and the new viewer uses a distinct `product-viewer-container` id.
