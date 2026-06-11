# Design: Updating File

## Summary
This plan covers the STEP-file-replacement improvements in spec 05, which bundle three
independent fixes plus a new change-review workflow: (1) scoping the `existing_nodes`
and `name_and_number_query` SPARQL helpers to the active project's graph; (2) making
new node instances inherit IFC classification and property sets (Approach 1); (3)
replacing the hardcoded "Davide Avogaro" author with user-entered name fields; and (4)
a notify-and-review loop where assemblies whose CAD structure changed are flagged in
Virtuoso (`x3d:hasAddedEntities` / `x3d:hasRemovedEntities`), surfaced as yellow product
cards, and cleared via a "Mark as Reviewed" action.

It does **NOT** cover: geometry-fingerprint or rename-aware matching (Approaches 3–4
from the earlier discussion were explicitly declined); per-instance flagging or
diff-level reporting of *which* child changed; authentication on the new route; or
migrating the change-flag predicates into the IFC export.

Reading the real code (not just the spec) surfaced **four findings that change the
plan materially** versus the spec as written. These are the spine of this document:

1. **The product inventory only lists Fundamental Nodes, not arbitrary
   `x3d:CADAssembly` nodes.** `product_inventory.py` filters on
   `x3d:attrib = "Fundamental_Node"`. The spec says "flag each affected CADAssembly,"
   but the user also says "the product card returns to normal." Those only reconcile if
   the flag lands on the **fundamental-node product** that contains the change — not on
   whatever nested sub-assembly the change physically occurred in. This plan flags the
   nearest Fundamental-Node ancestor (see Logic design and Open question #1).

2. **The flag must live on the *metadata* URI, not the node-instance URI.** The
   inventory groups by `?metadata` (`GRAPH_NAMESPACE[label]`); the detail page and the
   review route key off the same metadata URI. The spec's `product_inventory` snippet
   reads the flag from `?node`, which would never match a flag written on the metadata
   resource. This plan standardises on the metadata URI everywhere (query, write,
   clear).

3. **`rdf_update_step` cannot currently see a new child added under an *unchanged*
   parent.** Its `add_node` returns immediately when a node is found in the old tree and
   only recurses into the children of *new* nodes. So an addition nested beneath a
   preserved assembly is never visited and never written — which means it also can't be
   flagged. Detecting additions therefore requires changing that early-return to "skip
   rewriting this node's own triples but still recurse into its children" (Open
   question #2 / Logic design).

4. **Adding `?parentMetadata` to `substitution_file_query`'s `GROUP BY` (as the spec
   directs) risks breaking instance numbering.** That query's result feeds the
   number-consumption logic in `build_node_hierarchy`, which assumes **one row per
   metadata** and pops from `numbers`. Splitting rows by parent would fragment the
   number pool and `get_substitute_by_metadata` (a `next()` first-match) would consume
   from only one fragment. This plan leaves the numbering query untouched and derives
   removal-parents from a **separate** lookup (Logic design).

Consistent with prior designs (`01`, `04`), this project has **no `database/db.py`** and
**no server-side templates** — persistence is RDF in Virtuoso and the UI is React — so
the skill's "Database design" and "Template design" sections are reframed as "RDF /
persistence design" and "Frontend component design."

## Implementation order
1. **Graph-scoping fix (lowest risk, unblocks correctness).** Add the required `graph`
   parameter to `name_and_number_query` and `existing_nodes`, thread `graph` through
   `gltf_update_STEP` and `existing_nodes`' caller in `update_STEP.py`. This is
   self-contained and independently verifiable, and every later step runs inside the
   same update flow, so getting the graph right first avoids re-testing.
2. **IFC inheritance for new instances (Approach 1).** Bring `RDF_update_STEP`'s local
   `ExistingProps` and IFC-emission block to parity with `RDF_conversion.py`. This is a
   pure additive change to the new-node branch and can be verified by replacing a file
   that adds an instance of an already-classified component.
3. **Author fields.** The smallest, fully decoupled change — modal state + two inputs +
   disabled-guard. Land it any time; placing it here keeps backend and frontend work
   batched.
4. **Change detection + flag emission (backend).** The hardest step. Decide and
   implement the affected-assembly resolution (fundamental-ancestor), fix the
   recursion-skip so additions are reachable, capture removal-parents without disturbing
   numbering, and emit the two predicates on the right metadata URIs. Must precede any
   UI that reads the flags.
5. **Inventory + card highlight (frontend read path).** Extend the inventory query and
   `InventoryItem`, then style `ProductCard`. Verifiable against flags written in step 4.
6. **Review route + ProductDetailPage button (frontend write-back).** Add
   `review_changes.py`, register it, and wire the "Mark as Reviewed" control. This
   closes the loop and is the last thing to land because it depends on flags existing.

## RDF / persistence design

### Two new predicates (X3D namespace)
- **`x3d:hasAddedEntities`** — boolean literal `true`. Asserted on the **metadata URI**
  of a Fundamental-Node product when the replacement introduced one or more new
  descendant entities under it.
- **`x3d:hasRemovedEntities`** — boolean literal `true`. Asserted on the same metadata
  URI when one or more descendant entities were removed by the replacement.
- **Subject = metadata URI** (`GRAPH_NAMESPACE[label]`, e.g. the resource whose local
  name equals the product label), never the node-instance URI. This matches the
  inventory's `GROUP BY ?metadata`, the detail page's root-metadata lookup, and the
  review route's delete target.
- **Presence-only semantics.** A flag is written only when the corresponding change
  occurred. The "false" state is the *absence* of the triple — never an explicit
  `false` literal. This keeps the inventory `OPTIONAL` clean (bound vs. unbound) and
  makes clearing a simple delete.
- **Graph:** written into the active project's named graph (the flags ride along in the
  same `bulk_import.nt` that the update WebSocket batch-imports), and deleted from that
  same graph by the review route.
- **Lifecycle:** set during a STEP replacement; cleared by `POST /api/review-changes`.
  No migration, no schema registration beyond optionally declaring the two predicates
  as `owl:DatatypeProperty` (matching how the existing converters declare their
  predicates) — declaration is cosmetic and can be skipped.

### No other persistence changes
No `projects.json` change. No new graphs. No IFC-export changes — the flags are a
review-state concern internal to the platform and are deliberately not propagated to
generated IFC.

## Route design

### `POST /api/review-changes` (new)
- **Purpose / behaviour:** an engineer who has inspected a flagged product clicks "Mark
  as Reviewed"; this clears both change flags from that product's metadata URI so the
  card returns to normal on the next inventory load.
- **Inputs:** JSON body with `metadata_uri` (string, the full product metadata URI) and
  `graph` (string, the active project's graph URI).
- **Validation:**
  - `graph` must match a known project — reuse `assert_known_graph` from `projects.py`;
    mismatch → 400.
  - `metadata_uri` must start with the platform namespace prefix
    (`https://elettra2.0#`); otherwise → 400. This is the SPARQL-injection guard for the
    one user-influenced value that gets interpolated into the delete (the inventory and
    detail page only ever send URIs they derived from server data, but the route must
    not trust that).
- **Access level:** public (matches the unauthenticated posture of every existing
  route).
- **Success flow:** issue two graph-scoped SPARQL deletes (one per predicate) against
  `VIRTUOSO_URL` using the same `requests.post(..., data={"update": ...})` pattern as
  `projects.py`'s DROP GRAPH, run inside `run_in_threadpool`; return `{"status":
  "success"}`. Deleting an absent flag is a harmless no-op, so no existence check is
  needed and the operation is idempotent.
- **Error flow:** validation → 400; Virtuoso unreachable / SPARQL error → 500 with a
  descriptive detail.

### `GET /api/product-inventory` (modified)
- **Change:** the per-request query (already built inside `_run_query(graph)` after
  spec 04) gains two `OPTIONAL` joins reading `x3d:hasAddedEntities` /
  `x3d:hasRemovedEntities` **on `?metadata`** (the grouped key), surfaced through
  boolean aggregates so the GROUP BY stays valid. `_transform` maps each to a Python
  bool on the response object as `hasAddedEntities` / `hasRemovedEntities`.
- **No signature/validation change** — still `graph` query param, still
  `assert_known_graph`, still `[]`/500 behaviour.
- **Correction vs. spec:** the spec's snippet reads the flags from `?node`; it must read
  from `?metadata`, because that is where step 4 writes them.

### `WS /api/ws/update` (internal call-chain changes only)
- The handler itself keeps its message contract. Internally: pass `graph_name` to
  `existing_nodes`; unpack the now-richer return of `return_gltf_hierarchy` (scene data
  plus the set of removal-affected product metadata); and pass that set into
  `rdf_update_step` so it can emit removal flags alongside the addition flags it
  computes itself.

## Frontend component design

### Modified: `pages/UpdateFilesPage/UpdateSTEPModal.tsx`
- **Currently:** owner first/last name are module-local constants ("Davide"/"Avogaro");
  the WebSocket payload already references `ownerFirstName` / `ownerLastName`
  identifiers, and `time` is `new Date().toISOString()`.
- **Changes:** replace the two constants with controlled state, default empty. Render
  two text inputs (First Name, Last Name) above the file picker, styled like the
  existing dialog controls (white text, matching padding). Extend the Upload button's
  disabled guard to also require both names non-blank (trimmed). On Cancel, reset both
  name fields (and the file) so the dialog opens blank next time. Because the payload
  already reads those identifiers, no socket-send change is needed beyond the state
  rename.
- **Conditional behaviour:** Upload stays disabled until a `.stp` file is chosen **and**
  both names are filled.

### Modified: `pages/InventoryProductPage/useProductInventory.ts`
- Add `hasAddedEntities: boolean` and `hasRemovedEntities: boolean` to the
  `InventoryItem` type. No fetch-logic change — the fields arrive on the existing JSON
  payload. (Switching projects already refetches via the `graphUri` effect dependency,
  so a freshly cleared or freshly flagged product reflects on reload.)

### Modified: `pages/InventoryProductPage/ProductCard.tsx`
- **Currently:** destructures explicit `InventoryItem` fields; computes
  `incomplete = ifcClass === null` and applies a red background for incomplete cards;
  hover styling via local state.
- **Changes:** destructure the two new booleans; derive a single `hasChanges` flag.
  Apply a yellow/amber warning background **only when `hasChanges && !incomplete`**, so
  the existing red "incomplete" treatment keeps visual priority (a card can be both
  unclassified and changed; red is the more urgent state). Add a small warning chip
  below the CAD-type badge whose text distinguishes added-only, removed-only, and
  both. The chip and background are the only additions; the link target and hover
  behaviour are unchanged.
- **Data flow note:** the page spreads `{...item}` into `ProductCard` and
  `ProductCardProps = InventoryItem`, so the new fields propagate automatically once
  added to the type and the destructure.
- **Optional (flag in review):** the inventory "Status" sort could be extended to float
  changed products to the top; not required by the spec.

### Modified: `pages/ProductDetailPage/ProductDetailPage.tsx`
- **Currently:** resolves `rootUri` via `useProductHierarchy(label, graphUri)`; renders
  a back-navigation row; has access to `activeProject` and `refresh`.
- **Changes:**
  - Derive the product's **metadata URI** as the platform namespace prefix + the route
    `label` (the detail page's root metadata local name equals the product label).
  - After load, run a one-shot graph-scoped SPARQL read (via the existing `fetchQuery`
    helper or a direct `/api/sparql-query` POST) for the two flags on that metadata URI,
    storing an `{added, removed}` state pair.
  - When either flag is set, render a **"Mark as Reviewed"** control
    (`generalButton`-styled) in the existing navigation row. Clicking it POSTs to
    `/api/review-changes` with the metadata URI and `activeProject.graphUri`; on success
    it sets both flags false locally (the button disappears immediately) and calls
    `refresh()` so the hierarchy view stays consistent.
- **Guarding:** if `activeProject` is null (still loading) the button is not shown / is
  inert, mirroring how other pages gate graph-dependent actions.

### Registration
- `app.py` imports and includes `review_changes.router` under the `/api` prefix,
  alongside the other routers.

## Logic design

### Change detection — the core algorithm
The update pipeline already distinguishes matched, new, and removed instances; this
feature reads those existing signals rather than inventing a new diff.

- **Removed instances** are exactly the `NodeToSubstitute` entries that still hold
  unconsumed `numbers` after `build_node_hierarchy` finishes popping. `gltf_update_STEP`
  already computes this set immediately before `delete_remaining_nodes_sparql`.
- **Added instances** are the new-tree nodes that did **not** consume an existing
  substitution number — equivalently, the nodes for which `rdf_update_step`'s `add_node`
  takes its "not found in old tree" branch.

### Resolving the *affected product* (fundamental-node ancestor)
Because the inventory and review UI operate at the Fundamental-Node level, a raw
parent-assembly is not directly actionable. For each detected change, resolve the
nearest ancestor whose metadata carries `x3d:attrib = "Fundamental_Node"` and flag
**that** metadata. Two resolution paths, by change type:

- **Additions (in-memory walk).** During `add_node` recursion the ancestor chain of
  node URIs is known. The `existing_nodes` list (`list[ExistingProps]`) already carries
  each label's `attrib`, so an ancestor label can be tested for fundamental-ness without
  a DB round-trip. Walk up the chain to the first fundamental ancestor; collect its
  label. If none is fundamental, fall back to the top-most ancestor (the product root of
  that file).
- **Removals (DB lookup).** The removed instances are known as (metadata, number) pairs,
  i.e. node URIs. Run **one** graph-scoped SPARQL query that, for those URIs, walks
  `x3d:hasParentCADPart` upward and returns the nearest ancestor metadata flagged
  `Fundamental_Node`. This keeps the numbering query (`substitution_file_query`)
  completely unchanged — the spec's plan to add `?parentMetadata` to its `GROUP BY` is
  rejected here because it fragments the number pool the build step relies on.

### Flag emission
- After the recursion completes, `rdf_update_step` holds two label sets:
  `parents_with_additions` (computed in-memory) and `parents_with_removals` (passed in
  from `gltf_update_STEP`). For each label it emits the corresponding boolean predicate
  on `GRAPH_NAMESPACE[label]`. These triples serialize into `bulk_import.nt` and import
  into the active graph with the rest of the update.
- **Prerequisite fix:** `add_node`'s early `return` on a matched node must change so that
  a matched node's *own* triples are still skipped (preserving its data) but its
  *children* are still visited — otherwise additions beneath an unchanged assembly are
  unreachable and silently lost (finding #3). This is the single riskiest edit;
  implementation must confirm it does not cause matched nodes' subtrees to be rewritten.

### IFC inheritance for new instances (Approach 1)
- In `RDF_update_STEP`, the new-node branch gains the same IFC emission block that
  `RDF_conversion.py` already contains: assign the inherited `ifc_class` as an
  `rdf:type`, re-emit `predefinedType_*`, rebuild the `objectType_IfcObject` sub-resource,
  and reconstruct each property set (`IfcRelDefinesByProperties` → `IfcPropertySet` →
  `IfcPropertySingleValue` chain) keyed by `label`/`pset`/`prop`.
- **Decision point — GUIDs.** `RDF_conversion.py` mints a fresh `globalId_IfcRoot` and a
  `name_IfcRoot` for every node. For *update*-created new instances the spec says to
  leave GUID and IFC name absent so the user assigns them via the IFC form. This plan
  follows the spec (no auto-GUID on update), and notes the divergence from initial
  import as Open question #4 — emitting a pset chain whose owning relation lacks a node
  GUID should be verified against the IFC export/Blender step.
- Inheritance fires only for a **new** node (old-tree miss) that has a matching
  `existing_prop` with an `ifc_class`; matched nodes are untouched (their triples already
  exist).

### Graph scoping
- `name_and_number_query(graph)` and `existing_nodes(graph)` each gain a required
  `graph` parameter (no default, so a missing argument fails loudly rather than silently
  querying every graph) and a `FROM <graph>` clause inserted between their PREFIX block
  and SELECT. `gltf_update_STEP.return_gltf_hierarchy` already receives `graph` and
  passes it to `name_and_number_query`; `update_STEP.py` passes its `graph_name` to
  `existing_nodes`.

## Dependency and integration notes
- **No new packages**, backend or frontend. Backend reuses `requests` / `SPARQLWrapper`
  / `rdflib` / `ifcopenshell` (all present); frontend reuses React state + `fetch` + the
  existing `fetchQuery` helper.
- **Integration points:** the Virtuoso SPARQL endpoint for the flag reads, the
  removal-parent lookup, and the review-route deletes; the existing update WebSocket for
  flag insertion. The new frontend calls go through the Vite `/api` proxy (use relative
  `/api/...` paths in new code; note `fetchQuery.ts` uses an absolute
  `http://localhost:8000` URL today — pre-existing, out of scope).

## Security checklist
- **Authentication on protected routes:** not applicable — the platform is
  unauthenticated local-network tooling; `review-changes` matches that posture. Worth
  recording that anyone on the network can clear another user's review flags.
- **Authorisation (own-data only):** not applicable — no user/ownership model exists.
- **Input validation / sanitisation:** the review route validates `graph` against the
  `projects.json` allowlist (`assert_known_graph`) and requires `metadata_uri` to begin
  with the `https://elettra2.0#` namespace before interpolation. The author name fields
  flow into RDF literals (not URIs) via rdflib, which handles literal escaping; they are
  not interpolated into raw SPARQL. The product label that becomes a metadata URI on the
  detail page originates from server-provided inventory data.
- **SPARQL injection prevention:** the codebase interpolates values into SPARQL via
  f-strings rather than true parameter binding — a pre-existing characteristic. This
  plan does not worsen it: the only newly user-influenced value reaching a raw SPARQL
  string (the review route's `metadata_uri`) is prefix-validated, and `graph` is
  allowlist-validated. The removal-parent lookup interpolates only server-derived node
  URIs.
- **CSRF:** not applicable — no cookies/sessions; CORS is already restricted to
  `http://localhost:3000`. The new POST is state-changing but same-posture as existing
  mutating routes.
- **Sensitive data handling:** none — flags are booleans; author names are
  non-sensitive provenance labels already stored as RDF literals today.

## Open questions
1. **Flag granularity: fundamental-node ancestor vs. literal affected assembly.** The
   spec says "each affected `x3d:CADAssembly`," but the inventory and review UI are
   Fundamental-Node–scoped.
   - *Assumption:* flag the nearest Fundamental-Node ancestor of each change, so exactly
     the product card the user would open lights up and clearing it from that page works.
   - *Impact if wrong:* if literal sub-assembly flagging is desired, the inventory (which
     filters to fundamental nodes) wouldn't surface most flags, and the detail-page
     clear (keyed on the product label) wouldn't target them — a different read/write
     model would be needed (e.g. aggregate "any flagged descendant" into the product
     row).
2. **Recursion-skip in `add_node`.** New children beneath an unchanged parent are
   currently unreachable.
   - *Assumption:* change the matched-node early-return to skip only the node's own
     triple rewrite while still recursing into its children, so additions are detected
     and existing data is preserved.
   - *Impact if wrong:* if the early-return must stay (e.g. it guards against rewriting
     shared cross-project products), additions can't be detected through this path and
     an alternative detection (count-diffing instances per product against the DB) is
     required.
3. **`substitution_file_query` shape.** The spec adds `?parentMetadata` to its
   `GROUP BY`.
   - *Assumption:* do **not** modify that query; derive removal-parents from a separate
     lookup, leaving the numbering pool one-row-per-metadata.
   - *Impact if wrong:* if the grouped variant is used anyway, `build_node_hierarchy`'s
     number consumption may assign duplicate or skipped instance numbers when a metadata
     appears under multiple parents.
4. **No GUID for update-created instances.** The spec omits `globalId_IfcRoot` /
   `name_IfcRoot` for new nodes, diverging from initial import.
   - *Assumption:* follow the spec — leave them absent for the user to assign.
   - *Impact if wrong:* a pset/relation chain on a node lacking an IFC GUID may produce
     an invalid or incomplete IFC on export; the Blender/IFC step should be checked, and
     if it breaks, minting a GUID on update (as initial import does) is the fallback.
5. **Detail-page flag read.** Adds one extra SPARQL round-trip per product open.
   - *Assumption:* a small dedicated query is acceptable.
   - *Impact if wrong:* if the extra round-trip is unwanted, the `product-hierarchy`
     route could return the flags on the root, removing the separate call.

## Definition of done (design review)
- [ ] Agreement that flags are written on the **metadata URI** (not the node instance)
      and on the **nearest Fundamental-Node ancestor** (Open question #1).
- [ ] Agreement to fix `add_node`'s recursion-skip so additions under unchanged parents
      are reachable, with a verification step that matched subtrees are not rewritten
      (Open question #2).
- [ ] Agreement that `substitution_file_query` stays unchanged and removal-parents come
      from a separate lookup (Open question #3).
- [ ] Decision recorded on update-created GUIDs (follow spec: none) and a noted check of
      the IFC-export path (Open question #4).
- [ ] Confirmed `product_inventory` reads the flags from `?metadata`, not `?node`, and
      via GROUP-BY-safe boolean aggregates.
- [ ] Confirmed `name_and_number_query` and `existing_nodes` take a required `graph`
      (no default) and that all callers pass it.
- [ ] Confirmed presence-only flag semantics (no explicit `false`), so the review route
      is a pure idempotent delete and the inventory uses bound/unbound OPTIONALs.
- [ ] Confirmed `review-changes` validates both `graph` (allowlist) and `metadata_uri`
      (namespace prefix) before interpolation, and is registered in `app.py`.
- [ ] Confirmed the author-name fields gate the Upload button and reset on Cancel.
