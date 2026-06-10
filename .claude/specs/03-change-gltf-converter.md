# Spec: Change GLTF Converter

## Overview
Replace the external Mayo CLI tool (`mayo-conv.exe`) with a self-contained Python-based STEP→GLTF converter built on `pythonocc-core` and `pygltflib`. The conversion logic already exists in `backend/test.py` — this spec moves it into a proper service module (`occ_converter.py`) and wires it into the existing STEP-upload WebSocket pipeline (`mayo_and_gltf.py`). This eliminates the hard dependency on a Windows-only GUI executable and brings the full conversion into the Python process. The rest of the pipeline (hierarchy parsing, GLB compression via gltfpack, RDF conversion, Virtuoso import) is unchanged.

## Depends on
No previous spec is required. The backend pipeline (`mayo_and_gltf.py`) already exists; this spec updates it in-place.

## Routes
No new routes.

The existing route conflict between `mayo_and_gltf.py` and `bypass_step.py` (both declare `WS /ws/convert`) is resolved as part of this spec:
- `bypass_step.py` has its WebSocket route renamed from `/ws/convert` to `/ws/convert-bypass`
- `mayo_and_gltf.py` (updated to use the Python converter) becomes the sole owner of `WS /api/ws/convert`
- `app.py` uncomments `mayo_and_gltf.router`

## Database changes
No database changes.

## Templates / Components
No frontend changes. The frontend already connects to `ws://localhost:8000/api/ws/convert` and the message protocol is preserved (only the status text "Conversion Done with Mayo" is updated to "Conversion Done").

## Files to change
- `backend/api/routes/mayo_and_gltf.py` — replace `convert_with_mayo()` with `export_gltf()` from `occ_converter.py`; update the status message text
- `backend/api/routes/bypass_step.py` — rename WebSocket route from `/ws/convert` to `/ws/convert-bypass`
- `backend/app.py` — uncomment `mayo_and_gltf.router`
- `backend/requirements.txt` — add `pythonocc-core`

## Files to create
- `backend/api/services/importing_STEP/occ_converter.py` — contains the full STEP→GLTF conversion logic extracted from `test.py`

## New dependencies
- `pythonocc-core` — Python bindings for the OpenCASCADE geometry kernel (BRep tessellation, XCAF STEP reader, colour tools)

`pygltflib` and `numpy` are already in `requirements.txt`.

## Rules for implementation

### occ_converter.py
- Copy **every** function, dataclass, and import from `backend/test.py` that is needed by `export_gltf()` — specifically: `PartMesh`, `AssemblyNode`, `XcafContext`, `extract_rgba`, `triangulate_shape`, `load_xcaf`, `label_name`, `sanitize_node_name`, `resolve_color`, `compose_location`, `location_to_matrix`, `compose_matrices`, `decode_step_string`, `split_step_args`, `parse_ref`, `parse_ref_list`, `extract_step_entity_signature`, `build_nauo_manifold_map`, `build_assembly_tree`, `export_gltf`
- Do **not** copy the `if __name__ == "__main__":` block or the `argparse` import — those are CLI harness only
- Do **not** edit `backend/test.py`
- The public interface of the module is a single function:
  ```python
  def export_gltf(step_path: str, output_path: str, deflection: float = 0.01, unit_scale: float = 0.001) -> str
  ```
  `output_path` may be passed without the `.gltf` extension; the function appends it if missing and returns the final path. It also creates a sibling `.bin` file in the same directory.

### mayo_and_gltf.py
- Remove the `from api.services.importing_STEP.mayo import convert_with_mayo` import
- Add `from api.services.importing_STEP.occ_converter import export_gltf`
- Replace the `convert_with_mayo(input_file, output_file)` call (and its surrounding `run_in_threadpool` wrapper) with:
  ```python
  gltf_path = await run_in_threadpool(export_gltf, step_file_path, gltf_output_path)
  ```
  where `step_file_path` is the path to the uploaded `.stp`/`.step` file and `gltf_output_path` is the target path under `GLTF_FOLDER` (without extension — the function handles it)
- Update the success status message from `"Conversion Done with Mayo"` to `"Conversion Done"`
- All other logic (hierarchy parsing, compression, RDF conversion, DB import, error handling, WebSocket messaging) is unchanged

### bypass_step.py
- Change `@router.websocket("/ws/convert")` to `@router.websocket("/ws/convert-bypass")`
- No other changes

### app.py
- Uncomment `# app.include_router(mayo_and_gltf.router, prefix="/api")`
- Leave all other registrations as-is

### requirements.txt
- Append `pythonocc-core` on a new line

### General
- No SQLAlchemy or ORMs
- Parameterised queries only (unchanged — no SPARQL changes in this spec)
- Do not add error handling beyond what already exists in `mayo_and_gltf.py`; if `export_gltf` raises, the existing `except Exception as e` block in the WebSocket handler already sends an error message to the client

## Definition of done
- [ ] `backend/requirements.txt` contains `pythonocc-core`
- [ ] `backend/api/services/importing_STEP/occ_converter.py` exists and exports `export_gltf`
- [ ] `backend/test.py` is unchanged (no edits)
- [ ] Uploading a STEP file via the frontend completes the full pipeline over `ws://localhost:8000/api/ws/convert` without calling Mayo
- [ ] The WebSocket stream emits `{"status": "wip", "text": "Starting conversion"}` then `{"status": "success", "text": "Conversion Done"}` (not "with Mayo")
- [ ] The pipeline continues to emit hierarchy-parsed, compressed, RDF-created, and triples-imported messages as before
- [ ] A GLB file appears in `tmp/GLB/` after conversion
- [ ] Triples are importable into Virtuoso and the STEP hierarchy page renders the assembly tree
- [ ] `GET /api/ws/convert-bypass` is the only route served by `bypass_step.py` (no longer conflicts)
- [ ] `app.include_router(mayo_and_gltf.router, prefix="/api")` is active (not commented out) in `app.py`
- [ ] Running `python backend/run.py` starts without route-conflict errors
