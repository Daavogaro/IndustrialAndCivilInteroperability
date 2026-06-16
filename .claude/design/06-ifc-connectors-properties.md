# Design: IFC Connectors Properties (IfcDistributionPort)

## Summary
This plan covers attaching an **IfcDistributionPort** ("connector") to any node
classified as one of a small, extensible set of distribution classes
(`IfcDistributionElement`, `IfcDistributionControlElement`). It spans four
layers: (1) a build-time extraction script that writes `ifcDistributionPort.json`
(the port's three attribute enums + its applicable property sets); (2) a
conditional **IfcDistributionPort** section in `IFCNodeDetails.tsx` that reuses
the existing pset rendering and submit logic; (3) an extension of the existing
`POST /api/add-ifc-properties` route that, per matched occurrence, creates an
`IfcDistributionPort` named `Port_<nodeName>` nested under the element via
`IfcRelNests` (with attributes and psets); and (4) hierarchy read-back queries +
a new `TreeNode.distributionPort` field so a filled port is shown on reopen and
travels to the Blender script unchanged.

It does **NOT** cover any Blender script change (explicitly out of scope — the
user will wire the new `TreeNode.distributionPort` field into Blender manually),
and it does **NOT** introduce edit/delete-and-replace semantics for previously
written triples (see Open Questions — `import_to_db` is insert-only, a
limitation the existing element-pset flow already has).

Reading the real code surfaced several findings that are the backbone of this
design and that materially refine the written spec:

1. **The XSD enum values are lowercase, but the convention is UPPERCASE.** The
   XSD declares `value="cable"`, `value="airconditioning"`, `value="sink"`, yet
   the existing `generate-ifc-schema-from-xsd.cjs` uppercases every enum value
   (so `ifcPropertySchema.json` carries `ELECTRICACTUATOR`, `NOTDEFINED`, …) and
   the backend stores `predefinedType` as `IFC_NAMESPACE[<uppercase>]`. The new
   script must therefore **uppercase** the port enum values, and the backend must
   store the port attribute objects as `IFC_NAMESPACE[<uppercase>]` to stay
   consistent. A casing mismatch would create divergent enum individuals.
2. **The existing enum parser only matches `…TypeEnum`.** The regex in both
   generators keys on `Ifc…TypeEnum`. Of the three port attributes, only
   `IfcDistributionPortTypeEnum` matches; `IfcDistributionSystemEnum` and
   `IfcFlowDirectionEnum` would be silently missed. The new script needs a
   **generic `Ifc…Enum`** parser (or three explicit lookups).
3. **`import_to_db` is `INSERT DATA` only** — no `DELETE`/clear. Re-submitting a
   node adds triples on top of existing ones; because GUIDs use a fresh
   `ifcopenshell.guid.new()` each call, re-submission yields duplicate
   `globalId`/value individuals. This is a **pre-existing** property of the
   element-pset flow; the port feature inherits it. Editing-an-existing-port
   cleanly is therefore out of scope unless a delete-insert is added (Open Q).
4. **The existing read queries naturally isolate the port.** `ifcQuery` requires
   `?node x3d:hasMetadata ?metadata`; the port has no metadata, so it is never
   mistaken for an element. The existing `ifcPsetQuery` will match the port's own
   psets with `?node = port` (an orphan never rendered, since the port is not in
   the x3d edges/roots) — harmless, and the **element's** `psets` stay clean. The
   new port-pset query re-keys port psets to the **element** node via
   `IfcRelNests` so they show in the port section.
5. **`DownloadIFCButton` already sends the entire `node`** over the WebSocket, so
   adding `TreeNode.distributionPort` is sufficient to deliver port data to
   Blender — no other wiring, and no Blender edit.

As with the 01–05 designs, this project has **no** `database/db.py`, **no**
`app.py` (the FastAPI entrypoint is `backend/app.py` mounting `api/routes/*`),
and **no** server-side templates. The skill's "Database design", "Route design",
and "Template design" sections are adapted to **Triple/RDF design**, **Backend
route design**, and **UI-integration design** respectively.

## Implementation order
1. **Lock the data contract.** Pin the exact `ifcDistributionPort.json` shape
   against how `IFCNodeDetails.tsx` reads psets (`PSetSpec`, `resolvePropertyInputType`,
   `options`, the `data_type`/`ifc_value` submit payload). The port psets must be
   byte-shape-identical to `propertySets` entries in `ifcPropertySchema.json` so
   the same renderer/handlers work unchanged.
2. **Build the extraction script** `generate-distribution-port-from-xml.cjs`
   (mirrors `generate-psets-from-xml.cjs`), wire the npm command, regenerate, and
   verify the JSON (enums non-empty + uppercase; `Pset_DistributionPortCommon`
   present; `Pset_DistributionPortTypeCable` carries `predefinedTypes:["CABLE"]`).
3. **Extend the backend route** to accept `distribution_port` and emit the
   port/nest/attribute/pset triples per matched subject. Do this before the UI so
   the UI can be tested end-to-end against a live endpoint.
4. **Extend `TreeNode` + `buildTree`** with `distributionPort` and the two new
   input arrays, then **add the two SPARQL queries** in `UpdateHierarchyButton.tsx`
   and pass them through. This makes read-back work and is a prerequisite for the
   UI's "show existing port on reopen".
5. **Add the UI section** in `IFCNodeDetails.tsx`: the `PORT_CAPABLE_CLASSES`
   constant, the conditional section (attributes + reused pset renderer), the new
   state buckets, init-from-node hydration, submit-payload extension, and reset.
6. **Validate** against the spec's Definition of Done (create a port, multi-select
   occurrences, reopen a filled element, confirm WebSocket payload carries
   `distributionPort`, confirm no Blender file changed).

## Triple/RDF design (replaces "Database design")
No relational schema. New **triples** only, written into the active project
graph via the existing `import_to_db` (`INSERT DATA`). All names below use the
existing constants: `GRAPH_NAMESPACE` = `https://elettra2.0#`, `IFC_NAMESPACE` =
`https://w3id.org/ifc/IFC4X3_ADD2#`, `EXPRESS_NAMESPACE`, `XSD_NAMESPACE`.

Let `node_name = subject.split("#")[-1]` for each matched occurrence subject
(the element). The following are created **per subject, inside the existing
binding loop** (so each occurrence gets its own port — see Logic design, and note
this differs from element psets, which are built once and shared across
occurrences).

### IfcDistributionPort individual — `GRAPH_NAMESPACE["Port_" + node_name]`
- type `ifc:IfcDistributionPort`.
- **Name:** `ifc:name_IfcRoot` → a new `ifc:IfcLabel`
  (`GRAPH_NAMESPACE["Name_Port_" + node_name]`) whose value is the string
  `"Port_" + node_name`. **Literal predicate:** use `RDF.value` (mirroring how
  the element subject's name label is written at the bottom of the existing
  route), so the read-back query's `?nameLabel rdf:value ?portName` matches.
- **GlobalId:** `ifc:globalId_IfcRoot` → a new `ifc:IfcGloballyUniqueId`
  (`GRAPH_NAMESPACE["GUID_Port_" + node_name]`) with `RDF.value` = fresh
  `ifcopenshell.guid.new()` (mirrors the element subject's GUID pattern).
- **Attributes (only when set by the user):**
  - `ifc:systemType_IfcDistributionPort` → `IFC_NAMESPACE[<SystemType UPPERCASE>]`
  - `ifc:predefinedType_IfcDistributionPort` → `IFC_NAMESPACE[<PortType UPPERCASE>]`
  - `ifc:flowDirection_IfcDistributionPort` → `IFC_NAMESPACE[<FlowDirection UPPERCASE>]`
  - (object values mirror the element's `predefinedType_<class>` storage.)
- **Property sets:** same triple pattern as the element psets
  (`IfcRelDefinesByProperties` → `IfcPropertySet` → `IfcPropertySingleValue` →
  nominal value with `express:hasString`/`hasInteger`/`hasDouble`/`hasBoolean`),
  but the relationship's `relatedObjects_IfcRelDefinesByProperties` points to the
  **port** and the URIs are **scoped with `Port_` + node_name** so they never
  collide with the element's own pset URIs.

### IfcRelNests individual — `GRAPH_NAMESPACE["IfcRelNests_" + node_name]`
- type `ifc:IfcRelNests`.
- **GlobalId:** `ifc:globalId_IfcRoot` → new `ifc:IfcGloballyUniqueId`
  (`GRAPH_NAMESPACE["GUID_RelNests_" + node_name]`), `RDF.value` = fresh GUID.
- `ifc:relatingObject_IfcRelNests` → element subject.
- `ifc:relatedObjects_IfcRelNests` → the port URI.

### Element subject back-reference
- `ifc:isNestedBy_IfcObjectDefinition` → the `IfcRelNests` URI.

### Port → relationship back-reference
- port URI `ifc:nests_IfcObjectDefinition` → the `IfcRelNests` URI.

### Literal-predicate consistency (locked decision)
The existing route is **inconsistent** by design: the element subject's
name/GlobalId use `RDF.value`, while pset labels/identifiers use
`express:hasString`. To keep read/write symmetric:
- Port **name** and **GlobalId** (port and RelNests) → `RDF.value` (read back
  with `rdf:value`).
- Port **psets** → reuse the existing pset writer verbatim
  (`express:hasString` for labels/identifiers, typed `express:has*` for nominal
  values), read back by the existing/new pset query with `express:hasString`.

### "Migration"
None. Triples are added to an existing graph. There is **no delete-insert**, so
re-submission accumulates triples (Open Q 3). Reading back is purely additive.

## Backend route design (replaces "Route design")

### `POST /api/add-ifc-properties` (extended)
- **Purpose / behaviour:** unchanged for the element; additionally, when a
  `distribution_port` object is present and the element class is port-capable,
  create the port + nest + attribute + pset triples above for every matched
  occurrence.
- **Request inputs (additive):** a new optional `distribution_port` object:
  - `system_type: str | null`
  - `predefined_type: str | null`
  - `flow_direction: str | null`
  - `property_sets: Dict[str, Dict[str, Any]] | null` (same shape as the existing
    `property_sets`: `{ psetName: { propName: { value, ifc_value, data_type } } }`).
  Modelled as a nested Pydantic `DistributionPort` model added to `IFCProps`,
  defaulting to `None` (backward compatible — existing callers unaffected).
- **Validation rules:**
  - If `distribution_port` is `None` → behave exactly as today.
  - Each attribute is emitted **only if truthy** (non-empty string). Empty/None →
    no triple (lets the UI's "not set" option mean "omit").
  - Pset property values reuse the existing per-`data_type` coercion
    (`STRING`/`DATE`/`INTEGER`/`DOUBLE`|`REAL`/`BOOLEAN`/`HEX_BINARY`); empty
    values are skipped exactly as today.
  - No server-side check that the class is "port-capable" is required (the UI
    gates it); optionally guard by only emitting when `distribution_port` is
    present. Recommend trusting the payload to keep the route simple.
- **Auth / access:** unchanged (same as the existing route).
- **Success flow:** all element triples (as today) **plus** the port/nest triples
  per subject are added to the single `rdflib.Graph`, serialized to N-Triples, and
  `import_to_db`'d in one request. Response shape unchanged
  (`{status:"success", text:…}`).
- **Error flow:** same failure modes as today (Virtuoso unreachable → request
  raises; the frontend already treats a non-`ok` response per uri as a failure and
  surfaces "Failed to update N node(s)"). A malformed date string in a port pset
  would raise the same `strptime` error the element flow already has — not newly
  introduced.

(No new route. Rationale recorded in the spec: a second endpoint would duplicate
the metadata→subject SPARQL lookup and the per-occurrence loop.)

## UI-integration design (replaces "Template design")
No templates. One modified file.

### Modified: `frontend/src/pages/IFCPage/NodeDetails/IFCNodeDetails.tsx`
**What exists now:** a single form with Basic properties (IFC Class / Predefined
Type / Userdefined Type) and a Property Sets block driven by
`ifcPropertySchema.json` via `availablePsets`, `togglePsetSelection`,
`updatePropertyValue`, `resolvePropertyInputType`,
`resolvePropertyPrimitiveDataType`, and the `selectedPsets`/`propertyValues`
state. Submit loops over `uris`, POSTs per uri, then patches the tree via
`updateNodeInTree`. An init effect hydrates state from `primaryNodeData`.

**What is added:**
1. **Imports/constants:** import `ifcDistributionPort.json`; type it (reuse
   `PSetSpec`/`PropertyPayload`); define
   `const PORT_CAPABLE_CLASSES = ["IfcDistributionElement", "IfcDistributionControlElement"]`
   as the single source of truth. Derive `isPortCapable = PORT_CAPABLE_CLASSES.includes(ifcClass)`.
2. **New state:** `portSystemType`, `portPredefinedType`, `portFlowDirection`
   (strings, default `""` meaning "not set"), `portSelectedPsets`
   (`Record<string,boolean>`), `portPropertyValues`
   (`Record<string, Record<string, string|number|boolean>>`) — mirroring the
   element pset state.
3. **New section (rendered only when `isPortCapable`):** a titled
   "IfcDistributionPort" block after the element's Property Sets:
   - Three `<select>`s — System Type, Predefined Type, Flow Direction — each with
     a leading "— (not set) —" option (value `""`) followed by the values from
     `ifcDistributionPort.attributes.{SystemType,PredefinedType,FlowDirection}`.
   - A property-set list **reusing the exact same JSX/handlers** as the element
     psets, but bound to `ifcDistributionPort.propertySets`, `portSelectedPsets`,
     and `portPropertyValues`. Implement by parameterising the existing
     pset-rendering and toggle/update handlers over (spec, selected, values,
     setters) — not by copy-pasting the input-type branches. Apply the same
     predefined-type gating, but gated by `portPredefinedType`.
4. **Submit (`onIFCPropertiesFormSubmit`):** when `isPortCapable`, build a
   `distribution_port` payload:
   - `system_type: portSystemType || null`, etc.
   - `property_sets`: the same `PropertyPayload` map the element builds, using
     `resolvePropertyPrimitiveDataType`/`property.dataType` against the port spec.
   Add it to the per-uri POST `body`. After all POSTs succeed, write a
   `distributionPort` object onto each updated node via `updateNodeInTree` (and
   `primaryNodeData`) so the in-memory tree matches the DB without a full refresh.
5. **Init-from-node effect:** also hydrate the three port attributes and port
   psets from `primaryNodeData.distributionPort` (normalising enum values with
   `normalizeIfcName`) so reopening a filled element shows the port populated.
6. **Reset (`onIFCPropertiesFormReset`):** clear all five port state buckets.

**Deliberately unchanged:** the element pset logic, the input-rendering branches
(`boolean`/`select`/passthrough), and the existing submit/patch flow.

**Conditional display:** the port section shows iff `isPortCapable`; selecting
any other class (or `None`) hides it and its state is irrelevant to the payload.

## Logic design (prose only, no code)

### Extraction script — `generate-distribution-port-from-xml.cjs`
- **Responsibility:** produce `ifcDistributionPort.json`
  (`{ name:"IfcDistributionPort", attributes:{PredefinedType[],SystemType[],FlowDirection[]}, propertySets:[…] }`).
- **Inputs:** the committed XSD (`public/ifc-schema/IFC4X3_DEV_dcfeedc.xsd`) and
  the pset XML corpus (`public/ifc-schema/psets/*.xml`).
- **Outputs:** one JSON file in `src/pages/IFCPage/NodeDetails/`. Idempotent.
- **Method / decision tree:**
  - **Attributes:** parse simple types, but with a **generic** matcher for
    `Ifc[A-Za-z0-9_]+Enum` (NOT just `…TypeEnum`, finding #2), collect
    `<xs:enumeration value="…"/>` values **UPPERCASED** (finding #1), preserving
    XSD order. Read `IfcDistributionPortTypeEnum` → `PredefinedType`,
    `IfcDistributionSystemEnum` → `SystemType`, `IfcFlowDirectionEnum` →
    `FlowDirection`. Append `"NOTDEFINED"` if absent so the UI always has a
    safe default; keep `"USERDEFINED"` where present.
  - **Property sets:** reuse the `parsePsetFile`/`parsePropertyDef` logic from
    `generate-psets-from-xml.cjs` (same XML helpers, entity decode, whitespace
    normalisation, enumerated→inline `options`+`PEnum_*` dataType, table→single
    value, reference/complex→skip). Keep only sets whose `ApplicableClasses`
    contain `IfcDistributionPort` (direct match — ports aren't an `IfcElement`
    subtree, so no descendant expansion is needed for them). Preserve the
    `ClassName` `…/PREDEFINEDTYPE` restriction as `predefinedTypes`
    (e.g. `Pset_DistributionPortTypeCable` → `["CABLE"]`).
  - **Resources:** do **not** rewrite `resourcesIFCSchema.json`. The existing
    `generate:psets` already scans **all** pset files (including the
    DistributionPort ones) and registers their data types, so every `dataType`
    the port psets reference already resolves in the component. Enumerated
    properties additionally carry inline `options`, so selects render even
    without a resources lookup. (Note this dependency: run `generate:psets`
    at least once so the resources catalogue is complete.)
  - Sort `propertySets` by name; pretty-print with trailing newline.
- **Side effects:** one file write; console summary.

### npm-command design
Add to `frontend/package.json` `"scripts"`:
- `generate:distribution-port` → `node scripts/generate-distribution-port-from-xml.cjs`.
- Optionally extend `generate:ifc-full` to also run it (after `generate:psets`,
  since the port psets rely on the resources catalogue being populated). Keeping
  it separate is also fine; recommend chaining for one-command regeneration.

### `TreeNode` + `buildTree` (`frontend/src/pages/STEPPage/Hierarchy/buildTree.ts`)
- **Add field:** `distributionPort?: { name:string; systemType?:string;
  predefinedType?:string; flowDirection?:string; psets?:{ [pset]:{ [prop]: string|number|boolean } } }`.
- **Add two parameters:** `portData[]`
  (`{ node, port, portName, systemType, predefinedType, flowDirection }`) and
  `portPsetData[]` (`{ node, psetName, propName, propValue, datatype }`).
- **Population:**
  - For each `portData` row: `getNode(node).distributionPort = { name: portName
    or "Port_"+localName, systemType?, predefinedType?, flowDirection? }`,
    normalising enum URIs with `split("#").pop()`.
  - For each `portPsetData` row: ensure `distributionPort.psets[psetName]` and set
    the property value using the **same datatype coercion** already used for
    element psets (the `datatype.split("#")[1]` string/integer/double/real/boolean
    branch).
- **Keying:** both arrays are keyed by the **element** `?node` (the queries map
  the port back to its nesting element), so they attach to the rendered element
  node, not the orphan port node.
- **Backward compatibility:** the two new params are appended; every existing
  `buildTree(...)` caller must pass the new arrays (only `UpdateHierarchyButton.tsx`
  calls it — see below). Default to `[]` if a caller can't provide them.

### Hierarchy queries (`UpdateHierarchyButton.tsx`)
- Add **port attributes query** and **port pset query** (both in the spec),
  fetched via `fetchQuery`, mapped to `portData`/`portPsetData`, and passed into
  the extended `buildTree`. Both are scoped `FROM <graphUri>` like the others.
- The port attribute query joins through `IfcRelNests`
  (`relatingObject`→element `?node`, `relatedObjects`→`?port a IfcDistributionPort`)
  and `OPTIONAL`-reads name/systemType/predefinedType/flowDirection.
- The port pset query is the existing `ifcPsetQuery` body with an added
  `IfcRelNests` join so `?node` is the **element** while the pset defines the
  **port**.
- **Interaction note (finding #4):** the pre-existing `ifcQuery` excludes the
  port (no `hasMetadata`); the pre-existing `ifcPsetQuery` will surface port psets
  under `?node = port`, which `buildTree` stores on an orphan node that is never
  rendered — harmless. No change to the existing queries is required.

### Blender delivery
`DownloadIFCButton` serialises the whole `node` to the WebSocket; once
`distributionPort` exists on the node it is included automatically. **No Blender
script is read or modified.**

## Dependency and integration notes
- **No new dependencies.** Frontend script: Node built-ins only (`fs`, `path`),
  same style as the existing generators. Backend: reuses `rdflib`, `requests`,
  `ifcopenshell`, and the `models.py` namespaces already imported in
  `add_ifc_prop.py`.
- **Integration points:** `ifcDistributionPort.json` is imported directly by
  `IFCNodeDetails.tsx` (picked up by Vite); the extended route is reached by the
  existing per-uri `fetch("/api/add-ifc-properties")`; `buildTree` is only called
  from `UpdateHierarchyButton.tsx` (`refreshStepHierarchy`).
- **Pre-flight verification:** confirm both `IfcDistributionElement` **and**
  `IfcDistributionControlElement` are present in `ifcPropertySchema.json` (so they
  are selectable in the class dropdown). `IfcDistributionElement` is confirmed
  present; `IfcDistributionControlElement` should be verified during step 5.

## Security checklist
- **Authentication / Authorisation:** the route inherits the app's existing
  posture (no per-route auth is present in `add_ifc_prop.py` today); this feature
  adds no new auth surface and no cross-tenant data access — writes target the
  caller-supplied `graph`, exactly as the existing route.
- **Input validation / sanitisation:** attribute values are constrained by the UI
  dropdowns (enum lists from the generated JSON); the backend emits an attribute
  triple only for a truthy value. Pset values reuse the existing typed coercion.
  The extraction script's inputs are trusted, version-controlled schema files.
- **Injection (SPARQL):** triples are built with `rdflib` and serialized to
  N-Triples, then wrapped in `INSERT DATA` — the same mechanism the existing route
  uses. **Caveat (pre-existing):** `import_to_db` string-concatenates the graph
  IRI and the serialized triples into the update; this is unchanged by this
  feature, but values that could break out of literals should be considered. The
  new attribute values are bounded enum tokens (low risk); pset string values flow
  through `rdflib` literal serialization (escaped). No new injection vector is
  introduced; the existing concatenation pattern is retained for consistency.
- **CSRF:** not applicable (JSON API, no cookie-based session/form posts beyond
  what already exists).
- **Sensitive data handling:** none — IFC geometry/metadata only.
- **Read-back queries:** parameterised by `graphUri` interpolation exactly as the
  existing hierarchy queries; values returned are normalised (`split("#")`) before
  display. No new trust boundary.

## Open questions
1. **Always create the port, or only when the user engaged the section?**
   - *Assumption:* create the port + `IfcRelNests` whenever the class is
     port-capable **and** a `distribution_port` payload is sent; the UI sends the
     payload whenever the section is visible (even if attributes/psets are empty),
     so every port-capable submit yields a port skeleton.
   - *Impact if wrong:* if the user wants a port only when at least one
     attribute/pset is set, gate the payload in the UI on "non-empty". Contained
     change (one condition in submit).
2. **"Not set" vs `NOTDEFINED` for attributes.**
   - *Assumption:* a leading "— (not set) —" option (value `""`) means "emit no
     triple"; selecting `NOTDEFINED` explicitly emits a `NOTDEFINED` object.
   - *Impact if wrong:* if "not set" should default to `NOTDEFINED` triples,
     change the default and drop the empty option. Minor.
3. **Insert-only `import_to_db` → no clean re-edit.**
   - *Assumption:* accept the existing limitation; re-submitting a node adds
     duplicate triples (incl. new GUIDs), matching today's element-pset behaviour.
     "Show on reopen" works for the first write; editing is out of scope.
   - *Impact if wrong:* if true edit is required, add a `DELETE WHERE` for the
     node's existing port/nest/pset triples before insert (a larger, separate
     change touching `import_in_DB` or the route). Recommend a follow-up spec.
4. **Per-occurrence port vs shared.**
   - *Assumption:* create one port per matched subject (`Port_<subjectName>`),
     built inside the binding loop — this honours "Port_ + name of the node" and
     gives each occurrence its own `IfcRelNests`. (Element psets remain shared via
     the existing once-per-metadata construction.)
   - *Impact if wrong:* if a single shared port per type is desired, move port
     creation outside the binding loop and key it by metadata. Unlikely given the
     explicit naming requirement.
5. **`predefinedTypes` gating source for port psets.** Port psets like
   `Pset_DistributionPortTypeCable` are restricted to `CABLE`.
   - *Assumption:* gate the port pset selectability by the **port's**
     `PredefinedType` (reusing the element gating helper against `portPredefinedType`).
   - *Impact if wrong:* if all port psets should always be selectable, drop the
     gating for the port section. Minor.
6. **`generate:ifc-full` chaining.** Whether to add the new script to the combined
   command.
   - *Assumption:* add it (after `generate:psets`) for one-command regen; also
     keep a standalone `generate:distribution-port`.
   - *Impact if wrong:* trivial — a `package.json` line.

## Definition of done (design review)
- [ ] The `ifcDistributionPort.json` shape is confirmed identical (for
      `propertySets`) to `ifcPropertySchema.json` entries, so the existing pset
      renderer/handlers work unchanged; enum arrays are **UPPERCASE** and the
      script uses a **generic `…Enum`** parser (findings #1, #2).
- [ ] It is agreed the port + `IfcRelNests` are created **per matched occurrence**
      inside the binding loop, named `Port_<nodeName>`, with port-scoped pset URIs
      that cannot collide with element psets (Open Q 4).
- [ ] The literal-predicate convention is locked: port **name/GlobalId** use
      `RDF.value` (read with `rdf:value`); port **psets** reuse the existing
      `express:hasString`/typed-value writer and the existing pset query shape
      (finding, "Literal-predicate consistency").
- [ ] Attribute emission is agreed: emit a triple only for a truthy value;
      "— (not set) —" omits it (Open Q 2).
- [ ] The two read-back queries are agreed to key results by the **element** node
      (via `IfcRelNests`), and it is accepted that the pre-existing `ifcQuery`/
      `ifcPsetQuery` need no change (finding #4).
- [ ] `TreeNode.distributionPort` is agreed as the carrier to Blender, with **no
      Blender file edited**, and `DownloadIFCButton` requires no change (finding #5).
- [ ] The insert-only limitation (no clean edit/replace) is acknowledged and
      explicitly out of scope, or a delete-insert follow-up is agreed (Open Q 3).
- [ ] `PORT_CAPABLE_CLASSES` is a single array constant; both
      `IfcDistributionElement` and `IfcDistributionControlElement` are verified
      selectable in the class dropdown.
- [ ] The npm command(s) are agreed (`generate:distribution-port`, optional
      `generate:ifc-full` chaining) and the resources-catalogue dependency on
      `generate:psets` is noted (Open Q 6).
