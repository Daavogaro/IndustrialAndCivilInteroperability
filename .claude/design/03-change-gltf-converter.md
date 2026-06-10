# Design: Change GLTF Converter

## Summary
This plan covers replacing the external Mayo CLI (`mayo-conv.exe`) as the STEP→GLTF stage of the upload pipeline with a self-contained, in-process Python converter built on `pythonocc-core` + `pygltflib`, whose logic already exists in `backend/test.py`. The work is: (1) lift the conversion logic from `test.py` into a new service module `occ_converter.py` exposing a single `export_gltf(...)` function, **without editing `test.py`**; (2) swap the `convert_with_mayo` call inside the existing `mayo_and_gltf.py` WebSocket pipeline for `export_gltf`, keeping every downstream stage (hierarchy parse → GLB compression → RDF conversion → Virtuoso import) untouched; (3) resolve the standing `/ws/convert` route collision by renaming `bypass_step.py`'s route to `/ws/convert-bypass` and re-enabling `mayo_and_gltf.router` in `app.py`; (4) add `pythonocc-core` to `requirements.txt`.

It does **not** cover: any change to the hierarchy parser (`gltf.py`), the compressor (`compess_gltf.py`), the RDF conversion (`RDF_conversion.py`), the DB import, the WebSocket message protocol/shape, or any frontend file. It does not delete `mayo.py`, the `POST /convert` Mayo route, or the `MAYO_EXE`/`INI_FILE` constants — those stay as dead-but-harmless scaffolding (out of scope).

Two integration facts discovered while reading the code shape the plan and are flagged where they bite: (1) `mayo_and_gltf.router` is **currently commented out** in `app.py`, so today the live `/ws/convert` is actually the *bypass* (GLTF-only) handler — a grep confirms **only** `UploadSTEPModal.tsx` connects to `/ws/convert` and nothing in the frontend uses the bypass handler, so the rename is safe and re-enabling the OCC pipeline is what makes STEP upload actually run the converter; (2) the downstream hierarchy parser (`return_gltf_hierarchy`) **re-derives instance numbers itself** and rewrites node names before compression, so `test.py`'s naming scheme integrates cleanly and the parse-before-compress ordering (which spec 02's product isolation depends on) must be preserved. As with the 01/02 designs, this project has **no** `database/db.py` and **no** server-side templates, so the skill's "Database design" and "Template design" sections are adapted to "Pipeline / data-flow design" and "Module design".

## Implementation order
1. **Dependency first.** Add `pythonocc-core` to `requirements.txt` and confirm it imports in the backend environment. This is the highest-risk *environmental* step (pythonocc is conda-oriented; see Open Questions) and gates everything else — if `OCC.Core` cannot import, the converter is dead on arrival, so prove it before writing wiring.
2. **Extract the converter module.** Create `occ_converter.py` by copying the needed dataclasses, helpers, and `export_gltf` from `test.py` verbatim (minus the `argparse`/`__main__` harness). Verify it standalone by pointing it at a sample `.stp` and confirming a `.gltf`+`.bin` pair is produced and loads in `pygltflib`. This isolates the conversion concern before touching the pipeline.
3. **Rename the bypass route.** Change `bypass_step.py`'s `@router.websocket("/ws/convert")` to `/ws/convert-bypass`. Doing this before re-enabling the OCC router guarantees there is never a moment where two routers claim the same path.
4. **Swap the converter call in the pipeline.** In `mayo_and_gltf.py`, replace the `convert_with_mayo` import + call with `export_gltf`, capture its returned path, feed it to the existing hierarchy/compression stages, and update the status text. Remove the now-dead `convert_with_mayo` import and `safe_convert_with_mayo` helper.
5. **Re-enable the OCC router.** Uncomment `app.include_router(mayo_and_gltf.router, prefix="/api")` in `app.py`. This is last because it makes the new pipeline live; doing it only after the route rename (step 3) means the app never boots with a path collision.
6. **End-to-end verify.** Upload a real STEP via the frontend modal and walk the full status stream through to "Imported N triples", confirming a GLB lands in `tmp/GLB/` and the hierarchy renders.

## Pipeline / data-flow design
No RDF schema changes; no triples are written differently. The only thing that changes is **how the `.gltf` file is produced** at the head of the pipeline. The data flow after the swap is:

1. `UploadSTEPModal` uploads the `.stp` to `tmp/STEP/` (pre-existing upload step), then opens `ws://localhost:8000/api/ws/convert` and sends `{ filename, graph_name, parent_uri, ownerFirstName, ownerLastName, time }`.
2. **(CHANGED)** `export_gltf(step_path, gltf_output_path)` reads the STEP via OpenCASCADE XCAF, tessellates each solid, and writes `tmp/gLTF/<name>.gltf` + a sibling `<name>.bin`. Previously this was `convert_with_mayo` shelling out to `mayo-conv.exe`.
3. **(UNCHANGED)** `return_gltf_hierarchy(<gltf>)` loads the `.gltf` (+ external `.bin`), computes per-mesh bounding-box dimensions from accessor min/max, **renumbers node names** to `label.N`, rewrites the `.gltf`, and returns the scene hierarchy; the hierarchy JSON is saved to `tmp/JSON/`.
4. **(UNCHANGED)** hierarchy → RDF (`convert_hierarchy_in_rdf`), GLB compression (`gltfpack` over the renamed `.gltf` → `tmp/GLB/<name>.glb`), RDF file write, batched Virtuoso import.

**Compatibility chain — why the swap is drop-in:**
- **External `.bin` is fine.** `export_gltf` sets `buffers[0].uri = <bin basename>` and writes the `.bin` beside the `.gltf`. `preload_buffers` in `gltf.py` already handles non-`data:` buffer URIs by reading `os.path.join(gltf_file_dir, buffer.uri)`. ✓
- **Dimensions fast-path works.** `export_gltf` writes `min`/`max` on the POSITION accessor, which is exactly the fast path `get_mesh_dimensions` prefers. ✓
- **Naming is robust regardless of source.** `return_gltf_hierarchy` splits each node name on `.`, drops any existing trailing `.suffix`, and assigns its own instance number from `name_and_number_query`, then renames the node and re-saves. So whatever `test.py`'s `sanitize_node_name` emits (e.g. `Bolt`, `Bolt_1`, `Plate.2`) is normalised to `label.N` downstream. ✓
- **Compressor is unaffected.** `gltfpack` consumes the renamed `.gltf` + `.bin`; the parse-before-compress order in the current `mayo_and_gltf.py` (parse at line ~95, compress at line ~128) is preserved, so the GLB carries the renumbered names that spec-02 product isolation relies on. ✓

**Migration strategy:** none — read path only; no stored data format changes. Existing GLBs/triples from Mayo-era imports remain valid.

## Route design

### `WS /api/ws/convert` (full STEP→GLTF→RDF pipeline — re-enabled & converter swapped)
- **Method / path:** WebSocket at `/api/ws/convert` (the `/api` prefix is applied at registration in `app.py`). Becomes the sole owner of this path once the bypass route is renamed.
- **Purpose / behaviour:** unchanged end-to-end contract — accept a STEP filename, stream `{status, text}` progress messages, produce a GLB and import RDF triples. Only the conversion engine behind the first stage changes.
- **Request inputs (unchanged):** a single JSON message: `filename` (STEP file already uploaded to `tmp/STEP/`), `graph_name`, `parent_uri`, `ownerFirstName`, `ownerLastName`, `time`.
- **Validation rules:** `filename` is passed through the existing `sanitize_filename` (basename only, allow-listed chars, lowercased extension) — this already neutralises path traversal. No new validation is introduced. (See Open Questions re: `.step` vs `.stp` extension handling.)
- **Auth / access-level:** public on the local network, matching the whole app (no auth layer). No CORS change (the WebSocket origin policy is unchanged).
- **Success flow:** identical message sequence as before except the post-conversion message text changes from `"Conversion Done with Mayo"` to `"Conversion Done"`. Sequence: `wip:Starting conversion` → `success:Conversion Done` → `wip:Parsing hierarchy` → `success:Hierarchy parsed and saved as JSON` → `wip:Converting hierarchy to RDF` → `wip:Compressing gLTF` → `success:gLTF Compressed` → `success:RDF file created` → (batch import messages) → `success:Imported N triples in DB`.
- **Error flow:** unchanged — the existing top-level `except Exception as e: send_json({"status":"error","text":str(e)})` already wraps the whole body, so any exception raised by `export_gltf` (e.g. unreadable STEP, no triangulated geometry) is surfaced to the client as an `error` message with the exception text. No new error handling is added.

### `WS /api/ws/convert-bypass` (GLTF→RDF, no STEP conversion — renamed only)
- **Method / path:** WebSocket, renamed from `/ws/convert` to `/ws/convert-bypass`. Body and behaviour otherwise unchanged (compress an existing `.gltf` in `tmp/gLTF/`, parse hierarchy, convert to RDF, import).
- **Rationale / safety:** confirmed by grep that no frontend file connects to this handler today; the only `/ws/convert` consumer is `UploadSTEPModal.tsx`, which sends a STEP filename and therefore *should* be served by the OCC pipeline. Renaming frees the path for the OCC pipeline and keeps the bypass flow available for future/manual use without collision.

### `POST /api/convert` (Mayo HTTP route — untouched)
- Remains registered via `mayo.router`. Out of scope; not removed. It still shells out to `mayo-conv.exe` if anyone calls it directly, but nothing in the changed pipeline does.

## Module design

### New: `backend/api/services/importing_STEP/occ_converter.py`
- **What it contains:** an exact copy of every symbol from `test.py` that `export_gltf` transitively needs — dataclasses `PartMesh`, `AssemblyNode`, `XcafContext`; helpers `extract_rgba`, `triangulate_shape`, `load_xcaf`, `label_name`, `sanitize_node_name`, `resolve_color`, `compose_location`, `location_to_matrix`, `compose_matrices`, `decode_step_string`, `split_step_args`, `parse_ref`, `parse_ref_list`, `extract_step_entity_signature`, `build_nauo_manifold_map`, `build_assembly_tree`, and `export_gltf` — plus the imports those require (`OCC.Core.*`, `pygltflib`, `numpy`, `re`, `dataclasses`, `pathlib`).
- **What it omits:** `import argparse` and the entire `if __name__ == "__main__":` block (CLI harness only). No behavioural edits to any copied function.
- **Public surface:** one function, `export_gltf(step_path, output_path, deflection=0.01, unit_scale=0.001) -> str`. It tolerates `output_path` with or without a `.gltf` suffix (appends if missing), writes a sibling `.bin`, and returns the final `.gltf` path as a string. The defaults match `test.py`'s CLI invocation (`0.01`, `0.001`).
- **Relationship to `test.py`:** `test.py` is left exactly as-is (it remains a runnable standalone script). `occ_converter.py` is a parallel, import-safe copy. Duplication is accepted deliberately here because the spec forbids editing `test.py`; the alternative (importing from `test.py`) is rejected because `test.py` is a top-level CLI script outside the `api` package and importing it would drag in `argparse`/`__main__` semantics and an awkward module path.

### Modified: `backend/api/routes/mayo_and_gltf.py`
- **Currently:** imports `convert_with_mayo`; inside the WebSocket body, calls `await run_in_threadpool(convert_with_mayo, input_file, output_file)` then sends `"Conversion Done with Mayo"`. Also defines an unused `safe_convert_with_mayo` helper.
- **Changes:**
  - Remove `from ..services.importing_STEP.mayo import convert_with_mayo`; add `from ..services.importing_STEP.occ_converter import export_gltf`.
  - Replace the conversion call so the returned path is captured and used downstream: conceptually `gltf_path = await run_in_threadpool(export_gltf, input_file, output_file)`, then use `gltf_path` as the input to `return_gltf_hierarchy` and as the compression input (instead of re-deriving the path string twice as the current code does). Passing `output_file` (which already carries `.gltf`) is safe because `export_gltf` keeps an existing `.gltf` suffix.
  - Change the success message text from `"Conversion Done with Mayo"` to `"Conversion Done"`.
  - Remove the now-dead `safe_convert_with_mayo` helper (it references the removed import).
  - **Everything else stays:** the `run_in_threadpool` wrapping (keeps the CPU-heavy mesh step off the event loop), the hierarchy parse, JSON write, RDF conversion, compression, RDF file write, batched import, and the top-level `try/except` are unchanged.
- **Optional cleanup (recommended, not required by spec):** the body is still nested inside `async with httpx.AsyncClient() as client:` and imports `httpx` and `MAYO_SERVICE_URL` — both are now fully vestigial (the client object is never used). Removing them reduces confusion. Flagged as Open Question 5 so the implementer can decide whether to keep the diff minimal or tidy.

### Modified: `backend/api/routes/bypass_step.py`
- **Currently:** `@router.websocket("/ws/convert")`.
- **Change:** rename the decorator path to `@router.websocket("/ws/convert-bypass")`. No other change. (Its own stale `convert_with_mayo` import and `safe_convert_with_mayo` helper are pre-existing dead code and out of scope; may be left as-is to keep the diff focused, though removing them is harmless.)

### Modified: `backend/app.py`
- **Change:** uncomment line `app.include_router(mayo_and_gltf.router, prefix="/api")`. The `from api.routes import mayo_and_gltf` import is already present. Leave all other registrations untouched (`bypass_step`, `mayo`, etc. remain).

### Modified: `backend/requirements.txt`
- **Change:** append `pythonocc-core` on a new line. `pygltflib` and `numpy` are already listed, so no other additions.

## Logic design

### `export_gltf` (the new pipeline entry point) — contract & behaviour
- **Responsibility:** convert a STEP file to a glTF (JSON) + external binary buffer on disk.
- **Inputs:** `step_path` (absolute path to an existing `.stp`/`.step` under `tmp/STEP/`); `output_path` (target `.gltf` path under `tmp/gLTF/`, with or without extension); `deflection` (tessellation chordal tolerance, default `0.01`); `unit_scale` (vertex/translation multiplier, default `0.001`, i.e. millimetre STEP → metre glTF).
- **Output:** the final `.gltf` path string; side effect of writing `<name>.gltf` and `<name>.bin`.
- **Decision tree (as inherited from `test.py`, unchanged):**
  - Load STEP via `STEPCAFControl_Reader` with colour/layer/name/material/GDT modes on; raise `RuntimeError` if the file cannot be read or transferred.
  - Build a NAUO→manifold-solid map by text-parsing the STEP to split multi-solid product instances into per-solid child nodes.
  - Walk the XCAF assembly tree: references compose transforms and may expand into multiple manifold children; assemblies recurse; simple shapes tessellate. Faces that fail shape-level meshing are retried per-face; still-untriangulated faces are skipped with a warning.
  - If no geometry is extracted at all → raise `RuntimeError("No triangulated geometry was extracted.")` (surfaces as a WebSocket `error`).
  - Emit one glTF material per unique colour; write POSITION (with min/max) and index accessors; assemble nodes with optional 4×4 `matrix` transforms.
- **Side effects:** filesystem writes only; no DB, no network. Runs inside `run_in_threadpool` so the (potentially multi-second) meshing does not block the asyncio event loop.

### Downstream integration invariants (must remain true after the swap)
- **Parse before compress.** `return_gltf_hierarchy` renames nodes and re-saves the `.gltf`; the GLB must be produced *after* this so it carries `label.N` names. Preserve the existing call order.
- **External-buffer round-trip.** The `.gltf` and `.bin` must stay co-located in `tmp/gLTF/` for `preload_buffers` and `gltfpack` to resolve the buffer; `export_gltf` already writes them together.
- **Path consistency.** Use the path returned by `export_gltf` for the hierarchy parse and compression input to avoid drift between the conversion output and what downstream stages read.

## Dependency and integration notes
- **New package: `pythonocc-core`** — Python bindings for the OpenCASCADE geometry kernel, required for the STEP reader (`STEPCAFControl_Reader`), tessellation (`BRepMesh_IncrementalMesh`), topology traversal (`TopExp_Explorer`), and colour tools (`XCAFDoc_ColorTool`) that `test.py`'s logic is built on. This is the dependency that lets us drop the external `mayo-conv.exe` binary.
  - **Install caveat (important):** `pythonocc-core` is primarily distributed via **conda-forge**, and `pip install pythonocc-core` frequently fails or has no matching wheel on many platforms. The project's documented setup is `pip install -r requirements.txt`. Adding it to `requirements.txt` records intent, but the implementer must confirm the backend environment can actually import `OCC.Core` — possibly via conda, or a platform-specific wheel. **This must be validated in step 1 before any other work.** (Open Question 1.)
- **`pygltflib`, `numpy`** — already present; the converter uses `GLTF2`, accessors/buffer-views, and `np.ndarray` vertex/index arrays.
- **Removed runtime dependency:** the hard requirement on `MAYO_EXE` (`C:\Program Files\Fougue\Mayo\mayo-conv.exe`) for the upload pipeline. The constant and the `POST /convert` route remain in the codebase but are no longer on the upload path.
- **Integration points unchanged:** `gltfpack` (frontend `node_modules/.bin`) for compression; Virtuoso for import; the `/api/glb` static mount and `tmp/` folder layout.

## Security checklist
- **Authentication on protected routes:** not applicable — unauthenticated local-network tooling; the WebSocket matches that posture and gains no new exposure.
- **Authorisation (own-data only):** not applicable — no user/ownership model; single shared graph by design.
- **Input validation / sanitisation:** the only untrusted input remains `filename`, already neutralised by the existing `sanitize_filename` (basename-only, allow-listed characters, lowercased extension) before being joined to `STEP_FOLDER` — this prevents path traversal into or out of `tmp/STEP/`. No new untrusted input is introduced. The STEP *content* is parsed by OpenCASCADE; a malformed/malicious STEP at worst raises an exception caught by the handler (denial of that one job), not a process compromise — but note STEP parsing of fully untrusted files is a larger attack surface than shelling to Mayo was; acceptable for local-network use.
- **SQL/SPARQL injection prevention:** no query construction changes in this spec; the RDF conversion and import paths are untouched. Not applicable to the converter swap.
- **CSRF:** not applicable — WebSocket upgrade, no cookies/sessions; behaviour unchanged.
- **Sensitive data handling:** none — the converter only reads a CAD file the user just uploaded and writes derived geometry to `tmp/`.

## Open questions
1. **Can `pythonocc-core` be installed via `pip` in this environment?** It is conda-first and often lacks pip wheels.
   - *Assumption for this plan:* the backend environment can import `OCC.Core` (via conda or a working wheel) once the package is added; `requirements.txt` records the dependency.
   - *Impact if wrong:* the entire feature is blocked — `import OCC.Core` fails at module import and `/ws/convert` returns an immediate error. This is why it is **step 1** and must be proven before further work. If pip cannot provide it, the README/setup docs (and possibly `docker-compose`/env setup) need a conda or wheel-source note — a scope addition to flag with the user.
2. **Coordinate-system / axis orientation.** Mayo's `.ini` explicitly remapped axes (`posYfwd_posZup` → `negZfwd_posYup`) to suit web/three.js Y-up. `test.py`'s logic does **not** perform any axis remap — it only scales vertices/translations by `unit_scale`. STEP is typically Z-up.
   - *Assumption for this plan:* acceptable for v1; the model may appear rotated (Z-up) compared to Mayo output, to be confirmed visually after the first conversion.
   - *Impact if wrong:* imported products render rotated 90° in the viewer. Fixing it would require an axis transform — but that means changing conversion logic, which conflicts with "keep the logic in `test.py` / do not edit `test.py`". If orientation matters, the fix belongs either as a root-node transform applied in `occ_converter.py` (a deliberate divergence from `test.py`) or a follow-up spec. **Recommend a quick visual check against a known model early.**
3. **Unit scale (`0.001`) correctness.** The converter assumes STEP is in millimetres and outputs metres. If a given STEP uses different units, geometry will be 1000× off.
   - *Assumption:* mm STEP input (matches `test.py`'s defaults and the typical Elettra dataset).
   - *Impact if wrong:* dimensions in the hierarchy (and bounding boxes) are scaled wrong; the viewer auto-frames so it may not be visually obvious, but `x3d:bboxSize` values in RDF would be off. Could be exposed as a parameter later.
4. **`.step` vs `.stp` extension.** The existing `mayo_and_gltf.py` derives the output name with `filename.replace(".stp", ".gltf")`, which does **not** match a `.step` extension (so a `.step` upload would produce a wrongly-named output and break the hierarchy parse). This is a *pre-existing* bug, not introduced here.
   - *Assumption:* uploads use `.stp` (as the current code already implicitly requires).
   - *Impact if wrong:* `.step` uploads fail downstream regardless of converter. Worth fixing opportunistically (handle both extensions) but strictly outside this spec's stated scope — flag to the user whether to include the one-line fix.
5. **Vestigial `httpx` wrapper and dead helpers.** After the swap, `mayo_and_gltf.py` no longer needs `httpx`, `MAYO_SERVICE_URL`, or `safe_convert_with_mayo`; the `async with httpx.AsyncClient()` block wraps the body for no reason.
   - *Assumption:* remove `safe_convert_with_mayo` and the `convert_with_mayo` import (required for clean code), and **recommend** also removing the unused `httpx` client wrapper / import / `MAYO_SERVICE_URL` import as a tidy-up.
   - *Impact if wrong:* none functional; leaving them is harmless but misleading. Decision affects diff size only.
6. **Tessellation quality (`deflection=0.01`).** Controls mesh fidelity vs. file size/time. Mayo used chordal deflection 1.0 mm + angular 0.349 rad with `Precise` meshing.
   - *Assumption:* `test.py`'s `0.01` (with `unit_scale=0.001`, i.e. 0.01 in model units) is the intended quality and is kept.
   - *Impact if wrong:* meshes could be too coarse/fine or conversion slower than Mayo. Tunable via the `deflection` argument without code changes if needed.

## Definition of done (design review)
- [ ] It is confirmed (step 1) that `pythonocc-core` / `OCC.Core` actually imports in the backend environment, and the install method (pip vs conda vs wheel) is recorded; if pip cannot supply it, the setup-docs scope addition is agreed with the user.
- [ ] It is agreed that `occ_converter.py` is a **copy** of `test.py`'s logic (not an import of it), `test.py` is left unedited, and the copied `export_gltf` keeps the `(deflection=0.01, unit_scale=0.001)` defaults.
- [ ] The pipeline swap is scoped to: replace the converter call, capture/use its returned path, change the status text to `"Conversion Done"`, and drop the dead `convert_with_mayo` import + `safe_convert_with_mayo` helper — with **no** change to hierarchy/compression/RDF/import stages or their ordering (parse-before-compress preserved).
- [ ] The route plan is agreed: `bypass_step.py` → `/ws/convert-bypass`, `mayo_and_gltf.router` re-enabled, and it is confirmed (grep result) that no frontend code consumes the bypass path so no frontend change is needed.
- [ ] A decision is recorded on the **axis-orientation** question (accept possible rotation for v1, or add a transform as a deliberate divergence) — Open Question 2.
- [ ] A decision is recorded on the optional cleanups (vestigial `httpx`/`MAYO_SERVICE_URL` wrapper) and on whether to opportunistically fix the `.step` extension handling — Open Questions 4 & 5.
- [ ] It is confirmed the downstream contract is unchanged: external `.gltf`+`.bin` co-located, POSITION accessor min/max present, node renaming handled by `return_gltf_hierarchy`, GLB built after the rename.
- [ ] The WebSocket message sequence and `{status, text}` shape are confirmed identical to today except for the single text change, so `UploadSTEPModal.tsx` needs no edits.
