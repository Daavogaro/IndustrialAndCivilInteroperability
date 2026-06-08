# Design: Product Inventory

## Summary
This plan covers a read-only Product Inventory feature: a backend FastAPI route that runs a single SPARQL aggregation against the existing Virtuoso graph and returns one clean record per **Fundamental Node** product type, plus a React page that renders those records as a grid of clickable cards with live search and four sort modes, and a stub product-detail page reached by clicking a card. It does **not** cover real provenance tracking (last editor / last edit date are hardcoded placeholders), the contents of the detail page beyond a title and a "coming soon" message, pagination, or any write/edit operations. Key assumptions: (1) the `Fundamental_Node` attrib is stored as an `xsd:string` literal — confirmed in `add_fundamental_node.py` — and the query must match that datatype; (2) marking a node fundamental applies the attrib to *all* nodes sharing a metadata URI, so grouping by metadata yields a correct per-product instance count; (3) the dark theme and existing CSS utility classes (`generalButton`, `panel-scroll`, `ifc-card`, `toogle-view.active`) are reused rather than introducing new global styles. Note: this project has **no** `database/db.py` and **no** server-side templates — persistence is RDF in Virtuoso and the UI is React — so the skill's "Database design" and "Template design" sections are adapted to "RDF / data-source design" and "Frontend component design".

## Implementation order
1. **Backend route first.** Build and register `product_inventory.py` so the data contract is fixed before any UI work. This is the foundation everything else consumes, and it can be verified independently by hitting the endpoint directly.
2. **Inventory data hook.** Build `useProductInventory.ts` against the real endpoint so the page has a typed, reusable source of `{ items, loading, error, refresh }` before any rendering logic exists.
3. **Card component.** Build `ProductCard.tsx` as a pure presentational unit (props in, markup out, red-when-incomplete styling) so it can be reasoned about and styled in isolation.
4. **Inventory page composition.** Replace the `InventoryProductPage.tsx` stub with search bar + sort controls + the card grid + loading/error/empty states, wiring the hook and the card together.
5. **Routing + detail stub.** Add `ProductDetailPage.tsx` and register the `/product/:label` route in `App.tsx`, then make cards navigate. This comes last because it depends on the card existing and being clickable.

## RDF / data-source design
There are **no schema changes**. The feature is purely read-side against the existing named graph `http://localhost:8890/Elettra2/`.

**Source predicates relied upon (all already produced by the import pipeline):**
- `x3d:hasMetadata` — links an instance node to its shared metadata URI (`https://elettra2.0#<label>`); the grouping key for a "product type".
- `x3d:attrib` with value `"Fundamental_Node"` — marks fundamental nodes. **Critical:** `add_fundamental_node.py` inserts this as `"Fundamental_Node"^^xsd:string`. In RDF 1.1 a plain literal is implicitly `xsd:string`, so a plain match *should* succeed, but to be robust against Virtuoso literal-matching quirks the query should either (a) match the explicit typed literal, or (b) bind `?attrib` and apply `FILTER(STR(?attrib) = "Fundamental_Node")`. Approach (b) is recommended as the most defensive.
- `rdf:type` (`a`) — a node carries its X3D type (`CADPart` / `CADAssembly`) and, when classified, an IFC type in the `IFC4X3_ADD2` namespace. The two are separated by namespace-prefix filters.

**Aggregation correctness notes (to fold into the final query):**
- Use `COUNT(DISTINCT ?node)`, not `COUNT(?node)`. Because the optional IFC-type join and the X3D-type join can each contribute rows, a non-distinct count risks inflation if a node ever carries more than one matching type triple. DISTINCT makes the instance count provably correct.
- Group by `?metadata`; `SAMPLE()` the `cadType` and `ifcClass` (one representative value per product type is sufficient for the card).
- `ORDER BY DESC(count)` server-side is a sensible default, though the frontend re-sorts anyway.

**Backend-derived / injected fields (not from RDF):**
- `label` — last `#` segment of the metadata URI, computed server-side.
- `cadType` — last `#` segment of the X3D type URI (`CADPart` / `CADAssembly`).
- `ifcClass` — last `#` segment of the IFC type URI, or `null` when the OPTIONAL is unbound.
- `lastEditor` = `"Sergio Mattarella"` and `lastEditDate` = `"2026-05-14T10:32:00"` — hardcoded constants injected into every record, each marked with a `TODO` comment pointing at future PROV-based provenance.

**Migration strategy:** none required — read-only, no triples written, no breaking change to existing queries.

## Route design

### `GET /api/product-inventory`
- **Method / path:** `GET /api/product-inventory` (registered with the `/api` prefix in `backend/app.py`, consistent with all other routers).
- **Purpose / behaviour:** returns a JSON array of product-type records for the inventory grid. One record per fundamental-node metadata group.
- **Request inputs:** none — no query params, no path params, no body. (The SPARQL string is fully static, which by construction satisfies the "no user input in queries" rule.)
- **Validation rules:** not applicable (no inputs). The handler must still defensively handle Virtuoso returning zero bindings (→ empty array, HTTP 200) versus Virtuoso being unreachable or erroring (→ HTTP 500).
- **Auth / access-level:** public on the local network, matching every other route in this app (no auth layer exists). No change to the CORS policy is needed.
- **Success flow:** handler runs the static SPARQL query inside `run_in_threadpool` (same pattern as `sparql_query.py`), transforms each binding into the clean record shape (deriving `label`/`cadType`/`ifcClass` short names, casting `count` from its string literal to an integer, injecting the two fake fields), and returns the list. Client receives `200` with the array.
- **Error flow:**
  - Virtuoso unreachable / timeout / malformed response → catch and raise `HTTPException(500)` with a descriptive `detail`, mirroring `sparql_query.py`.
  - Empty result set → **not** an error; return `[]` with `200` so the frontend can show its empty state.

### `GET /product/:label` (frontend route only — no backend)
- **Method / path:** client-side React Router route, not an HTTP API. Path param `label`.
- **Purpose / behaviour:** renders the stub product-detail page for the clicked product.
- **Inputs:** `label` path param, read via `useParams`.
- **Validation:** none for the stub; if `label` is missing/empty the page shows a generic title. Because labels can contain characters that are unsafe in a URL segment, navigation must `encodeURIComponent` the label and the page must rely on React Router's automatic decoding of `useParams` (no manual double-decoding).
- **Success flow:** displays `<Topbar title={label} />` and a "coming soon" paragraph.
- **Error flow:** not applicable — purely presentational stub.

## Frontend component design

### New: `ProductDetailPage.tsx` (`frontend/src/pages/ProductDetailPage/`)
- **Renders:** `Topbar` with the decoded `label` as title, and a single paragraph "Product detail coming soon."
- **Dynamic data:** `label` from `useParams`. No props, no data fetching.
- **Conditional sections:** none.

### New: `ProductCard.tsx` (`frontend/src/pages/InventoryProductPage/`)
- **Role:** pure presentational card for one product record.
- **Props it needs:** the full record (`label`, `count`, `cadType`, `ifcClass`, `lastEditor`, `lastEditDate`) plus an `onClick`/navigation handler (or it renders a router `<Link>` internally).
- **Layout:** name in bold/large at top; a CAD-type badge; instance count; IFC class (or `—` when `null`); last editor; last edit date formatted `DD/MM/YYYY HH:mm` from the ISO string.
- **Conditional styling:** when `ifcClass` is `null`, the card uses a strong red background with white text (incomplete-metadata flag); otherwise it reuses the existing dark card style (`ifc-card` / `var(--background-100)` family). The red should be a hard-coded accent (e.g. `#c0392b`) since no red token exists in the theme palette.

### New: `useProductInventory.ts` (`frontend/src/pages/InventoryProductPage/`)
- **Role:** data hook. Fetches `/api/product-inventory` (relative path — the Vite dev server proxies `/api/*` to the backend, so no hard-coded `localhost:8000`).
- **Exposes:** `{ items, loading, error, refresh }`.
- **States:** `loading` true during fetch; `error` set on non-2xx or network failure; `items` is the parsed array (possibly empty).

### Modified: `InventoryProductPage.tsx`
- **Currently:** a stub rendering only `<Topbar title="Inventory Product" />` (and an unused `GLTFViewer` import).
- **Changes:** remove the unused import; fix the title to "Product Inventory" for consistency with the sidebar label; add (1) a controlled search input, (2) a row of four sort buttons styled like `toogle-view`/`generalButton` with an active state, (3) a responsive CSS-grid container of `ProductCard`s, and (4) explicit loading / error / empty branches. Search and sort are applied client-side over `items` via derived state (filter then sort) — no refetch on interaction.
- **Conditional sections:** loading spinner/text while `loading`; error message when `error`; empty-state message when `items` is `[]`; otherwise the grid.

### Modified: `App.tsx`
- **Currently:** defines routes for `/`, `/IFCHierarchy`, `/IFCViewer`, `/FileUpdate`, `/ProductInventory`.
- **Changes:** add a `<Route path="/product/:label" element={<ProductDetailPage />} />` and import the new page. No other route changes; the `/ProductInventory` route and its sidebar link already exist.

### Not modified: `Sidebar.tsx`
- The "Product Inventory" nav link to `/ProductInventory` already exists — no change needed. (Worth confirming during review so we don't add a duplicate.)

## Logic design

### Backend: record transformation (inside `product_inventory.py`)
- **Responsibility:** convert raw SPARQL JSON bindings into the clean API contract.
- **Inputs:** the `results.bindings` list from `SPARQLWrapper`.
- **Outputs:** a list of dicts matching the documented response shape.
- **Decision tree per binding:**
  - `label` ← split `metadata` value on `#`, take last segment.
  - `cadType` ← split the X3D type value on `#`, take last segment.
  - `ifcClass` ← if the `ifcClass` binding is present, split on `#` take last; else `null`.
  - `count` ← cast the literal value to `int`.
  - `lastEditor` / `lastEditDate` ← constant injection (with `TODO`).
- **Side effects:** none (read-only).

### Frontend: derived filtered-and-sorted list (inside `InventoryProductPage.tsx`)
- **Responsibility:** produce the display list from `items`, the search term, and the active sort key.
- **Inputs:** `items` (array), `search` (string), `sortKey` (one of `name | lastEdit | status | author`).
- **Output:** a new array to map into cards.
- **Decision tree:**
  - Filter: keep records whose `label` contains `search` (case-insensitive substring). Empty search keeps all.
  - Sort by `sortKey`:
    - `name` → alphabetical by `label` (default).
    - `lastEdit` → descending by `lastEditDate`.
    - `status` → incomplete (`ifcClass === null`) first, then complete.
    - `author` → alphabetical by `lastEditor`.
  - Sorting must be on a copy (never mutate `items` in place).
- **Side effects:** none.

### Frontend: date formatting helper
- **Responsibility:** turn the ISO `lastEditDate` into `DD/MM/YYYY HH:mm`.
- **Inputs:** ISO date-time string. **Output:** formatted string. Defensive: if parsing fails, fall back to the raw string rather than rendering `Invalid Date`.

## Dependency and integration notes
- **No new packages**, backend or frontend. The backend reuses `SPARQLWrapper` (already used by `sparql_query.py`); the frontend reuses `react-router-dom` (already a dependency) for `useParams`/navigation.
- **Integration points:** Virtuoso SPARQL endpoint (`VIRTUOSO_URL` from `models.py`) on the backend; the Vite `/api` proxy on the frontend. No third-party services.

## Security checklist
- **Authentication on protected routes:** not applicable — the entire app is unauthenticated local-network tooling; this route matches that posture and introduces no new exposure (read-only).
- **Authorisation (own-data only):** not applicable — there is no user/ownership model; all data in the single graph is shared by design.
- **Input validation / sanitisation:** the backend route takes **no** input, so there is no untrusted data reaching the query. On the frontend, the `label` path param is `encodeURIComponent`-encoded on navigation and decoded by React Router; it is only rendered as text (no `dangerouslySetInnerHTML`), so no injection surface.
- **SQL/SPARQL injection prevention:** the SPARQL query is a fully static string literal with no interpolated user input — injection is impossible by construction. (Contrast with `add_fundamental_node.py`, which interpolates URIs; that is out of scope here and unchanged.)
- **CSRF:** not applicable — `GET`, read-only, no state mutation, no cookies/sessions.
- **Sensitive data handling:** none — the response exposes only component labels, counts, and class names already visible elsewhere in the UI; the editor/date fields are fake constants.

## Open questions
1. **Identical fake editor/date defeats two sort modes.** Every record gets the same `"Sergio Mattarella"` / `"2026-05-14T10:32:00"`, so the *Author* and *Last Edit* buttons reorder nothing observable, making two Definition-of-Done checks unverifiable by eye.
   - *Assumption for this plan:* follow the spec literally — hardcode identical values; the sort logic is implemented correctly even if its effect isn't visible yet.
   - *Impact if wrong:* if the reviewer wants those buttons to *demonstrably* reorder, the backend should instead derive deterministic pseudo-fake values per label (e.g. cycle through a small set of names and offset the date by a hash of the label). Low effort, isolated to the transformation step.
2. **Plain vs typed-literal match for `Fundamental_Node`.** The attrib is stored `^^xsd:string`.
   - *Assumption:* use the defensive `FILTER(STR(?attrib) = "Fundamental_Node")` form so the match works regardless of how Virtuoso normalises the literal.
   - *Impact if wrong:* a naive plain-literal match could silently return zero rows on some Virtuoso configurations, making the page perpetually empty despite fundamental nodes existing.
3. **`cadType` of fundamental nodes.** It's unclear whether fundamental nodes are predominantly `CADPart`, `CADAssembly`, or a mix.
   - *Assumption:* show whatever `cadType` the node carries as a neutral badge; no behaviour depends on it.
   - *Impact if wrong:* none functionally — purely a label on the card.
4. **Detail route key.** The route is `/product/:label`, keyed by human label rather than the full metadata URI.
   - *Assumption:* label is unique enough for the stub (it's derived from a unique metadata URI within one namespace).
   - *Impact if wrong:* if two distinct metadata URIs ever produce the same label, the future (non-stub) detail page would be ambiguous; revisit by keying on the encoded metadata URI when the detail page gains real content.

## Definition of done (design review)
- [ ] The SPARQL query matches the `Fundamental_Node` attrib defensively (handles the `^^xsd:string` datatype) and uses `COUNT(DISTINCT ?node)`.
- [ ] The route contract (field names, types, `null` semantics, fake-field injection with `TODO`) is agreed before frontend work begins.
- [ ] The backend handler runs the query in `run_in_threadpool` and distinguishes empty-result (200, `[]`) from failure (500).
- [ ] The frontend fetches via the relative `/api/product-inventory` path (uses the Vite proxy, no hard-coded host).
- [ ] Search/sort are agreed to be client-side derived state with no refetch, sorting on a copy.
- [ ] The red incomplete-card style and the active-sort-button style reuse existing theme tokens/classes where possible; the one new hard-coded colour (red) is acknowledged.
- [ ] The identical-fake-values limitation (Open Question 1) has an explicit decision recorded before implementation.
- [ ] Routing keys, label encoding/decoding, and the no-sidebar-change assumption are confirmed.
