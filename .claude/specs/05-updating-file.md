# Spec: Updating File

## Overview
After spec 04 introduced multi-project support, the STEP file replacement pipeline
(`WS /api/ws/update`) has three correctness gaps.

1. **Graph scope**: the SPARQL helpers `existing_nodes()` and `name_and_number_query()`
   query across all Virtuoso named graphs. When two projects share component names this
   causes incorrect instance numbering and silently corrupts the wrong project's triples.

2. **IFC property loss**: `rdf_update_step` inherits only `visible`/`display`/`attrib`
   for new nodes that appear after a replacement. The richer fields already present in
   `ExistingProps` — `ifc_class`, `predefined_type`, `object_type`, and `psets` — are
   ignored, so new instances of an existing component type are stripped of their IFC
   classification and property sets.

3. **Hardcoded author**: `UpdateSTEPModal.tsx` hard-codes the owner as "Davide Avogaro";
   every replacement is attributed to the same person regardless of who performs it.

This spec fixes all three gaps and adds a review workflow: after a replacement the
affected CAD assemblies are flagged in Virtuoso; product cards for those assemblies
are highlighted yellow in the inventory; and a "Mark as Reviewed" action on the
product detail page clears the flags once an engineer has inspected the changes.

## Depends on
Spec 04 (Multiple Project) — relies on `ProjectContext`, `activeProject.graphUri`,
`project_id` in the WebSocket message, and `get_project_folders` from `models.py`.

## Routes

### New routes
- `POST /api/review-changes` — remove change flags from one assembly node — public
  - Body: `{ "metadata_uri": str, "graph": str }`
  - Returns `{ "status": "success" }`

### Modified routes
The existing `WS /api/ws/update` handler remains; its internal call chain is updated.
`GET /api/product-inventory` — add `hasAddedEntities` and `hasRemovedEntities` fields
to the response objects (backend query extended, no signature change).

## Database changes
Two new RDF predicates are introduced under the existing X3D namespace
(`https://www.web3d.org/specifications/X3dOntology4.0#`):
- `x3d:hasAddedEntities` (boolean) — set on a CADAssembly when the replacement added
  one or more direct child entities
- `x3d:hasRemovedEntities` (boolean) — set on a CADAssembly when the replacement
  removed one or more direct child entities

These predicates are not persisted anywhere other than Virtuoso triple store.

## Files to change

### Backend

**`backend/api/services/db_requests/name_and_number.py`**
- Signature → `async def name_and_number_query(graph: str) -> list[NameAndNumber]`
- Add `FROM <{graph}>` between the PREFIX block and SELECT
- No default value for `graph`

**`backend/api/services/db_requests/existing_nodes.py`**
- Signature → `async def existing_nodes(graph: str) -> list[ExistingProps]`
- Add `FROM <{graph}>` to both `base_query` and `psets_query`
- No default value for `graph`

**`backend/api/services/db_requests/substitution_file_query.py`**
- Add `?parentMetadata` to the SELECT and to the GROUP BY clause
- Add the following join inside the WHERE block:
  ```sparql
  OPTIONAL {
    ?s x3d:hasParentCADPart ?parentNode .
    ?parentNode x3d:hasMetadata ?parentMetadata .
  }
  ```
- Add `parentMetadata: str | None` to the `NodeToSubstitute` TypedDict
- In `convert_sparql_results`, populate it as
  `binding.get("parentMetadata", {}).get("value")`

**`backend/api/services/db_requests/updatingSTEP/gltf_update_STEP.py`**
- Thread `graph` through to `name_and_number_query(graph)` (currently called without
  args at line 257)
- `return_gltf_hierarchy` returns `scenes_data` today; change the return type to a
  named tuple / dict:
  ```python
  return {
      "scenes": scenes_data,
      "parents_with_removals": parents_with_removals,   # set[str] — parent metadata URIs
  }
  ```
- Before calling `delete_remaining_nodes_sparql`, collect `parents_with_removals`:
  a set of `item["parentMetadata"]` values for every `NodeToSubstitute` entry that
  still has remaining numbers (i.e., nodes about to be deleted). Exclude `None` values.

**`backend/api/services/db_requests/updatingSTEP/RDF_update_STEP.py`**
- Update the local `ExistingProps` TypedDict to mirror the canonical one in
  `RDF_conversion.py`: add `ifc_class: str | None`, `predefined_type: str | None`,
  `object_type: str | None`, `psets: dict | None`
- Add `parents_with_removals: set[str]` parameter to `rdf_update_step`
- Import the IFC, EXPRESS namespaces already used in `RDF_conversion.py`
  (`IFC_NAMESPACE`, `EXPRESS_NAMESPACE`) from `models.py`
- In `add_node`, when `old_node is None` and `existing_prop` is found, add the same
  IFC property block that `RDF_conversion.py` emits for new nodes:
  - `rdf:type IFC_NAMESPACE[ifc_class]` if `ifc_class` is set
  - `predefinedType_…` triple if `predefined_type` is set
  - `objectType_IfcObject` sub-resource if `object_type` is set
  - Full pset reconstruction loop (same pattern as `RDF_conversion.py` lines 169–230)
  - Do **not** generate a GUID for the new instance; leave GUID and
    `ifc:name_IfcRoot` absent — the user assigns them via the IFC property form
- Track additions: maintain a `parents_with_additions: set[str]` local set inside
  `rdf_update_step`. When `add_node` fires with `old_node is None` and
  `parent_uri is not None`, resolve the parent's metadata label
  (`parent_uri.split("#")[-1].rsplit(".", 1)[0]`) and add it to the set.
- After the recursion loop, emit change-flag triples for each collected label:
  ```python
  for label in parents_with_additions:
      meta_uri = GRAPH_NAMESPACE[label]
      g.add((meta_uri, X3D_NAMESPACE.hasAddedEntities, Literal(True, datatype=XSD_NAMESPACE.boolean)))
  for label in parents_with_removals:
      meta_uri = GRAPH_NAMESPACE[label]
      g.add((meta_uri, X3D_NAMESPACE.hasRemovedEntities, Literal(True, datatype=XSD_NAMESPACE.boolean)))
  ```

**`backend/api/routes/update_STEP.py`**
- Change `exist_nodes = await existing_nodes()` →
  `exist_nodes = await existing_nodes(graph_name)`
- Unpack the new dict returned by `return_gltf_hierarchy`:
  ```python
  result = await return_gltf_hierarchy(...)
  hierarchy = result["scenes"]
  parents_with_removals = result["parents_with_removals"]
  ```
- Pass `parents_with_removals` to `rdf_update_step(..., parents_with_removals=parents_with_removals)`

**`backend/api/routes/product_inventory.py`**
- Extend `_run_query` to also select the change flags:
  ```sparql
  (MAX(IF(BOUND(?hasAdded)   && ?hasAdded   = true, 1, 0)) AS ?hasAddedEntities)
  (MAX(IF(BOUND(?hasRemoved) && ?hasRemoved = true, 1, 0)) AS ?hasRemovedEntities)
  ```
  with:
  ```sparql
  OPTIONAL { ?node x3d:hasAddedEntities   ?hasAdded   }
  OPTIONAL { ?node x3d:hasRemovedEntities ?hasRemoved }
  ```
- In `_transform`, populate `"hasAddedEntities": bool(int(b.get(..., {}).get("value", 0)))`
  and `"hasRemovedEntities"` accordingly

**`backend/app.py`**
- Add `from api.routes import review_changes` and
  `app.include_router(review_changes.router, prefix="/api")`

### Frontend

**`frontend/src/pages/UpdateFilesPage/UpdateSTEPModal.tsx`**
- Remove `const ownerFirstName = "Davide"` and `const ownerLastName = "Avogaro"`
- Add `const [ownerFirstName, setOwnerFirstName] = useState("")` and
  `const [ownerLastName, setOwnerLastName] = useState("")`
- Render two `<input type="text">` fields (First Name, Last Name) before the file
  picker; style consistent with the dialog (white text, same padding)
- Upload button `disabled` → `!file || uploading || !ownerFirstName.trim() || !ownerLastName.trim()`
- Reset both fields to `""` when Cancel is clicked

**`frontend/src/pages/InventoryProductPage/useProductInventory.ts`**
- Add `hasAddedEntities: boolean` and `hasRemovedEntities: boolean` to `InventoryItem`

**`frontend/src/pages/InventoryProductPage/ProductCard.tsx`**
- Accept the two new boolean props (they flow through from `InventoryItem` via
  `type ProductCardProps = InventoryItem`)
- Derive `const hasChanges = hasAddedEntities || hasRemovedEntities`
- When `hasChanges` is true apply a yellow warning background; when `incomplete` is
  also true the red incomplete style takes priority (keep the existing precedence):
  ```ts
  ...(hasChanges && !incomplete ? { backgroundColor: "#b8860b", color: "white" } : {}),
  ```
- Render a warning chip below the `cadType` badge when `hasChanges` is true:
  ```tsx
  {hasChanges && (
    <span style={{ ... backgroundColor: "rgba(0,0,0,0.25)", ... }}>
      {hasAddedEntities && hasRemovedEntities
        ? "⚠ Added & Removed Entities"
        : hasAddedEntities
        ? "⚠ Added Entities"
        : "⚠ Removed Entities"}
    </span>
  )}
  ```

**`frontend/src/pages/ProductDetailPage/ProductDetailPage.tsx`**
- After `rootUri` is resolved, fetch the change flags for the root node with a
  one-shot SPARQL call (use `fetchQuery` or a direct `fetch /api/sparql-query`):
  ```sparql
  PREFIX x3d: <https://www.web3d.org/specifications/X3dOntology4.0#>
  SELECT ?hasAdded ?hasRemoved
  FROM <{graphUri}>
  WHERE {
    OPTIONAL { <{rootMetadataUri}> x3d:hasAddedEntities   ?hasAdded   }
    OPTIONAL { <{rootMetadataUri}> x3d:hasRemovedEntities ?hasRemoved }
  }
  ```
  Store results in `const [changeFlags, setChangeFlags] = useState<{added: boolean, removed: boolean}>({added: false, removed: false})`
- In Row 2 (navigation row), when `changeFlags.added || changeFlags.removed`, render a
  **"Mark as Reviewed"** `<span className="generalButton">` alongside the existing
  back-navigation buttons
- Clicking it calls `POST /api/review-changes` with
  `{ metadata_uri: rootMetadataUri, graph: activeProject.graphUri }`; on success
  sets `changeFlags` to `{added: false, removed: false}` and calls `refresh()`
- The `rootMetadataUri` is the metadata URI of the label, i.e.
  `"https://elettra2.0#" + label`

## Files to create

**`backend/api/routes/review_changes.py`**
- `POST /api/review-changes` FastAPI route
- Pydantic body: `class ReviewChangesRequest(BaseModel): metadata_uri: str; graph: str`
- Call `assert_known_graph(graph)` (import from `projects.py`)
- Issue two SPARQL DELETE statements via `requests.post(VIRTUOSO_URL, data={"update": ...})`:
  ```sparql
  DELETE FROM <{graph}> { <{metadata_uri}> x3d:hasAddedEntities   ?v }
  WHERE      { <{metadata_uri}> x3d:hasAddedEntities   ?v }
  ```
  ```sparql
  DELETE FROM <{graph}> { <{metadata_uri}> x3d:hasRemovedEntities ?v }
  WHERE      { <{metadata_uri}> x3d:hasRemovedEntities ?v }
  ```
- Return `{"status": "success"}` on HTTP 200; raise `HTTPException(404)` if
  `assert_known_graph` throws; raise `HTTPException(500)` for SPARQL errors
- No SQLAlchemy or ORMs; no raw user input interpolated into SPARQL — `metadata_uri`
  must be validated to start with the known namespace prefix (`https://elettra2.0#`)
  before being interpolated; raise `HTTPException(400)` otherwise

## New dependencies
No new Python packages. No new npm packages.

## Rules for implementation

### name_and_number.py / existing_nodes.py
- No default value for `graph` — callers must pass it explicitly

### substitution_file_query.py
- `parentMetadata` is `None` for root-level nodes (no `x3d:hasParentCADPart` triple);
  the collection step in `gltf_update_STEP.py` must skip `None` entries

### RDF_update_STEP.py — IFC property inheritance
- Only inherit `ifc_class`, `predefined_type`, `object_type`, `psets` when
  `existing_prop` is not None **and** `old_node is None` (new nodes only)
- Do not generate a new IFC GUID; leave `ifc:globalId_IfcRoot` absent for new
  instances — the user must assign it manually via the IFC property form
- The pset reconstruction follows the same pattern as `RDF_conversion.py`:
  create fresh URI resources keyed by `label + pset_name + prop_name` using
  `GRAPH_NAMESPACE`; do not reuse existing pset URIs

### RDF_update_STEP.py — change-flag emission
- The parent label is derived from the `parent_uri` string, not from a Virtuoso query;
  the URI format is always `https://elettra2.0#{Label}.{Number}` so
  `parent_uri.split("#")[-1].rsplit(".", 1)[0]` gives the label
- Flags are emitted on the **metadata URI** (`GRAPH_NAMESPACE[label]`), not on the
  individual node URI (`GRAPH_NAMESPACE["Label.3"]`), so the product inventory
  query can find them by joining through `x3d:hasMetadata`
- Only emit a flag when there is at least one affected entity; do not emit
  `hasAddedEntities false` or `hasRemovedEntities false`

### review_changes.py
- Validate `metadata_uri` starts with `"https://elettra2.0#"` before interpolating
  into SPARQL; return HTTP 400 otherwise
- Use `requests.post(VIRTUOSO_URL, data={"update": ...})` (same pattern as
  `projects.py` for the DROP GRAPH call); run in `run_in_threadpool`

### General
- No SQLAlchemy or ORMs
- Parameterised queries only — graph URI always originates from `projects.json`

## Definition of done

### Graph scoping
- [ ] Uploading a replacement STEP file in Project A does not affect node numbering
      in Project B (verify via SPARQL endpoint)
- [ ] `existing_nodes()` or `name_and_number_query()` called without `graph` raises
      `TypeError` (no default value)

### IFC property inheritance
- [ ] Replacing a STEP file that adds a new instance of an existing component type
      (e.g., a fourth bolt) results in the new node carrying the same `rdf:type`
      IFC class as the other instances of that label
- [ ] `predefined_type` and `object_type` are likewise inherited for the new instance
- [ ] No `ifc:globalId_IfcRoot` triple is created for the new instance automatically

### Author fields
- [ ] The Update modal shows First Name and Last Name inputs above the file picker
- [ ] The Upload button is disabled until both name fields are filled and a `.stp`
      file is selected
- [ ] After a successful update, `prov:wasAttributedTo` triples reflect the typed
      name, not "Davide Avogaro"
- [ ] Cancelling clears both name fields

### Change-flag emission
- [ ] Replacing a STEP file that removes one component from an assembly results in
      `x3d:hasRemovedEntities true` on that assembly's metadata URI in Virtuoso
- [ ] Replacing a STEP file that adds one component to an assembly results in
      `x3d:hasAddedEntities true` on that assembly's metadata URI
- [ ] Replacing a STEP file with no structural changes emits neither flag
- [ ] After a replacement where both additions and removals occur, both flags are
      present on the affected assemblies

### Product card highlighting
- [ ] A product card for an assembly with `hasAddedEntities = true` displays a yellow
      background and the "⚠ Added Entities" chip
- [ ] A product card for an assembly with `hasRemovedEntities = true` displays a yellow
      background and the "⚠ Removed Entities" chip
- [ ] The red "incomplete" style (no IFC class) takes visual priority over yellow
- [ ] Cards without change flags display their normal style

### Review workflow
- [ ] Opening the ProductDetailPage for a flagged assembly shows a
      "Mark as Reviewed" button in the navigation row
- [ ] Clicking "Mark as Reviewed" calls `POST /api/review-changes`; on success
      the button disappears and the product card returns to its normal style on
      next inventory load
- [ ] `POST /api/review-changes` with a `metadata_uri` that does not start with
      `"https://elettra2.0#"` returns HTTP 400
- [ ] `python backend/run.py` starts without import errors after all changes
