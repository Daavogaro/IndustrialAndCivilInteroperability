# Spec: Product Inventory

## Overview
The Product Inventory page presents a card-based catalog of every unique component type present in the Virtuoso RDF graph. Components are grouped by their `MetadataString` identity — the shared label stripped of the per-instance `.N` suffix. Each card shows the component name, instance count, IFC class (if assigned), the last editor, and the last edit date. Cards with a missing IFC class are highlighted in red to flag incomplete metadata. Clicking a card navigates to a dedicated product detail page (stub for now). A search bar and sort controls allow quick filtering and ordering of the catalog.

## Depends on
No strict functional predecessor — the page is useful as soon as at least one STEP file has been imported and its RDF triples are in Virtuoso.

## Routes
- `GET /api/product-inventory` — returns a JSON array of component-type records (label, instance count, dimensions, IFC class, CAD type) — public (local network only)

## RDF / Database changes
No schema changes. The endpoint issues a read-only SPARQL SELECT against the existing Virtuoso graph `http://localhost:8890/Elettra2/`.

Only **Fundamental Nodes** are shown in the inventory. A Fundamental Node is a node that carries the RDF triple `x3d:attrib "Fundamental_Node"` (set via the UI on the STEP Hierarchy page).

SPARQL query to run server-side:
```sparql
PREFIX x3d: <https://www.web3d.org/specifications/X3dOntology4.0#>
SELECT ?metadata
       (COUNT(?node) AS ?count)
       (SAMPLE(?cadType) AS ?cadType)
       (SAMPLE(?ifcClass) AS ?ifcClass)
FROM <http://localhost:8890/Elettra2/>
WHERE {
  ?node x3d:hasMetadata ?metadata .
  ?node x3d:attrib "Fundamental_Node" .
  ?node a ?cadType .
  FILTER(STRSTARTS(STR(?cadType), "https://www.web3d.org/specifications/X3dOntology4.0#"))
  OPTIONAL {
    ?node a ?ifcClass .
    FILTER(STRSTARTS(STR(?ifcClass), "https://w3id.org/ifc/IFC4X3_ADD2#"))
  }
}
GROUP BY ?metadata
ORDER BY DESC(?count)
```

Response shape per record:
```json
{
  "label": "SomePart",
  "metadata": "https://elettra2.0#SomePart",
  "count": 4,
  "cadType": "CADPart",
  "ifcClass": "IfcBeam",
  "lastEditor": "Sergio Mattarella",
  "lastEditDate": "2026-05-14T10:32:00"
}
```
- `label` = last segment of `metadata` URI after `#`
- `cadType` = last segment of the X3D type URI after `#` (`CADPart` or `CADAssembly`)
- `ifcClass` is `null` when absent
- `lastEditor` and `lastEditDate` are hardcoded fake values for now (`"Sergio Mattarella"` and `"2026-05-14T10:32:00"`); the backend injects them into every record until real provenance tracking is implemented

## Components

**Create:**
- `frontend/src/pages/InventoryProductPage/useProductInventory.ts` — custom hook that fetches `/api/product-inventory` and exposes `{ items, loading, error, refresh }`
- `frontend/src/pages/InventoryProductPage/ProductCard.tsx` — single card component; red background when `ifcClass` is null
- `frontend/src/pages/ProductDetailPage/ProductDetailPage.tsx` — stub detail page reached by clicking a card; shows the product label as a title and a "coming soon" placeholder

**Modify:**
- `frontend/src/pages/InventoryProductPage/InventoryProductPage.tsx` — replace stub with: search bar + sort controls + card grid + loading/error/empty states
- `frontend/src/App.tsx` — add route `/product/:label` → `<ProductDetailPage>`

## Files to change
- `backend/app.py` — import and register `product_inventory.router` with prefix `/api`
- `frontend/src/pages/InventoryProductPage/InventoryProductPage.tsx`
- `frontend/src/App.tsx`

## Files to create
- `backend/api/routes/product_inventory.py` — FastAPI router with `GET /product-inventory`
- `frontend/src/pages/InventoryProductPage/useProductInventory.ts`
- `frontend/src/pages/InventoryProductPage/ProductCard.tsx`
- `frontend/src/pages/ProductDetailPage/ProductDetailPage.tsx`

## New dependencies
No new dependencies.

## Rules for implementation
- The backend route uses `SPARQLWrapper` exactly as in `sparql_query.py` — no new libraries
- Run the SPARQL query in `run_in_threadpool` (same pattern as `sparql_query.py`) to avoid blocking the event loop
- The `label` field is derived server-side by splitting the metadata URI on `#` and taking the last segment; never sent as a raw URI to the frontend
- The `cadType` field is derived the same way from the X3D type URI
- `lastEditor` and `lastEditDate` are injected as hardcoded constants in the backend response; add a `TODO` comment marking them for replacement when provenance is tracked in RDF
- **Card layout:** display cards in a responsive CSS grid (e.g. `repeat(auto-fill, minmax(260px, 1fr))`)
- **Card content:** component name (bold, large), instance count, CAD type badge, IFC class (or "—" if absent), last editor name, last edit date formatted as `DD/MM/YYYY HH:mm`
- **Scope:** only Fundamental Nodes (`x3d:attrib "Fundamental_Node"`) appear in the inventory; ordinary CADPart/CADAssembly nodes are excluded
- **Card status colour:** if `ifcClass` is `null`, card background is red (`#c0392b` or similar strong red with white text) to flag missing metadata; otherwise use `var(--background-100)`
- **Search bar:** filters cards client-side on the `label` field, case-insensitive substring match; no backend call on input
- **Sort controls:** four buttons — *Name* (alphabetical by `label`), *Last Edit* (descending by `lastEditDate`), *Status* (incomplete / red cards first, then complete), *Author* (alphabetical by `lastEditor`); only one active at a time, default sort is *Name*; active button is visually distinguished (e.g. `generalButton` with an active state)
- **Navigation:** clicking a card navigates to `/product/:label` using `react-router-dom` `<Link>` or `useNavigate`
- **Product detail page:** stub — shows `<Topbar title={label} />` and a `<p>Product detail coming soon.</p>` paragraph; reads the `label` param from the URL with `useParams`
- Prefer the dedicated `/api/product-inventory` route over the generic SPARQL endpoint from the frontend
- No SQLAlchemy or ORMs
- Parameterised queries only (the SPARQL query has no user input, so this is satisfied by construction)
- Keep styling consistent with the rest of the app: `panel-scroll`, `generalButton`, `var(--background-100)` CSS variables, `Topbar` component at the top

## Definition of done
- [ ] Navigating to `/ProductInventory` via the sidebar renders a card grid without errors
- [ ] Only Fundamental Nodes appear as cards (non-fundamental nodes are excluded)
- [ ] Each card shows the component name, instance count, CAD type, IFC class (or "—"), last editor ("Sergio Mattarella"), and formatted last edit date
- [ ] Cards with no IFC class have a red background with white text; cards with an IFC class use the default background
- [ ] Typing in the search bar filters cards live by name; clearing it restores all cards
- [ ] The *Name* sort button orders cards alphabetically by label
- [ ] The *Last Edit* sort button orders cards with most-recently-edited first
- [ ] The *Status* sort button places red (incomplete) cards before complete cards
- [ ] The *Author* sort button orders cards alphabetically by last editor name
- [ ] Only one sort button is visually active at a time
- [ ] Clicking a card navigates to `/product/:label`
- [ ] The product detail page at `/product/:label` renders the label in the topbar and a "coming soon" message
- [ ] A loading state is shown while the inventory fetch is in progress
- [ ] An error message is shown if the backend returns a non-2xx response or is unreachable
- [ ] The page renders an empty-state message when Virtuoso has no triples (no STEP imported yet)
