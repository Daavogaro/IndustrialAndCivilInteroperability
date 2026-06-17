# Spec: Undo Fundamental Node

## Overview
Today the `FundamentalNodeButton` (the IFC-logo button shown next to a selected
node in the STEP interface) is a one-way action: clicking it tags the node with
`x3d:attrib "Fundamental_Node"` and un-deletes it, but there is no way to revert
that. This feature turns the button into a **toggle**: when the selected node is
already a fundamental node, pressing the button removes the `Fundamental_Node`
attribute (undo); when it is not, it behaves exactly as today (promote to
fundamental node). This lets users correct mistakes without re-importing the
STEP file and keeps the RDF graph clean for the downstream Blender/IFC conversion.

## Depends on
- The existing fundamental-node feature: `POST /api/add-fundamental-node`
  (`backend/api/routes/add_fundamental_node.py`) and the `FundamentalNodeButton`
  component.
- Multiple-project support (step 04): routes are graph-scoped and validated via
  `assert_known_graph` (`backend/api/routes/projects.py`).

## Routes
- `POST /api/remove-fundamental-node` — deletes the
  `?s x3d:attrib "Fundamental_Node"` triple for the node identified by its
  `hasMetadata` URI, within the given named graph — logged-in (graph-scoped).

Existing route `POST /api/add-fundamental-node` is unchanged (still used for the
"promote" direction).

## Database changes
This project uses a Virtuoso RDF triple store (no relational DB / `db.py`).

No schema changes. The undo path issues a SPARQL `DELETE` that removes the triple

```
GRAPH <graph> { ?s x3d:attrib "Fundamental_Node"^^xsd:string . }
WHERE { ?s x3d:hasMetadata <metadata> ; x3d:attrib "Fundamental_Node"^^xsd:string . }
```

No other triples are touched (the node's `x3d:visible` value is left as-is on
undo).

## Templates
This is a React/Vite frontend — there are no server-side templates.
- **Create:** none
- **Modify:** none

## Files to change
- `backend/app.py` — import and `include_router` the new
  `remove_fundamental_node` route under the `/api` prefix.
- `frontend/src/pages/STEPPage/gLTFViewer/FundamentalNodeButton.tsx` — accept a
  new `isFundamental: boolean` prop; branch the `onClick` handler to call
  `/api/remove-fundamental-node` when `isFundamental` is true, otherwise the
  current add flow. Swap the button content based on state: when the node is NOT
  fundamental, render the existing `<img src="../IFC-logo.png" />`; when it IS
  fundamental (toggled on), render a `<span>undo</span>` instead of the image so
  the user can clearly see that pressing it will undo the fundamental-node tag.
- `frontend/src/pages/STEPPage/STEPPage.tsx` — pass
  `isFundamental={nodeData?.isFundamental ?? false}` to the button.
- `frontend/src/pages/ProductDetailPage/NodeDetails/NodeDetails.tsx` — pass
  `isFundamental={treeNodeData.isFundamental}` and render the button regardless
  of `isFundamental` (so the node can be un-toggled there too) instead of hiding
  it when `isFundamental` is true.

## Files to create
- `backend/api/routes/remove_fundamental_node.py` — FastAPI router exposing
  `POST /api/remove-fundamental-node`, mirroring `add_fundamental_node.py` but
  issuing a SPARQL `DELETE`. Calls `assert_known_graph(graph)` before mutating.

## New dependencies
No new dependencies (reuses `fastapi`, `pydantic`, `requests`).

## Rules for implementation
- No SQLAlchemy or ORMs — RDF only, via raw SPARQL over `requests` to
  `VIRTUOSO_URL`.
- Parameterised/scoped queries only — always target the specific named graph and
  the specific node via its `hasMetadata` URI; never run an ungraphed update.
- Centralise constants: import `VIRTUOSO_URL`, `GRAPH_NAMESPACE`,
  `X3D_NAMESPACE` from `api/models/models.py` — do not hardcode endpoints or
  namespaces in the new route.
- Validate the graph with `assert_known_graph` (as `update_deletion.py` does)
  before issuing the delete.
- Keep the existing add behaviour untouched; the toggle decision lives in the
  frontend based on `isFundamental`.
- Match the existing response shape: `{ "status": "success", "text": "..." }`
  so `setMessage` keeps working.
- After either action the button must call `onUpdated()` to refresh the
  hierarchy so `isFundamental` reflects the new state.

## Definition of done
- With the app running (Virtuoso → backend → frontend), selecting a non-fundamental
  node and clicking the button promotes it: the node gains
  `x3d:attrib "Fundamental_Node"` and the hierarchy refreshes showing it as
  fundamental.
- Clicking the button again on that now-fundamental node removes the
  `Fundamental_Node` attribute: a SPARQL query confirms the triple is gone, and
  the refreshed hierarchy no longer marks the node as fundamental.
- The toggle is repeatable (promote → undo → promote) with no leftover or
  duplicate `attrib` triples in the graph.
- `POST /api/remove-fundamental-node` with an unknown graph is rejected by
  `assert_known_graph`.
- The button content reflects the node's state: the `IFC-logo.png` image shows
  for a non-fundamental node, and a `<span>undo</span>` shows for a fundamental
  one; the content swaps after each toggle and refresh.
- A success message appears in the message panel for both directions.
- No regression: the `add-fundamental-node` + un-delete behaviour still works for
  nodes that were previously hidden.
