# Spec: IFC Psets Schema Generation from XSD

## Overview
This feature replaces the current manual / web-ifc–driven approach for generating
`ifcPropertySchema.json` and `resourcesIFCSchema.json` with two Node.js build scripts
that derive everything from the authoritative IFC sources shipped in the repo:
the XSD schema (`frontend/public/ifc-schema/IFC4X3_DEV_dcfeedc.xsd`) for class
taxonomy and data-type mappings, and the Pset/Qto XML files
(`frontend/public/ifc-schema/psets/*.xml`) for property-set and quantity-set
definitions.  The result is a fully populated `ifcPropertySchema.json` where every
non-abstract, non-type IFC element class carries the correct predefined-type
enumeration and all applicable property/quantity sets with per-property definitions
and data-type references.  `resourcesIFCSchema.json` is rebuilt from scratch to
contain every IFC simple type and every Pset enumeration encountered in the XML
files, mapped to the correct HTML input type.

## Depends on
Steps 01–04 (specifically the IFCPage NodeDetails UI that consumes both JSON files).

## Routes
No new routes.

## Database changes
No database changes.

## Templates
No template changes (JSON files are consumed by existing React components).
UI impact: the existing NodeDetails components already read `definition` and
`description` fields if they exist; any tooltip / info-label rendering for pset and
property definitions requires a follow-up UI task (out of scope for this spec —
this spec only produces the data).

## Files to change
- `frontend/package.json` — add two new npm run scripts
- `frontend/src/pages/IFCPage/NodeDetails/ifcPropertySchema.json` — rebuilt from scratch
- `frontend/src/pages/IFCPage/NodeDetails/resourcesIFCSchema.json` — rebuilt from scratch

## Files to create
- `frontend/scripts/generate-ifc-schema-from-xsd.cjs`
- `frontend/scripts/generate-psets-from-xml.cjs`

---

## Script 1 — `generate-ifc-schema-from-xsd.cjs`

**Purpose:** Parse `IFC4X3_DEV_dcfeedc.xsd` to discover every concrete (non-abstract,
non-`*Type`) IFC element class that descends from `IfcElement`, extract its
`PredefinedType` enum values, and write `ifcPropertySchema.json` with empty
`propertySets` arrays (to be populated by Script 2).

### Algorithm

1. Read `frontend/public/ifc-schema/IFC4X3_DEV_dcfeedc.xsd` as UTF-8 text.

2. **Extract class metadata** by scanning every `<xs:element name="IfcXxx"
   substitutionGroup="ifc:IFcYyy" …>` line:
   - `className` — the `name` attribute value (e.g. `IfcWall`)
   - `parentClass` — the local name from `substitutionGroup` (strip `ifc:` prefix,
     e.g. `IfcElement`)
   - `isAbstract` — `true` if the element has `abstract="true"` on the same tag

3. **Exclude** any class where:
   - `isAbstract === true`
   - `className.endsWith("Type")` (e.g. `IfcWallType`)

4. **Build inheritance tree** using the `parentClass → className` relationships
   collected in step 2 (covering abstract parents too — they are needed as
   intermediate nodes in the tree but are not themselves emitted).

5. **Filter to IfcElement descendants** — keep only classes reachable from
   `IfcElement` (breadth-first or recursive walk).

6. **Extract PredefinedType enums** for each surviving class:
   - Find the `<xs:complexType name="IfcXxx">` block in the XSD.
   - Within that block look for `<xs:attribute name="PredefinedType" type="ifc:IfcXxxTypeEnum"`.
   - Resolve `ifc:IfcXxxTypeEnum` → find `<xs:simpleType name="IfcXxxTypeEnum">` →
     collect all `<xs:enumeration value="…"/>` values.
   - If no direct `PredefinedType` attribute is found, walk up the inheritance chain
     to the first ancestor that declares one.
   - Default to `["NOTDEFINED"]` if nothing is found.

7. **Merge with existing** `ifcPropertySchema.json`:
   - Preserve existing `propertySets` arrays so psets added manually are not lost
     when the script is re-run.
   - For `predefinedTypes`, use the freshly extracted values (XSD is authoritative).

8. Write the merged result to `ifcPropertySchema.json`, sorted alphabetically by
   `name`.

### npm command
```
"generate:ifc-schema": "node scripts/generate-ifc-schema-from-xsd.cjs"
```

---

## Script 2 — `generate-psets-from-xml.cjs`

**Purpose:** Read every `*.xml` file in `frontend/public/ifc-schema/psets/`, parse
Pset and Qto definitions, expand applicable-class lists to all concrete descendants,
attach each set to the relevant class entries in `ifcPropertySchema.json`, and
populate `resourcesIFCSchema.json` with the full data-type catalogue.

**This script must run AFTER Script 1** (it reads the `ifcPropertySchema.json` that
Script 1 produced).

### Algorithm

#### Phase A — Build class hierarchy from XSD (same as Script 1 step 4)
Re-read the XSD to reconstruct the full inheritance tree (including abstract nodes),
so that `ApplicableClasses` entries like `IfcElement` can be expanded to all concrete
descendants.

#### Phase B — Parse Pset / Qto XML files

For each `*.xml` file in `psets/`:

1. Detect document type:
   - Root element `<PropertySetDef>` → Pset
   - Root element `<QtoSetDef>` → Qto

2. Extract common fields:
   - `name` — `<Name>` text content
   - `definition` — `<Definition>` text content (trimmed)

3. Extract `ApplicableClasses` → list of `<ClassName>` text values.
   Filter out `*Type` class names (e.g. `IfcWallType`).
   Expand abstract classes to their full set of concrete descendants using the
   class hierarchy from Phase A.

4. **For Psets** — iterate `<PropertyDefs>/<PropertyDef>`:
   - `name` — `<Name>` text
   - `definition` — `<Definition>` text (trimmed)
   - Determine `dataType`:
     - `<TypePropertySingleValue><DataType type="IfcXxx"/>` → `dataType = "IfcXxx"`
     - `<TypePropertyEnumeratedValue><EnumList name="PEnum_Xxx">` →
       `dataType = "PEnum_Xxx"`; collect `<EnumItem>` values for
       `resourcesIFCSchema.json`.
     - `<TypePropertyBoundedValue><DataType type="IfcXxx"/>` → `dataType = "IfcXxx"`
     - `<TypePropertyTableValue>` → `dataType = "IfcLabel"` (fallback)
     - `<TypePropertyReferenceValue>` → skip (references only, not editable)
     - `<TypeComplexProperty>` → skip for now
   - Build property object:
     ```json
     {
       "name": "PropertyName",
       "definition": "Property description text.",
       "dataType": "IfcLabel"
     }
     ```

5. **For Qtos** — iterate `<QtoDefs>/<QtoDef>`:
   - `name` — `<Name>` text
   - `definition` — `<Definition>` text
   - `QtoType` → map to an `IfcQuantity*` data type:
     - `Q_LENGTH` → `IfcQuantityLength`
     - `Q_AREA` → `IfcQuantityArea`
     - `Q_VOLUME` → `IfcQuantityVolume`
     - `Q_WEIGHT` → `IfcQuantityWeight`
     - `Q_COUNT` → `IfcQuantityCount`
     - `Q_TIME` → `IfcQuantityTime`
     - `Q_NUMBER` → `IfcReal`
   - Build property object same shape as Psets above.

6. Build pset object:
   ```json
   {
     "name": "Pset_WallCommon",
     "definition": "Properties common to…",
     "properties": [...]
   }
   ```

#### Phase C — Attach psets to class entries

Load the `ifcPropertySchema.json` produced by Script 1.

For each pset/qto and each expanded applicable class name, find the matching class
entry and push the pset object into its `propertySets` array (de-duplicate by
`name` — if a pset with the same name is already present, replace it).

Write the updated `ifcPropertySchema.json`.

#### Phase D — Build `resourcesIFCSchema.json`

Collect every unique `dataType` string encountered across all properties (both Pset
and Qto).  For each type, determine the HTML input mapping by reading the XSD:

1. Resolve the type name to a `<xs:simpleType>` or `<xs:complexType>` in the XSD.
2. Follow `<xs:restriction base="…">` chains until a native XSD type is reached or a
   recognized base type is found.
3. Map to HTML:

| XSD base (resolved)         | `inputType` | `dataType` |
|-----------------------------|-------------|------------|
| `xs:boolean`                | `checkbox`  | `BOOLEAN`  |
| `xs:long` / `xs:integer`    | `number`    | `INTEGER`  |
| `xs:double` / `xs:float`    | `number`    | `REAL`     |
| `xs:normalizedString` / `xs:string` | `text` | `STRING` |
| `xs:date`                   | `date`      | `DATE`     |
| `xs:dateTime`               | `datetime-local` | `DATETIME` |
| Enumeration (restriction with `<xs:enumeration>`) | `select` | `ENUM` |
| IfcQuantity* (no direct XSD base) | `number` | `REAL` |
| `PEnum_*` (collected inline from XML) | `select` | `ENUM` |

4. For `select` types include an `options` array with the enumeration values.
5. Write `resourcesIFCSchema.json`:
   ```json
   {
     "classes": [
       {
         "name": "IfcLabel",
         "inputType": "text",
         "dataType": "STRING"
       },
       {
         "name": "PEnum_ElementStatus",
         "inputType": "select",
         "options": ["DEMOLISH", "EXISTING", "NEW", ...],
         "dataType": "ENUM"
       }
     ]
   }
   ```

### npm commands
```
"generate:psets": "node scripts/generate-psets-from-xml.cjs",
"generate:ifc-full": "npm run generate:ifc-schema && npm run generate:psets"
```

---

## JSON Schema Shape (output)

### `ifcPropertySchema.json`
```json
{
  "classes": [
    {
      "name": "IfcWall",
      "predefinedTypes": ["ELEMENTEDWALL", "MOVABLE", ..., "USERDEFINED", "NOTDEFINED"],
      "propertySets": [
        {
          "name": "Pset_WallCommon",
          "definition": "Properties common to the definition of all occurrences of IfcWall.",
          "properties": [
            {
              "name": "Reference",
              "definition": "Reference ID for this specified type in this project…",
              "dataType": "IfcIdentifier"
            }
          ]
        }
      ]
    }
  ]
}
```

### `resourcesIFCSchema.json`
```json
{
  "classes": [
    { "name": "IfcBoolean",    "inputType": "checkbox", "dataType": "BOOLEAN" },
    { "name": "IfcLabel",      "inputType": "text",     "dataType": "STRING"  },
    { "name": "IfcIdentifier", "inputType": "text",     "dataType": "STRING"  },
    { "name": "IfcInteger",    "inputType": "number",   "dataType": "INTEGER" },
    { "name": "IfcReal",       "inputType": "number",   "dataType": "REAL"    },
    { "name": "IfcDate",       "inputType": "date",     "dataType": "DATE"    },
    {
      "name": "PEnum_ElementStatus",
      "inputType": "select",
      "options": ["DEMOLISH", "EXISTING", "NEW", "TEMPORARY", "OTHER", "NOTKNOWN", "UNSET"],
      "dataType": "ENUM"
    }
  ]
}
```

---

## Rules for implementation
- Both scripts are CommonJS (`.cjs`) so they work without transpilation under Node
  with `"type": "commonjs"` in `package.json`.
- Use only Node.js built-ins (`fs`, `path`) — no third-party XML parser.  Parse the
  XSD with targeted regex / `indexOf` / simple state-machine scanning (same approach
  as `generate-ifc-schema-from-webifc.cjs`).  For XML (pset files), a minimal
  recursive descent or regex-based tag extractor is sufficient given the known,
  well-structured format.
- Do NOT delete `ifcPropertySchema.json` before running Script 1; Script 1 reads it
  to preserve manually-added psets.  Script 2 overwrites only the `propertySets`
  arrays (de-duplicate by name).
- The `definition` field on psets and properties should have whitespace normalised
  (collapse consecutive whitespace / newlines to a single space, trim).
- Keep both scripts idempotent — re-running them produces the same output.
- No SQLAlchemy or ORMs (backend only, not applicable here).
- Parameterised queries only (backend only, not applicable here).

## Definition of done
- [ ] `npm run generate:ifc-schema` runs without errors and writes
      `ifcPropertySchema.json` containing only concrete, non-abstract, non-`*Type`
      descendants of `IfcElement` (verify e.g. `IfcWall` is present, `IfcElement`
      and `IfcWallType` are absent).
- [ ] `npm run generate:psets` runs without errors and attaches psets to the
      appropriate class entries (verify `IfcWall` has `Pset_WallCommon`, `IfcSlab`
      has `Pset_SlabCommon` and `Qto_SlabBaseQuantities`).
- [ ] `npm run generate:ifc-full` runs both scripts in sequence successfully.
- [ ] `resourcesIFCSchema.json` contains entries for at least `IfcBoolean`,
      `IfcLabel`, `IfcIdentifier`, `IfcInteger`, `IfcReal`, `IfcDate`,
      `IfcLengthMeasure`, `IfcThermalTransmittanceMeasure`, and
      `PEnum_ElementStatus`.
- [ ] All `PEnum_*` types in `resourcesIFCSchema.json` have a non-empty `options`
      array.
- [ ] `IfcElement` (abstract) and `IfcWallType` (Type class) do **not** appear in
      `ifcPropertySchema.json`.
- [ ] Re-running either script does not corrupt or duplicate data in the output JSON
      files.
