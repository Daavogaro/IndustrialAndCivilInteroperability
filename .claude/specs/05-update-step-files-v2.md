# Spec: Update Step Files V2

## Overview
The current "Update Files" flow re-converts a STEP file with the external Mayo CLI and re-imports its hierarchy, but it does not tell the user **what changed** between the old and new version of the model. This feature reworks the update pipeline so that (1) the uploaded STEP file is converted with the in-process OCC converter (`export_gltf` in `backend/api/services/importing_STEP/occ_converter.py`) instead of Mayo, exactly like the main upload pipeline; and (2) after re-import, the platform compares the **pattern** of every **fundamental node** (`x3d:CADAssembly` carrying `x3d:attrib "Fundamental_Node"`) between the old and new versions. The *pattern* is the labelled hierarchy inside the fundamental node's assembly — nodes are matched by their metadata **label** (e.g. `NodeXX.1` and `NodeXX.2` are the same node type; the instance number is ignored), and the hierarchy *under* any nested fundamental nodes is **excluded**. If the old and new patterns are identical the fundamental node is **unchanged**, and the new nodes reuse the old instance names. If the patterns differ the fundamental node is **changed**: only the nodes that do **not** belong to the shared pattern receive new names, and the changed `x3d:CADAssembly` instance gets the data properties `x3d:hasRemovedEntities` (one per node that disappeared) and/or `x3d:hasAddedEntities` (one per new node). Because the same product can live in several files and several projects, this obsolescence marker is **propagated** to every other instance of that product across all files and all project graphs, so users are warned that their un-updated copies are now stale. In the Product Inventory, any product that is obsolete in any file turns **yellow**; opening its detail page shows which file(s) must be updated and offers a **"Mark as reviewed"** action that removes the markers (for that product in the active project) and returns the card to normal.

## Depends on
- **Spec 01 – Product Inventory** (`GET /api/product-inventory`, the inventory card grid, `useProductInventory`, `ProductCard`).
- **Spec 02 – Cards Page** (product detail page / `GET /api/product-hierarchy/{label}`, `useProductHierarchy`, `buildTree`).
- **Spec 03 – Change GLTF Converter** (provides `export_gltf` in `occ_converter.py`; `pythonocc-core` already in `requirements.txt`).
- **Spec 04 – Multiple Project** (named graphs per project, `projects.json`, `assert_known_graph`, the `_read_projects()` helper used here to enumerate project graphs for cross-project propagation).

## User instructions
- When the user uploads a new file in the update flow, convert it with the same OCC conversion as `backend/api/services/importing_STEP/occ_converter.py` (`export_gltf`), not Mayo.
- After conversion, detect which nodes changed and which did not, comparing the new hierarchy against the previous state.
- The comparison for a fundamental node covers only the hierarchy of nodes **inside its assembly, excluding the hierarchy under any nested (child) fundamental nodes**.
- Compare the old and new hierarchies by **pattern**: two nodes are "the same" when their metadata **label** matches — `NodeXX.1` and `NodeXX.2` are the same node type, the instance number is **not** considered. The pattern is the labelled assembly hierarchy with instance numbers ignored.
- If the old and new patterns are **exactly the same**, the product is **unchanged**: reuse the old names (with their instance numbers) for the new nodes, and attach no markers.
- If the pattern **changed**, give a **new name (new instance) only to the nodes that do not belong to the shared pattern**; nodes that belong to the pattern keep their old names.
- For each changed fundamental-node assembly, if at least one node of the old pattern has no counterpart in the new pattern, attach `x3d:hasRemovedEntities` to that `x3d:CADAssembly` node (one per missing node); if at least one new node is not part of the old pattern, attach `x3d:hasAddedEntities` (one per added node). Both can be present at once.
- If a fundamental node's assembly is unchanged → leave it as is. If it changed → its Product Inventory card turns **yellow**, and the detail page gains a **"Mark as reviewed"** button that deletes `x3d:hasRemovedEntities` and `x3d:hasAddedEntities`, making the card normal again.
- "Mark as reviewed" is scoped to the product in the **active project**, and clears the markers for that product **all at once**; a message on the detail page tells the user which file(s) need updating.
- The obsolescence applies **per product, per file, per project**: updating file X does not update file Y, so the same product in file Y (and in other projects) must also be flagged obsolete and shown as a yellow card. Propagate the markers to every other instance of the changed product across all files and all project graphs.
- If any node inside a fundamental node's assembly changed (excluding the hierarchy under nested fundamental nodes), **do not carry over / save the IFC properties of that (old) fundamental node** during re-import.

## Routes

### New routes
- `POST /api/mark-reviewed` — remove `x3d:hasRemovedEntities` and `x3d:hasAddedEntities` from every node of a given product (`metadata`) in a given project graph; returns `{ "status": "success" }` — public (local network only)

### Modified routes
- `WS /api/ws/update` (`backend/api/routes/update_STEP.py`) — convert with OCC instead of Mayo; snapshot the pre-update fundamental-node assemblies; compute the per-fundamental-node diff after re-import; write the add/remove markers on changed fundamental nodes; propagate the markers across files/graphs; suppress IFC-property reuse for changed fundamental nodes.
- `GET /api/product-inventory` (`backend/api/routes/product_inventory.py`) — add a boolean `obsolete` field per record (true if any instance of that metadata in the graph carries `x3d:hasRemovedEntities` or `x3d:hasAddedEntities`).
- `GET /api/product-hierarchy/{label}` (`backend/api/routes/product_hierarchy.py`) — add `obsolete` (bool), `obsoleteFiles` (list of filenames whose instances of this product are obsolete), `addedEntities` (list of strings) and `removedEntities` (list of strings) to the response.

## Database changes
No Virtuoso schema migration. Two new **data properties** are introduced in the existing X3D namespace (`https://www.web3d.org/specifications/X3dOntology4.0#`, prefix `x3d:`):

- `x3d:hasRemovedEntities` — `owl:DatatypeProperty`, `xsd:string`. One triple per node of the **old** pattern (recorded by its old `label.N` instance name) that has no counterpart in the new pattern (matching done by label, ignoring instance numbers).
- `x3d:hasAddedEntities` — `owl:DatatypeProperty`, `xsd:string`. One triple per node of the **new** pattern (recorded by its newly assigned `label.N` instance name) that has no counterpart in the old pattern.

Both are attached to the `x3d:CADAssembly` node URI of the changed fundamental-node instance, and to every other instance of the same product (matched by the graph-independent `x3d:hasMetadata` URI, e.g. `https://elettra2.0#<label>`) across all files in all known project graphs from `projects.json`.

No changes to `projects.json` structure.

## Templates
This is a React/TS frontend (no server-side templates). Components instead:

- **Create:**
  - `frontend/src/pages/ProductDetailPage/ObsolescenceBanner.tsx` — banner shown on the product detail page when the product is obsolete: lists the file(s) that need updating, the added/removed entity names, and a **"Mark as reviewed"** button.
- **Modify:**
  - `frontend/src/pages/InventoryProductPage/ProductCard.tsx` — yellow card styling when `obsolete` is true (takes visual precedence over the red "missing IFC class" style).
  - `frontend/src/pages/InventoryProductPage/useProductInventory.ts` — add `obsolete: boolean` to `InventoryItem`.
  - `frontend/src/pages/InventoryProductPage/InventoryProductPage.tsx` — extend the existing *Status* sort so obsolete (yellow) cards sort first; no new controls required.
  - `frontend/src/pages/ProductDetailPage/ProductDetailPage.tsx` — render `<ObsolescenceBanner>` above the body when obsolete; wire the "Mark as reviewed" action to refresh hierarchy + inventory afterwards.
  - `frontend/src/pages/ProductDetailPage/useProductHierarchy.ts` — capture and expose `obsolete`, `obsoleteFiles`, `addedEntities`, `removedEntities` from the hierarchy response.

## Files to change
- `backend/api/routes/update_STEP.py`
- `backend/api/services/db_requests/updatingSTEP/RDF_update_STEP.py`
- `backend/api/services/db_requests/updatingSTEP/gltf_update_STEP.py`
- `backend/api/routes/product_inventory.py`
- `backend/api/routes/product_hierarchy.py`
- `backend/app.py`
- `frontend/src/pages/InventoryProductPage/ProductCard.tsx`
- `frontend/src/pages/InventoryProductPage/useProductInventory.ts`
- `frontend/src/pages/InventoryProductPage/InventoryProductPage.tsx`
- `frontend/src/pages/ProductDetailPage/ProductDetailPage.tsx`
- `frontend/src/pages/ProductDetailPage/useProductHierarchy.ts`

## Files to create
- `backend/api/services/db_requests/updatingSTEP/diff_fundamental_nodes.py` — snapshot old fundamental-node assemblies from the DB, compute per-fundamental-node added/removed instance sets against the freshly parsed hierarchy, and build/run the SPARQL `INSERT` queries that write and propagate the markers across all known graphs.
- `backend/api/routes/mark_reviewed.py` — `POST /api/mark-reviewed`.
- `frontend/src/pages/ProductDetailPage/ObsolescenceBanner.tsx`

## New dependencies
No new dependencies. `pythonocc-core` (for `export_gltf`) and `SPARQLWrapper`/`requests`/`rdflib` are already present.

## Rules for implementation

### General
- No SQLAlchemy or ORMs.
- Parameterised queries only — graph URIs always originate from `projects.json` on the server side (validate with `assert_known_graph`), never from raw client input concatenated blindly; metadata/entity literals embedded in SPARQL must be controlled, server-derived values.
- Keep styling consistent with the rest of the app: `panel-scroll`, `generalButton`, `var(--background-100)`, `Topbar`, and the existing CSS variables.

### `update_STEP.py` (`WS /api/ws/update`)
- Replace `from ..services.importing_STEP.mayo import convert_with_mayo` usage with `from ..services.importing_STEP.occ_converter import export_gltf`. Replace the `await run_in_threadpool(convert_with_mayo, input_file, output_file)` call with `await run_in_threadpool(export_gltf, input_file, output_file)` (the function appends `.gltf` and writes the sibling `.bin` itself). Update the success status text from "Conversion Done with Mayo" to "Conversion Done".
- **Order of operations matters.** Before `return_gltf_hierarchy` runs (it deletes/renumbers old nodes via the substitution mechanism), snapshot the old fundamental-node assemblies for this file from the active graph. Then parse the new hierarchy, compute the diff, import the new RDF, and finally write + propagate the markers.
- A **fundamental node** is a node with `x3d:attrib "Fundamental_Node"`. Its **assembly** = all `x3d:children*` descendants, pruned so that traversal stops at (but still includes) any descendant that is itself a fundamental node — i.e. exclude the hierarchy *under* nested fundamental nodes.
- Build the **pattern** of each fundamental node's assembly: the labelled subtree keyed by metadata **label** (the name without the trailing `.N`; instance numbers ignored), pruned at nested fundamental-node boundaries. Compare the old snapshot's pattern with the new hierarchy's pattern **structurally** (`NodeXX.1` ≡ `NodeXX.2`).
- If the patterns are **identical** → the fundamental node is **unchanged**: the new nodes must reuse the old instance names (`label.N`); no markers, no renumbering.
- If the patterns **differ** → the fundamental node is **changed**: nodes that belong to the shared pattern keep their old instance names; nodes outside the shared pattern get **new** instance names. Add one `x3d:hasRemovedEntities "<old label.N>"^^xsd:string` per old-pattern node with no counterpart, and one `x3d:hasAddedEntities "<new label.N>"^^xsd:string` per new-pattern node with no counterpart, on that `x3d:CADAssembly` instance URI.
- This matched-vs-new naming builds on the existing substitution/renumbering machinery in `gltf_update_STEP.py` (`build_node_hierarchy` consuming `nodes_to_substitute` from `substitution_file_query`, plus `delete_remaining_nodes_sparql`): reused numbers correspond to matched pattern nodes, freshly assigned numbers to added nodes, and deleted leftover numbers to removed nodes. The diff is derived from this correspondence rather than from comparing raw instance numbers.
- **Propagation:** for each changed product (its `x3d:hasMetadata` URI), enumerate every known graph via `_read_projects()` and, for every fundamental-node instance of that metadata in each graph (across all files), INSERT the same `x3d:hasRemovedEntities` / `x3d:hasAddedEntities` markers. Re-inserting identical triples must be idempotent.
- Declare `x3d:hasRemovedEntities` and `x3d:hasAddedEntities` as `owl:DatatypeProperty` in the emitted graph, matching how the other `x3d:` data properties are declared in `RDF_conversion.py` / `RDF_update_STEP.py`.

### `RDF_update_STEP.py` (re-import RDF generation)
- The re-import must **preserve** existing per-node properties (visibility, `bboxDisplay`, `attrib` including `Fundamental_Node`, and IFC metadata) for nodes that persist — i.e. reuse `existing_nodes` the same way `convert_hierarchy_in_rdf` does, including the IFC class / predefined type / object type / property-set reuse block.
- **IFC suppression for changed fundamental nodes:** accept the set of changed fundamental-node labels (derived from the diff) and, for any node that is a fundamental node whose assembly changed, **omit** the IFC-property reuse entirely (no `ifc:` class, no GUID, no name label, no predefined type, no object type, no property sets). Non-fundamental nodes and unchanged fundamental nodes keep their reused IFC metadata.
- Do not save the old IFC properties of a changed fundamental node anywhere; they are intentionally dropped so the user must re-enter them.

### `diff_fundamental_nodes.py`
- Provide a function to read the current (pre-update) fundamental-node assemblies for a given file URL + graph from Virtuoso, returning a mapping `fundamental instance URI → { metadata, pattern }`, where `pattern` is the labelled assembly subtree (nodes keyed by metadata **label**, instance numbers ignored), honouring the nested-fundamental-node boundary. Keep the old instance names alongside the labels so removed entities can be reported as `label.N`.
- Provide a function to compute the new assemblies' patterns from the parsed `GeometryNode` hierarchy with the same boundary and label-keying rule.
- Provide a function that compares an old pattern with a new pattern **structurally** (matching by label, ignoring instance numbers) and returns, per fundamental node: whether it changed, the removed nodes (old `label.N`) and the added nodes (new `label.N`). A fundamental node is unchanged iff the two patterns are identical.
- Provide a function that, given the diff (per changed fundamental node: metadata, added list, removed list), builds and executes the local marker INSERT and the cross-graph propagation INSERTs using `requests.post(VIRTUOSO_URL, data={"update": ...})` (same pattern as `add_fundamental_node.py` / `update_deletion.py`), looping over graphs from `_read_projects()`.
- Run all blocking SPARQL work in `run_in_threadpool` from the WebSocket handler (do not block the event loop), consistent with the rest of `update_STEP.py`.

### `gltf_update_STEP.py` (naming / number reuse)
- Ensure the instance-number assignment in `build_node_hierarchy` follows the pattern rule: nodes that belong to the shared pattern reuse their old instance numbers (via `nodes_to_substitute`), and only nodes that are **not** part of the pattern receive new numbers. Leftover old numbers (removed nodes) continue to be deleted via `delete_remaining_nodes_sparql`.
- Expose enough information (which numbers were reused vs newly assigned vs deleted, per fundamental-node assembly) for `diff_fundamental_nodes.py` / `update_STEP.py` to derive the added/removed entity lists without re-querying, or document the query path the diff module uses instead.

### `mark_reviewed.py` (`POST /api/mark-reviewed`)
- Pydantic body: `{ graph: str, metadata: str }` (the full metadata URI, e.g. `https://elettra2.0#Motor`).
- `assert_known_graph(graph)` first.
- Issue a SPARQL `DELETE ... WHERE` against `<{graph}>` that removes every `x3d:hasRemovedEntities` and `x3d:hasAddedEntities` triple from all `?s x3d:hasMetadata <{metadata}>` nodes (clear the product "all at once" within the active project). Use `requests.post(VIRTUOSO_URL, data={"update": ...})` like the other mutation routes.
- Scope is the active project graph only — other projects keep their markers until reviewed in their own inventory.
- Return `{ "status": "success", "text": "Marked <label> as reviewed" }`.
- Register the router in `app.py` with prefix `/api`.

### `product_inventory.py`
- Add `obsolete` to each record: true when at least one instance of that `?metadata` in `<{graph}>` has `x3d:hasRemovedEntities` or `x3d:hasAddedEntities`. Implement with an `OPTIONAL`/`EXISTS` in the existing grouped query (or a `BOUND(...)` over a `SAMPLE`), keeping the single-query shape; do not break the existing fields.
- Keep `assert_known_graph` and the existing fundamental-node filter (`x3d:attrib "Fundamental_Node"`).

### `product_hierarchy.py`
- Add a query (over the active `<{graph}>`) that, for the product `metadata`, collects: the distinct file names (`pre:storedAt` of `x3d:hasParentX3D`, stripped to a filename) of instances carrying the markers → `obsoleteFiles`; the union of `x3d:hasAddedEntities` literals → `addedEntities`; the union of `x3d:hasRemovedEntities` literals → `removedEntities`. Set `obsolete = len(obsoleteFiles) > 0`. Add these four keys to the returned object.

### `useProductInventory.ts` / `ProductCard.tsx` / `InventoryProductPage.tsx`
- `InventoryItem` gains `obsolete: boolean`.
- When `obsolete` is true, the card uses a **yellow** background (e.g. `#f1c40f`) with dark text; this takes precedence over the red incomplete-IFC styling. When `obsolete` is false, behaviour is unchanged (red if no IFC class, otherwise default).
- The existing *Status* sort places obsolete (yellow) cards first, then incomplete (red), then complete — one active sort at a time as today. No new buttons.

### `ProductDetailPage.tsx` / `useProductHierarchy.ts` / `ObsolescenceBanner.tsx`
- `useProductHierarchy` exposes `obsolete`, `obsoleteFiles`, `addedEntities`, `removedEntities` from the response.
- When `obsolete` is true, render `<ObsolescenceBanner>` (yellow) above the two-column body. It shows: a heading like "This product is obsolete", the message "Files to update:" followed by the `obsoleteFiles` list, the added/removed entity names, and a **"Mark as reviewed"** button.
- "Mark as reviewed" calls `POST /api/mark-reviewed` with `{ graph: activeProject.graphUri, metadata: <full metadata URI> }`. On success it calls the hierarchy `refresh()` (and, where reachable, triggers an inventory refresh) so the banner disappears and the card returns to normal. Disable the button while the request is in flight; surface success/error via `setMessage`.
- The full metadata URI for the request is derived from the loaded hierarchy root's `metadata` (e.g. the root node's `metadata` field), not reconstructed on the client from the label.

## Definition of done
- [ ] Uploading a replacement STEP file via the "Update Files" page runs the full `WS /api/ws/update` pipeline using `export_gltf` (no Mayo call); the success message reads "Conversion Done".
- [ ] Re-uploading a file whose fundamental node has the **same pattern** as before (same labelled hierarchy, instance numbers aside) leaves that fundamental node unchanged: no markers are written, and the new nodes reuse the old `label.N` instance names.
- [ ] After an update where a node of the old pattern has no counterpart in the new pattern, that `x3d:CADAssembly` instance has one `x3d:hasRemovedEntities` triple per missing node (recorded by its old `label.N`), verifiable via the SPARQL endpoint.
- [ ] After an update that introduces a node not present in the old pattern, that instance has one `x3d:hasAddedEntities` triple per added node (recorded by its new `label.N`); both properties can coexist on the same node.
- [ ] When a fundamental node's pattern changed, only the nodes outside the shared pattern get new instance names; nodes that belong to the pattern keep their old `label.N` names.
- [ ] Node matching ignores instance numbers (`NodeXX.1` and `NodeXX.2` are treated as the same node type when comparing patterns).
- [ ] Changes inside a **nested** fundamental node's own subtree do **not** flag the outer fundamental node (boundary respected).
- [ ] In the Product Inventory of the active project, a product with at least one obsolete instance shows a **yellow** card; products with no markers are unaffected.
- [ ] When the same product exists in file X and file Y of the same project and only file X is updated with a change, the product's card is yellow and its detail page lists both the changed file and the stale file(s) under "Files to update".
- [ ] When the same product exists in another project's graph, that project's inventory also shows the product as yellow (cross-project propagation), and reviewing it in one project does not clear it in the other.
- [ ] Opening an obsolete product's detail page shows the obsolescence banner with the added/removed entity names and the list of files to update.
- [ ] Clicking "Mark as reviewed" deletes `x3d:hasRemovedEntities` and `x3d:hasAddedEntities` for that product in the active project graph; the banner disappears and the card returns to normal after refresh.
- [ ] After "Mark as reviewed" in project A, the same product in project B is still yellow until reviewed there.
- [ ] When a fundamental node's assembly changed during an update, the re-imported fundamental node has **no** IFC class / property sets carried over (its IFC metadata must be re-entered); unchanged fundamental nodes keep their IFC metadata.
- [ ] `POST /api/mark-reviewed` returns 400 for an unknown graph and `{ "status": "success" }` for a known one.
- [ ] `GET /api/product-inventory?graph=<known>` includes an `obsolete` boolean on every record without breaking existing fields.
- [ ] `GET /api/product-hierarchy/<label>?graph=<known>` returns `obsolete`, `obsoleteFiles`, `addedEntities`, and `removedEntities`.
- [ ] Running `python backend/run.py` starts with no import errors from the new `mark_reviewed` route or `diff_fundamental_nodes` module.
