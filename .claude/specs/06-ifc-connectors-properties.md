# Spec: IFC Connectors Properties (IfcDistributionPort)

## Overview
This feature lets a user attach an **IfcDistributionPort** ("connector") to any
distribution element in the IFC hierarchy editor. When a node is classified as
`IfcDistributionElement` or `IfcDistributionControlElement` (kept in an
extensible array so more classes can be added later), the
`IFCNodeDetails` component reveals a new **IfcDistributionPort** section. There
the user can optionally pick the port's three enumerated attributes
(`SystemType`, `PredefinedType`, `FlowDirection`) and select/fill applicable
property sets — reusing the exact same checkbox + property-input logic already
used for the element's own psets.

On submit, the backend creates a brand-new `ifc:IfcDistributionPort` individual
named `Port_<elementNodeName>` and nests it under the element through an
`ifc:IfcRelNests` relationship (with its own GlobalIds), plus the chosen
attribute/pset triples, and writes them to Virtuoso. As with the existing IFC
properties form, the same configuration is applied to **all selected
occurrences of the same type**. The hierarchy-refresh queries are extended to
read this data back so an already-filled port is shown when the element is
reopened, and the port data is carried on the `TreeNode` object so it travels to
the Blender conversion script untouched (the Blender script itself is **not**
edited in this feature).

## Depends on
- Step 05 (`ifc-psets-schema-generation`) — provides `ifcPropertySchema.json`,
  `resourcesIFCSchema.json` and the XSD/pset XML sources this feature reuses.
- The existing IFCPage NodeDetails UI, `add-ifc-properties` route, hierarchy
  refresh query, and `buildTree`/`TreeNode` model.

## Routes
Extend the existing route — **no brand-new route**:
- `POST /api/add-ifc-properties` — extended to accept an optional
  `distribution_port` object in the request body and, when present, emit the
  IfcDistributionPort + IfcRelNests triples for every matched subject — access:
  logged-in (unchanged).

(Rationale: the form is a single submit per node and the port relates to the
same subject already resolved in this route; adding a second endpoint would
duplicate the metadata→subject SPARQL lookup and the per-occurrence loop.)

## Database changes
No schema/table changes (RDF triple store, not a relational DB). New **triples**
only, written into the active project graph. Per matched subject (the element):

**IfcDistributionPort individual** — `port_uri = GRAPH_NAMESPACE["Port_" + <nodeName>]`:
- `rdf:type ifc:IfcDistributionPort`
- `ifc:name_IfcRoot` → new `ifc:IfcLabel` whose `rdf:value` is `"Port_" + <nodeName>`
- `ifc:globalId_IfcRoot` → new `ifc:IfcGloballyUniqueId` (fresh `ifcopenshell.guid.new()`)
- if `system_type` set: `ifc:systemType_IfcDistributionPort` → `ifc:<SystemTypeEnumValue>`
- if `predefined_type` set: `ifc:predefinedType_IfcDistributionPort` → `ifc:<PortTypeEnumValue>`
- if `flow_direction` set: `ifc:flowDirection_IfcDistributionPort` → `ifc:<FlowDirectionEnumValue>`
- property sets: same `IfcRelDefinesByProperties` / `IfcPropertySet` /
  `IfcPropertySingleValue` triple pattern as element psets, but defining
  `port_uri` instead of the element, and with port-scoped URI keys to avoid
  collision with the element's own psets.

**IfcRelNests individual** — `rel_nests_uri = GRAPH_NAMESPACE["IfcRelNests_" + <nodeName>]`:
- `rdf:type ifc:IfcRelNests`
- `ifc:globalId_IfcRoot` → new `ifc:IfcGloballyUniqueId` (fresh guid)
- `ifc:relatingObject_IfcRelNests` → element subject
- `ifc:relatedObjects_IfcRelNests` → `port_uri`

**Element subject** (the IfcDistributionElement / IfcDistributionControlElement):
- `ifc:isNestedBy_IfcObjectDefinition` → `rel_nests_uri`

**Port → relationship back-reference**:
- `port_uri ifc:nests_IfcObjectDefinition` → `rel_nests_uri`

Enum object values (`SystemType`, `PredefinedType`, `FlowDirection`) are written
as `IFC_NAMESPACE[<value>]` URIs, mirroring how `predefinedType_<class>` is
already stored for elements.

## Templates
Not a templated project (React SPA). UI impact:
- **Modify** `frontend/src/pages/IFCPage/NodeDetails/IFCNodeDetails.tsx` — add the
  conditional **IfcDistributionPort** section (attributes + property sets) shown
  only when the selected IFC class is in `PORT_CAPABLE_CLASSES`.

## Files to create
- `frontend/scripts/generate-distribution-port-from-xml.cjs` — extraction script
  (CommonJS, Node built-ins only) that reads the IFC XSD + pset XML files and
  writes `ifcDistributionPort.json`.
- `frontend/src/pages/IFCPage/NodeDetails/ifcDistributionPort.json` — generated
  data file consumed by the React component.

## Files to change
- `frontend/package.json` — add npm script
  `"generate:distribution-port": "node scripts/generate-distribution-port-from-xml.cjs"`
  (and optionally chain it into a combined `generate:ifc-full`).
- `frontend/src/pages/IFCPage/NodeDetails/IFCNodeDetails.tsx` — port section,
  state, init-from-node, and submit payload (see UI section).
- `frontend/src/pages/STEPPage/Hierarchy/buildTree.ts` — add `distributionPort`
  to `TreeNode`; add two new input arrays (`portData`, `portPsetData`) and
  populate `node.distributionPort`.
- `frontend/src/pages/STEPPage/Hierarchy/HierarchyButtons/buttons/UpdateHierarchyButton.tsx`
  — add the port attribute query + port pset query and pass them to `buildTree`.
- `backend/api/routes/add_ifc_prop.py` — extend `IFCProps` model and the route to
  build the port/nest triples.

## New dependencies
No new dependencies (frontend script is Node built-ins only; backend reuses
`rdflib` + `ifcopenshell` already imported in `add_ifc_prop.py`).

---

## Part 1 — Extraction script `generate-distribution-port-from-xml.cjs`

**Purpose:** Produce `ifcDistributionPort.json` describing the IfcDistributionPort
attribute enums and its applicable property sets, in a shape the React component
can consume with the same property-input logic it already uses (the `dataType`
values resolve against the existing `resourcesIFCSchema.json`).

Model it on `generate-psets-from-xml.cjs` (same XSD/XML helpers, same regex
parsing — no third-party XML parser).

### Algorithm
1. Read `frontend/public/ifc-schema/IFC4X3_DEV_dcfeedc.xsd`.
2. **Attribute enums** — parse simple types (reuse `parseSimpleTypes`) and
   collect enumeration values (preserving XSD order) for:
   - `IfcDistributionPortTypeEnum` → `attributes.PredefinedType`
   - `IfcDistributionSystemEnum`  → `attributes.SystemType`
   - `IfcFlowDirectionEnum`       → `attributes.FlowDirection`

   Append `"NOTDEFINED"` if the enum lacks it (so the UI always has a default),
   and keep `"USERDEFINED"` where the XSD declares it. Do **not** uppercase —
   keep the exact XSD `value=` casing used elsewhere for enum object URIs.
3. **Property sets** — read every `*.xml` in `public/ifc-schema/psets/`, reuse the
   `parsePsetFile` logic, and keep only sets whose `ApplicableClasses` include
   `IfcDistributionPort` (directly or via descendant expansion — for ports the
   direct match on `IfcDistributionPort` is what matters). Build each set as
   `{ name, definition, properties:[{name, definition, dataType, options?}], predefinedTypes? }`,
   identical in shape to `propertySets` entries in `ifcPropertySchema.json`.
   - Preserve the `ClassName` `Ifc.../PREDEFINEDTYPE` restriction → `predefinedTypes`
     (e.g. `Pset_DistributionPortTypeCable` → `["CABLE"]`) exactly as the existing
     pset script does, so the section can grey out non-applicable sets by the
     port's chosen PredefinedType.
   - Enumerated properties emit inline `options` (so the component does not depend
     on a `resources` regeneration). Non-enumerated `dataType`s resolve against
     `resourcesIFCSchema.json` at runtime (already populated by `generate:psets`,
     which scans all pset files including the DistributionPort ones).
4. Write `ifcDistributionPort.json` (pretty-printed, trailing newline), psets
   sorted by name. Idempotent.

### Output shape — `ifcDistributionPort.json`
```json
{
  "name": "IfcDistributionPort",
  "attributes": {
    "PredefinedType": ["CABLE", "CABLECARRIER", "DUCT", "PIPE", "...", "USERDEFINED", "NOTDEFINED"],
    "SystemType":     ["AIRCONDITIONING", "...", "USERDEFINED", "NOTDEFINED"],
    "FlowDirection":  ["SOURCE", "SINK", "SOURCEANDSINK", "NOTDEFINED"]
  },
  "propertySets": [
    {
      "name": "Pset_DistributionPortCommon",
      "definition": "Common properties ...",
      "properties": [
        { "name": "Status", "definition": "...", "dataType": "PEnum_ElementStatus", "options": ["NEW", "..."] }
      ]
    },
    {
      "name": "Pset_DistributionPortTypeCable",
      "definition": "...",
      "properties": [ "..." ],
      "predefinedTypes": ["CABLE"]
    }
  ]
}
```

### npm command
```
"generate:distribution-port": "node scripts/generate-distribution-port-from-xml.cjs"
```

---

## Part 2 — UI changes in `IFCNodeDetails.tsx`

1. **Import** `ifcDistributionPort.json` and type it (reuse `PSetSpec`,
   `PropertyPayload` types). Build:
   ```ts
   const PORT_CAPABLE_CLASSES = ["IfcDistributionElement", "IfcDistributionControlElement"];
   ```
   (single source of truth — extending it later automatically enables the section).
2. **Visibility:** show the new "IfcDistributionPort" `<section>` only when
   `PORT_CAPABLE_CLASSES.includes(ifcClass)`.
3. **Attributes:** three optional `<select>`s — System Type, Predefined Type,
   Flow Direction — each sourced from `ifcDistributionPort.attributes.*`, each
   with a leading "— (none) —" / unset option so the user can leave any attribute
   out (only set ones become triples).
4. **Property sets:** reuse the *same* rendering and handlers used for element
   psets (checkbox + per-property input by `resolvePropertyInputType` /
   `resolvePropertyPrimitiveDataType`), driven by
   `ifcDistributionPort.propertySets`. Apply the existing predefined-type-gating
   logic, but gate against the **port's** chosen PredefinedType
   (`isPsetApplicableFor`-style helper using `portPredefinedType`).
5. **New state:** `portSystemType`, `portPredefinedType`, `portFlowDirection`,
   `portSelectedPsets`, `portPropertyValues` — mirroring the element pset state.
6. **Init from node:** in the existing "initialize from `primaryNodeData`"
   effect, also hydrate the port state from `primaryNodeData.distributionPort`
   (attributes + psets) so an already-filled port is shown on reopen. Reset them
   in `onIFCPropertiesFormReset`.
7. **Submit:** in `onIFCPropertiesFormSubmit`, when the class is port-capable and
   the user set at least one attribute or pset, add a `distribution_port` object
   to the POST body:
   ```ts
   distribution_port: {
     system_type: portSystemType || null,
     predefined_type: portPredefinedType || null,
     flow_direction: portFlowDirection || null,
     property_sets: <same PropertyPayload map shape as property_sets>,
   }
   ```
   Build the payload with the same `ifc_value` / `data_type` derivation used for
   element psets. After all POSTs succeed, write `distributionPort` onto each
   updated node via `updateNodeInTree` (and `primaryNodeData`) so the in-memory
   tree matches the DB without a full refresh.

---

## Part 3 — `TreeNode` + `buildTree` changes

Add to `TreeNode` in `buildTree.ts`:
```ts
distributionPort?: {
  name: string;              // "Port_<elementName>"
  systemType?: string;
  predefinedType?: string;
  flowDirection?: string;
  psets?: {
    [psetName: string]: { [propertyName: string]: string | number | boolean };
  };
};
```
- Add two parameters to `buildTree`: `portData[]`
  (`{ node, port, portName, systemType, predefinedType, flowDirection }`) and
  `portPsetData[]` (`{ node, psetName, propName, propValue, datatype }`).
- Normalize enum URIs (`split("#").pop()`) before storing.
- Populate `treeNode.distributionPort` from `portData`, and fill
  `distributionPort.psets` from `portPsetData` using the same datatype-coercion
  logic already used for element psets.
- Because `DownloadIFCButton` already sends the entire `node` over the WebSocket,
  adding this field is sufficient to deliver the port data to the Blender script
  — **no Blender code is edited in this feature** (the user will wire it up
  manually).

## Part 4 — Hierarchy refresh queries (`UpdateHierarchyButton.tsx`)

Add two SPARQL queries and feed their results into `buildTree`:

**Port attributes** (maps each port back to its nesting element `?node`):
```sparql
PREFIX ifc: <https://w3id.org/ifc/IFC4X3_ADD2#>
SELECT ?node ?port ?portName ?systemType ?predefinedType ?flowDirection
FROM <${graphUri}>
WHERE {
  ?rel a ifc:IfcRelNests .
  ?rel ifc:relatingObject_IfcRelNests ?node .
  ?rel ifc:relatedObjects_IfcRelNests ?port .
  ?port a ifc:IfcDistributionPort .
  OPTIONAL { ?port ifc:name_IfcRoot ?nameLabel . ?nameLabel rdf:value ?portName . }
  OPTIONAL { ?port ifc:systemType_IfcDistributionPort ?systemType . }
  OPTIONAL { ?port ifc:predefinedType_IfcDistributionPort ?predefinedType . }
  OPTIONAL { ?port ifc:flowDirection_IfcDistributionPort ?flowDirection . }
}
```

**Port property sets** (same structure as `ifcPsetQuery`, but the pset defines
the `?port` and the result is keyed by the element `?node`):
```sparql
PREFIX ifc: <https://w3id.org/ifc/IFC4X3_ADD2#>
PREFIX express: <https://w3id.org/express#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>
SELECT ?node ?psetName ?propName ?propValue ?datatype
FROM <${graphUri}>
WHERE {
  ?rel a ifc:IfcRelNests .
  ?rel ifc:relatingObject_IfcRelNests ?node .
  ?rel ifc:relatedObjects_IfcRelNests ?port .
  ?port a ifc:IfcDistributionPort .
  ?s a ifc:IfcRelDefinesByProperties .
  ?s ifc:relatedObjects_IfcRelDefinesByProperties ?port .
  ?s ifc:relatingPropertyDefinition_IfcRelDefinesByProperties ?pset .
  ?pset ifc:name_IfcRoot ?label .       ?label express:hasString ?psetName .
  ?pset ifc:hasProperties_IfcPropertySet ?prop .
  ?prop ifc:name_IfcProperty ?identifier . ?identifier express:hasString ?propName .
  ?prop ifc:nominalValue_IfcPropertySingleValue ?value .
  ?value ?p ?propValue . ?p a owl:DatatypeProperty .
  BIND(DATATYPE(?propValue) AS ?datatype)
}
```

---

## Part 5 — Backend `add_ifc_prop.py` changes

1. Extend the Pydantic model:
   ```python
   class DistributionPort(BaseModel):
       system_type: str | None = None
       predefined_type: str | None = None
       flow_direction: str | None = None
       property_sets: Dict[str, Dict[str, Any]] | None = None

   class IFCProps(BaseModel):
       ...
       distribution_port: DistributionPort | None = None
   ```
2. After the existing element triples are built, **for each matched subject**
   `bind["s"]` create the port + nest triples described in *Database changes*:
   - derive `node_name = subject.split("#")[-1]`;
   - `port_uri = GRAPH_NAMESPACE["Port_" + node_name]`,
     `rel_nests_uri = GRAPH_NAMESPACE["IfcRelNests_" + node_name]`;
   - emit type, name-label (`"Port_" + node_name`), and fresh GUIDs for both
     `port_uri` and `rel_nests_uri` using the same GUID pattern already in the
     file (`globalId_IfcRoot` → `IfcGloballyUniqueId` with `rdf:value`);
   - wire `relatingObject_IfcRelNests`, `relatedObjects_IfcRelNests`,
     `isNestedBy_IfcObjectDefinition`, `nests_IfcObjectDefinition`;
   - add `systemType_IfcDistributionPort` / `predefinedType_IfcDistributionPort` /
     `flowDirection_IfcDistributionPort` → `IFC_NAMESPACE[value]` only for set
     attributes;
   - build the port property sets with the **same** IfcRelDefinesByProperties /
     IfcPropertySet / IfcPropertySingleValue logic, but with URI keys scoped by
     `Port_<node_name>` so they never collide with the element's own pset URIs,
     and relating to `port_uri` (`relatedObjects_IfcRelDefinesByProperties` →
     `port_uri`, `port_uri isDefinedBy_IfcObject` → rel).
3. Serialize and `import_to_db` exactly as today (one graph for the whole
   request is fine; keep the single `g`).

---

## Rules for implementation
- The extraction script is CommonJS (`.cjs`), uses only Node built-ins
  (`fs`, `path`) and the same regex/scan approach as the existing generators — no
  third-party XML parser, no transpilation.
- Keep the extraction script idempotent — re-running yields identical output.
- `PORT_CAPABLE_CLASSES` must be a single array constant so adding a class later
  needs no other UI change.
- The port property-set UI must **reuse** the existing pset rendering and value
  handlers (no parallel copy of the input-type logic) — only the state buckets
  and the data source (`ifcDistributionPort.propertySets`) differ.
- Enum attribute object values are stored/read as `ifc:` URIs; always normalize
  with `split("#").pop()` before display.
- The port name is exactly `"Port_" + <elementNodeName>` (the metadata/local name
  used elsewhere in the route).
- Apply the configuration to **all** selected occurrences of the same type, just
  like the existing IFC properties submit loop.
- **Do not edit any Blender script** — only ensure `distributionPort` is present
  on the `TreeNode` sent over the WebSocket.
- Backend: parameterised / safe SPARQL only; build triples with `rdflib` (no
  string-concatenated SPARQL inserts). (No SQLAlchemy or ORMs — not applicable;
  this is an RDF triple store.)

## Definition of done
- [ ] `npm run generate:distribution-port` runs without error and writes
      `frontend/src/pages/IFCPage/NodeDetails/ifcDistributionPort.json` with
      non-empty `attributes.PredefinedType`, `attributes.SystemType`,
      `attributes.FlowDirection`, and a `propertySets` array that includes
      `Pset_DistributionPortCommon`.
- [ ] `Pset_DistributionPortTypeCable` appears with `predefinedTypes: ["CABLE"]`.
- [ ] Selecting an `IfcDistributionElement` (or `IfcDistributionControlElement`)
      node reveals the IfcDistributionPort section; selecting any other class
      hides it.
- [ ] Choosing port attributes/psets and submitting creates, in Virtuoso, an
      `ifc:IfcDistributionPort` named `Port_<node>` linked to the element via
      `ifc:IfcRelNests` (`relatingObject`/`relatedObjects`), with
      `isNestedBy_IfcObjectDefinition` / `nests_IfcObjectDefinition`
      back-references and both individuals carrying their own
      `ifc:IfcGloballyUniqueId`.
- [ ] Set attributes appear as `systemType_IfcDistributionPort` /
      `predefinedType_IfcDistributionPort` / `flowDirection_IfcDistributionPort`
      triples; unset attributes produce no triple.
- [ ] Submitting with multiple occurrences selected creates a port for each
      occurrence of that type.
- [ ] Refreshing the hierarchy and reopening a filled element shows its port
      attributes and pset values populated in the section.
- [ ] `TreeNode.distributionPort` is populated after refresh and is included in
      the object logged/sent by `DownloadIFCButton` (verify via console / network
      that the WebSocket payload contains `distributionPort`).
- [ ] No Blender script files were modified.
