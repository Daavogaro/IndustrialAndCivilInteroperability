# Spec: Cards Page (Product Detail)

## Overview
The Cards Page is the full Product Detail page reached by clicking a card on the Product Inventory. It replaces the current stub (`ProductDetailPage.tsx`) with a three-zone workspace focused on a single Fundamental Node product type. The left column renders `NodeDetails` (the existing STEP assembly/FundamentalNode view with delete/simplify controls) scoped to the product's first RDF instance. The right column holds two vertically stacked collapsible panels: the top panel is a 3D viewer that isolates and centres the product's geometry from the shared GLB; the bottom panel renders `IFCNodeDetails` (the existing IFC class + property-set editor). A single `selectedNodeUri` state, initialised to the product's root URI and updated as the user drills into the hierarchy, drives both `NodeDetails` (left) and `IFCNodeDetails` (bottom right). The page operates entirely on the **first instance** of the Fundamental Node (lowest `x3d:name` integer).

## Depends on
Spec 01 — Product Inventory (complete): the `ProductDetailPage` route `/product/:label` already exists in `App.tsx`; this spec replaces the stub body.

## Routes
- `GET /api/product-hierarchy/{label}` — returns roots + edges + IFC data for the first instance's subtree, in `buildTree()`-compatible format — public (local network only)

## RDF / Database changes
No schema changes. The endpoint issues four read-only SPARQL SELECTs against the existing Virtuoso graph `http://localhost:8890/Elettra2/`.

### Query 1 — Find root node (first instance)
```sparql
PREFIX x3d: <https://www.web3d.org/specifications/X3dOntology4.0#>
PREFIX pre: <http://www.loc.gov/premis/rdf/v3/>
SELECT ?root ?cadType ?metadata ?visible ?display ?dimensions ?attrib ?fileUrl
FROM <http://localhost:8890/Elettra2/>
WHERE {
  ?root x3d:hasMetadata <https://elettra2.0#{label}> .
  ?root x3d:attrib ?a .
  FILTER(STR(?a) = "Fundamental_Node")
  ?root a ?cadType .
  ?root x3d:name ?num .
  OPTIONAL { ?root x3d:visible ?visible . }
  OPTIONAL { ?root x3d:bboxDisplay ?display . }
  OPTIONAL { ?root x3d:bboxSize ?dimensions . }
  OPTIONAL { ?root x3d:attrib ?attrib . }
  OPTIONAL {
    ?root x3d:hasParentX3D ?file .
    ?file a pre:File .
    ?file pre:storedAt ?fileUrl .
  }
  FILTER(STRSTARTS(STR(?cadType), "https://www.web3d.org/specifications/X3dOntology4.0#"))
}
ORDER BY ?num
LIMIT 1
```
The URI returned in `?root` becomes `ROOT_URI` for the three queries below.

### Query 2 — All parent→child edges within the subtree
```sparql
PREFIX x3d: <https://www.web3d.org/specifications/X3dOntology4.0#>
PREFIX pre: <http://www.loc.gov/premis/rdf/v3/>
SELECT ?parent ?child ?cadType ?metadata ?visible ?display ?dimensions ?attrib ?fileUrl
FROM <http://localhost:8890/Elettra2/>
WHERE {
  <ROOT_URI> x3d:children* ?parent .
  ?parent x3d:children ?child .
  ?child a ?cadType .
  ?child x3d:hasMetadata ?metadata .
  OPTIONAL { ?child x3d:visible ?visible . }
  OPTIONAL { ?child x3d:bboxDisplay ?display . }
  OPTIONAL { ?child x3d:bboxSize ?dimensions . }
  OPTIONAL { ?child x3d:attrib ?attrib . }
  OPTIONAL {
    ?child x3d:hasParentX3D ?file .
    ?file a pre:File .
    ?file pre:storedAt ?fileUrl .
  }
  FILTER(STRSTARTS(STR(?cadType), "https://www.web3d.org/specifications/X3dOntology4.0#"))
}
```
`x3d:children*` traverses zero-or-more hops so `?parent` ranges over `ROOT_URI` and all its descendants.

### Query 3 — IFC class data for subtree nodes
```sparql
PREFIX x3d: <https://www.web3d.org/specifications/X3dOntology4.0#>
PREFIX ifc: <https://w3id.org/ifc/IFC4X3_ADD2#>
SELECT ?node ?ifcClass ?predefinedType ?objectType
FROM <http://localhost:8890/Elettra2/>
WHERE {
  { <ROOT_URI> x3d:children* ?node . } UNION { BIND(<ROOT_URI> AS ?node) }
  ?node a ?ifcClass .
  ?node x3d:hasMetadata ?metadata .
  ?node ifc:globalId_IfcRoot ?globalId .
  ?globalId rdf:value ?gidValue .
  OPTIONAL {
    ?node ?p ?predefinedType .
    FILTER(STRSTARTS(STR(?p), "https://w3id.org/ifc/IFC4X3_ADD2#predefinedType_"))
  }
  OPTIONAL {
    ?node ifc:objectType_IfcObject ?label .
    ?label rdf:value ?objectType .
  }
  FILTER(STRSTARTS(STR(?ifcClass), "https://w3id.org/ifc/IFC4X3_ADD2#"))
}
```

### Query 4 — IFC property sets for subtree nodes
Same SPARQL as the `ifcPsetQuery` in `UpdateHierarchyButton.tsx`, scoped with the same `{ ... } UNION { BIND(<ROOT_URI> AS ?node) }` pattern used in Query 3.

### Response shape
```json
{
  "rootUri": "https://elettra2.0#SomePart.1",
  "roots": [
    {
      "uri": "https://elettra2.0#SomePart.1",
      "cadType": "https://www.web3d.org/specifications/X3dOntology4.0#CADAssembly",
      "metadata": "https://elettra2.0#SomePart",
      "visible": "true",
      "display": "false",
      "dimensions": null,
      "attrib": "Fundamental_Node",
      "fileUrl": "/path/to/model.glb"
    }
  ],
  "edges": [
    {
      "parent": "https://elettra2.0#SomePart.1",
      "child": "https://elettra2.0#SubPart.3",
      "cadType": "https://www.web3d.org/specifications/X3dOntology4.0#CADPart",
      "metadata": "https://elettra2.0#SubPart",
      "visible": "true",
      "display": "false",
      "dimensions": "0.12 0.08 0.05",
      "attrib": null,
      "fileUrl": "/path/to/model.glb"
    }
  ],
  "ifcData": [
    { "node": "...", "ifcClass": "...", "predefinedType": "...", "objectType": "..." }
  ],
  "ifcPsetData": [
    { "node": "...", "psetName": "...", "propName": "...", "propValue": "...", "datatype": "..." }
  ]
}
```
- `fileUrl` values have the `file:///` prefix stripped server-side (same as `refreshStepHierarchy`)
- If the label matches no Fundamental Node, return HTTP 404 `{"detail": "Product not found"}`

## Page layout

```
┌────────────────────────────────────────────────────────────┐
│  <Topbar title={label} />                                  │
│  [← Back to Inventory]                                     │
├──────────────────────┬─────────────────────────────────────┤
│  Left (40%)          │  Right (60%)                        │
│                      │  ┌─────────────────────────────────┐│
│  NodeDetails         │  │ [▼] Product Viewer              ││
│  (FundamentalNode /  │  │   ProductGLTFViewer             ││
│   Assembly tabs,     │  │   (collapsible)                 ││
│   delete / simplify) │  └─────────────────────────────────┘│
│                      │  ┌─────────────────────────────────┐│
│                      │  │ [▼] IFC Properties              ││
│                      │  │   IFCNodeDetails                ││
│                      │  │   (collapsible)                 ││
│                      │  └─────────────────────────────────┘│
└──────────────────────┴─────────────────────────────────────┘
```

**CSS skeleton:**
- Outer wrapper: `display: grid; grid-template-rows: auto auto 1fr; height: 100vh; overflow: hidden`
  - Row 1: `<Topbar>`
  - Row 2: back-navigation bar (`← Back to Inventory` button)
  - Row 3: body row — `display: flex; flex-direction: row; min-height: 0`
- Left column: `width: 40%; overflow-y: auto; padding: 10px`
- Right column: `flex: 1; display: flex; flex-direction: column; min-height: 0`

## Left panel — NodeDetails

Render the existing `NodeDetails` component verbatim:

```tsx
<NodeDetails
  uri={selectedNodeUri}
  tree={tree}
  setTree={setTree}
  setNodeUri={setSelectedNodeUri}
  setMessage={setLocalMessage}
  setHoveredUri={setHoveredUri}
/>
```

- `selectedNodeUri` is initialised to `rootUri` once the hierarchy fetch completes
- When `NodeDetails` calls `setNodeUri` (user drills into a child), `selectedNodeUri` updates — both `NodeDetails` and `IFCNodeDetails` (bottom right) react
- `setHoveredUri` drives hover highlighting in the viewer (see below)
- Delete / simplify API calls (`/api/update-deletion`, `/api/update-simplification`) are unchanged — they operate on `metadata`, not the page-level state

## Right column — two collapsible panels

Both panels live in the right column (`flex: 1; display: flex; flex-direction: column`).

### Collapsible panel behaviour
Each panel consists of:
1. **Title bar** — full-width, `cursor: pointer`, shows title + chevron icon (`▼` / `▶`); clicking toggles `isCollapsed` boolean state
2. **Body** — when expanded: `flex: 1; overflow: hidden`; when collapsed: `flex: 0 0 36px; overflow: hidden` (the body content becomes invisible, only the title bar remains)

Space distribution: both expanded → each gets `flex: 1` (equal split); one collapsed → the other's `flex: 1` fills the vacated space automatically. Do **not** use `display: none` on the body — the Three.js canvas must still receive resize events.

### Top panel — Product Viewer

Title: **"Product Viewer"**. Default: expanded.

Body contains `<ProductGLTFViewer productLabel={label} hoveredUri={hoveredUri} />`.

**`ProductGLTFViewer` component** (new file, adapted from `gLTFViewer.tsx`):
- Props: `productLabel: string`, `hoveredUri?: string | null`
- Loads GLB files via the same `POST /api/gltf-upload` call as the original viewer
- Container element id: `"product-viewer-container"` (not `"viewer-container"`) to avoid DOM conflicts
- After each file loads, applies **product isolation**:
  1. Compute `targetName = normalizeName(productLabel + ".1")` using the same `normalizeName` helper from `gLTFViewer.tsx` (strips underscores, dots, spaces, hyphens; lowercases)
  2. Traverse the entire scene; collect all `THREE.Object3D` nodes whose own normalized `userData.name` equals `targetName`, or that have an ancestor with that name — these form the **product set**
  3. Traverse the scene a second time: set `visible = false` on every object that is neither in the product set nor an ancestor of a product-set member (ancestors must stay `visible = true` for Three.js to render their children)
  4. Build a `THREE.Box3` from the product set members and call `focusOnObject` on a proxy `Object3D` positioned at the box centre to centre the camera
- The file-list overlay panel (checkbox list in `gLTFViewer.tsx`) is **omitted**
- All other behaviour is preserved: `OrbitControls`, right-click focus, Escape-to-reset, hover highlight via `applyUriHighlight` driven by the `hoveredUri` prop

### Bottom panel — IFC Properties

Title: **"IFC Properties"**. Default: expanded.

Body contains the existing `IFCNodeDetails` component verbatim:

```tsx
<IFCNodeDetails
  uris={selectedNodeUri ? [selectedNodeUri] : []}
  tree={tree}
  setTree={setTree}
  setMessage={setLocalMessage}
  onClearSelection={() => setSelectedNodeUri(rootUri)}
/>
```

- When `selectedNodeUri` is null (hierarchy not yet loaded), `uris` is `[]` and `IFCNodeDetails` renders its own "No node selected." guard
- `onClearSelection` resets selection back to the product root after the user applies IFC properties

## State owned by ProductDetailPage

```ts
const [tree, setTree]                   // TreeNode[] — product subtree
const [rootUri, setRootUri]             // string | null — URI of the first instance
const [selectedNodeUri, setSelectedNodeUri] // string | null — drives both panels
const [hoveredUri, setHoveredUri]       // string | null — drives viewer highlight
const [loading, setLoading]             // boolean
const [error, setError]                 // string | null
const [localMessage, setLocalMessage]   // { status, text } | null — auto-clears after 8 s
const [viewerCollapsed, setViewerCollapsed]   // boolean
const [ifcCollapsed, setIfcCollapsed]         // boolean
```

`localMessage` is rendered as a slim status bar at the bottom of the right column (same visual style as the sidebar message, scoped to the page — do not propagate to App's global sidebar).

## Components

**Modify:**
- `frontend/src/pages/ProductDetailPage/ProductDetailPage.tsx` — replace stub with three-zone layout

**Create:**
- `frontend/src/pages/ProductDetailPage/useProductHierarchy.ts` — hook: fetches `/api/product-hierarchy/{label}`, calls `buildTree()`, exposes `{ rootUri, tree, setTree, loading, error, refresh }`
- `frontend/src/pages/ProductDetailPage/ProductGLTFViewer.tsx` — adapted viewer with product isolation
- `frontend/src/pages/ProductDetailPage/CollapsiblePanel.tsx` — wrapper with props `title: string`, `children: ReactNode`, `collapsed: boolean`, `onToggle: () => void`
- `backend/api/routes/product_hierarchy.py` — FastAPI router with `GET /product-hierarchy/{label}`

**Do not create** (superseded):
- `InstanceCard.tsx`, `useProductDetail.ts`, `backend/api/routes/product_detail.py`

## Files to change
- `backend/app.py` — import and register `product_hierarchy.router` with prefix `/api`
- `frontend/src/pages/ProductDetailPage/ProductDetailPage.tsx`

## Files to create
- `backend/api/routes/product_hierarchy.py`
- `frontend/src/pages/ProductDetailPage/useProductHierarchy.ts`
- `frontend/src/pages/ProductDetailPage/ProductGLTFViewer.tsx`
- `frontend/src/pages/ProductDetailPage/CollapsiblePanel.tsx`

## New dependencies
No new dependencies.

## Rules for implementation
- The backend runs all four SPARQL queries in a single `run_in_threadpool` call (one Python function that executes them sequentially and assembles the response dict)
- The `label` path parameter is URL-decoded before constructing the metadata URI: `urllib.parse.unquote(label)` → `f"https://elettra2.0#{decoded}"` — never interpolate the raw path string
- `fileUrl` values strip the `file:///` prefix server-side, same as `refreshStepHierarchy`
- `SPARQLWrapper` only — no new libraries
- **Product isolation**: target is `normalizeName(productLabel + ".1")`; the same `normalizeName` function from `gLTFViewer.tsx` must be copied into `ProductGLTFViewer.tsx` unchanged
- **Ancestor visibility**: when hiding non-product nodes, only set `visible = false` on leaf/branch nodes that are entirely outside the product subtree — ancestors of matched nodes stay `visible = true`
- **Camera centering**: after isolation, compute a union `Box3` from all visible product nodes and call `focusOnObject` with a proxy object at the box centre
- **Viewer container id**: `"product-viewer-container"` — not `"viewer-container"`
- **Collapsed panel body**: hide with `overflow: hidden; height: 0` (not `display: none`) so the canvas renderer still fires resize
- **`CollapsiblePanel`** is a pure presentational wrapper — it holds no state; state lives in `ProductDetailPage`
- **`NodeDetails` and `IFCNodeDetails`** are imported and used verbatim without any modification
- **Local message**: `localMessage` auto-clears via `setTimeout` of 8 000 ms in a `useEffect`; rendered as a fixed-height bar at the bottom of the page
- Keep styling consistent: `panel-scroll`, `generalButton`, `var(--background-100)`, `Topbar` component
- No SQLAlchemy or ORMs
- Parameterised queries only — label is URL-decoded and interpolated into SPARQL server-side

## Definition of done
- [ ] Clicking a product card on `/ProductInventory` navigates to `/product/:label` and renders the three-zone layout without errors
- [ ] The `<Topbar>` shows the product label; "← Back to Inventory" returns to the previous page
- [ ] The left panel renders `NodeDetails` rooted at the first instance of the Fundamental Node (FundamentalNode tab active by default)
- [ ] The FundamentalNode tab lists all CADPart descendants with delete/simplify checkboxes
- [ ] Checking delete calls `/api/update-deletion` and the badge appears in the hierarchy
- [ ] Checking simplify calls `/api/update-simplification` and the badge appears in the hierarchy
- [ ] Clicking a child node name in `NodeDetails` drills into that node (updates `selectedNodeUri`); `IFCNodeDetails` updates to show that node's IFC properties
- [ ] The top right panel loads the GLB and displays only the geometry of the product's first instance; all other products/nodes are hidden
- [ ] The camera is automatically centred on the isolated product geometry after load
- [ ] Hovering a row in `NodeDetails` highlights the corresponding mesh in the 3D viewer
- [ ] The bottom right panel shows `IFCNodeDetails` for the currently selected node: IFC Class dropdown, Predefined Type, Userdefined Type, and Property Sets
- [ ] Submitting the IFC form calls `/api/add-ifc-properties` and reflects the updated class/psets in the tree; selection resets to the product root
- [ ] Clicking the "Product Viewer" title bar collapses the top panel; `IFCNodeDetails` expands to fill the space
- [ ] Clicking the "IFC Properties" title bar collapses the bottom panel; the viewer expands to fill the space
- [ ] Both panels can be independently toggled; when both expanded they share the right column equally
- [ ] A loading state is shown while the hierarchy fetch is in progress
- [ ] An error state with a retry button is shown if the backend returns non-2xx
- [ ] Navigating to `/product/NonExistent` shows the error state (backend returns 404)
