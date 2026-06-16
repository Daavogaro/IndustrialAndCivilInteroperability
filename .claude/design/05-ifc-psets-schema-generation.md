# Design: IFC Psets Schema Generation from XSD

## Summary
This plan covers building two Node.js (`.cjs`) build-time scripts under `frontend/scripts/`
that regenerate, fully from the IFC sources shipped in the repo, the two JSON files the
IFCPage NodeDetails form consumes: `ifcPropertySchema.json` (the IFC class list, each
class's `predefinedTypes`, and its applicable `propertySets`) and `resourcesIFCSchema.json`
(the data-type catalogue that maps each `IfcXxx`/`PEnum_Xxx` to an HTML input type). Script 1
parses the XSD (`frontend/public/ifc-schema/IFC4X3_DEV_dcfeedc.xsd`) to emit only concrete
(non-`abstract`, non-`*Type`) descendants of `IfcElement` with their predefined-type enums.
Script 2 parses all ~470 Pset/Qto XML files in `frontend/public/ifc-schema/psets/`, expands
each set's applicable classes (including abstract roots like `IfcElement`) down to the concrete
classes Script 1 emitted, attaches every property/quantity (with its name, definition, and
data-type reference), and rebuilds the resources catalogue by resolving each referenced data
type through the XSD's `<xs:restriction>` chain to a native base and then to an HTML input type.

It does **NOT** cover (and the plan flags this as a conflict to resolve): the info-label /
hover-tooltip rendering that the original `/create-spec` request explicitly asked for. The
written spec scoped the UI out ("this spec only produces the data"); the user's request asked
for it. This plan therefore (a) makes the generators emit the `definition` strings the tooltips
need, so the data is ready, and (b) describes the small, low-risk `IFCNodeDetails.tsx` change
that would render them — as a **recommended** phase to be confirmed, not as committed scope.

Three findings from reading the **consuming** component (`IFCNodeDetails.tsx`) materially correct
the written spec and are the backbone of this design:
1. The component branches on `inputType === "boolean"` (renders a checkbox) and
   `inputType === "select"` (renders a dropdown); **every other** `inputType` value is passed
   straight through as an HTML `<input type=…>` attribute. So the boolean mapping **must** be
   `"boolean"` (the spec's proposed `"checkbox"` is wrong and would break boolean rendering),
   and `"text"/"number"/"date"` pass through natively.
2. The `<select>` for an enumerated property renders `property.options` — the property's **own**
   inline `options` array — **not** the resource's options. So enumerated properties **must**
   carry an inline `options` array in `ifcPropertySchema.json`, or the dropdown renders empty.
   (This is also a latent bug in the *current* file, where `Pset_WallCommon.Status` has only
   `dataType: "PEnum_ElementStatus"` and no inline options.)
3. On submit, the form sends `data_type: resolvePropertyPrimitiveDataType(property)`, which is
   `IFC_RESOURCE_BY_NAME[property.dataType]?.dataType ?? "UNKNOWN"`. So **every** `dataType`
   string emitted by Script 2 must have a matching entry in `resourcesIFCSchema.json`, or the
   UI shows `UNKNOWN` and falls back to a text input. Completeness of the resources file is a
   hard correctness requirement, not a nicety.

As with the 01–04 designs, this project has **no** `database/db.py`, **no** `app.py` routes
relevant here, and **no** server-side templates. The skill's "Database design", "Route design",
and "Template design" sections are therefore adapted to **Output-shape design**, **npm-command
design**, and **UI-integration design** respectively.

## Implementation order
1. **Lock the output contract first.** Pin down the exact JSON shapes (below) against the real
   `IFCNodeDetails.tsx` reader before writing either script — the boolean/options/completeness
   findings above mean the shape, not the parsing, is where this feature succeeds or fails.
2. **Build the shared XSD hierarchy reader (conceptually).** Both scripts need: per-class
   `name`, `substitutionGroup` parent, and `abstract` flag; the inheritance tree; an
   `isDescendantOf` walk; and a `PredefinedType`-enum resolver. Decide whether to duplicate this
   in each `.cjs` (matches the existing single-file script style and keeps each runnable alone)
   or factor a shared `ifc-xsd.cjs` helper. Recommended: duplicate the small parsing core to
   keep each script standalone, as the existing webifc script is.
3. **Script 1 — `generate-ifc-schema-from-xsd.cjs`.** Emit the class skeleton: concrete
   `IfcElement` descendants only, each with `predefinedTypes` and an **empty** `propertySets: []`.
   Verify the inclusion/exclusion rules (e.g. `IfcWall` in; `IfcElement`, `IfcWallType` out)
   before moving on, because Script 2 attaches onto exactly this list.
4. **Script 2 Phase A/B — parse psets/qtos.** Read every XML file, classify Pset vs Qto, extract
   name/definition/applicable-classes and each property/quantity with its resolved `dataType`,
   normalising definition whitespace and decoding XML entities. Collect the full set of distinct
   data types and PEnum definitions as a side effect.
5. **Script 2 Phase C — attach.** Load Script 1's output, clear every class's `propertySets` to
   `[]` (idempotency), expand each set's applicable classes to concrete descendants, and push a
   per-class copy of the set onto each match (dedupe by set name). Write `ifcPropertySchema.json`.
6. **Script 2 Phase D — resources.** Resolve every collected data type through the XSD restriction
   chain to a native base → HTML input mapping; merge in the inline `PEnum_*` definitions; write
   `resourcesIFCSchema.json`. Run last because it depends on the full data-type set gathered in B.
7. **Wire npm scripts and regenerate.** Repoint/extend `package.json`, run `generate:ifc-full`,
   and validate the DoD checks (including loading the IFCPage form against the new JSON).
8. **(Recommended, to confirm) Tooltip UI.** Only after the data is correct, make the small
   `IFCNodeDetails.tsx` change to show info icons with `title` tooltips for pset and property
   definitions. Kept last and separable so the data work can ship independently.

## Output-shape design (replaces "Database design")

### `ifcPropertySchema.json` — exact shape Script 2 must produce
Top level: `{ "classes": [ … ] }`. Each class object:
- `name` — string, e.g. `"IfcWall"`. Only concrete, non-`*Type`, `IfcElement` descendants.
- `predefinedTypes` — non-empty string array; from the XSD `PredefinedType` enum, else
  `["NOTDEFINED"]`. Authoritative from the XSD (overwrites any prior value).
- `propertySets` — array of set objects (empty if no applicable set). Each set object:
  - `name` — e.g. `"Pset_WallCommon"` or `"Qto_SlabBaseQuantities"`.
  - `definition` — whitespace-normalised, entity-decoded `<Definition>` text. **New field**
    (additive; the component ignores unknown keys, so it is safe). Needed by the tooltip phase.
  - `properties` — array of property objects:
    - `name` — e.g. `"Reference"`.
    - `definition` — normalised property `<Definition>`. **New field** (additive/safe).
    - `dataType` — the resource key, e.g. `"IfcIdentifier"`, `"IfcThermalTransmittanceMeasure"`,
      `"PEnum_ElementStatus"`, `"IfcQuantityLength"`. **Must** exist in `resourcesIFCSchema.json`.
    - `options` — **present only for enumerated properties** (string array of `EnumItem`s).
      Required for the component's `<select>` to render (finding #2). For non-enumerated
      properties this key is omitted.

Constraints that fall out of the component:
- Adding `definition` to sets and properties is safe — `IFCNodeDetails.tsx` reads `name`,
  `dataType`, and `options` only; extra keys are inert at runtime and the JSON is `as`-cast.
- For enumerated properties, emit **both** the inline `options` (so the dropdown has entries)
  **and** a `PEnum_*` `dataType` registered in resources (so `resolvePropertyInputType`'s resource
  fallback also yields `"select"` and the submit payload's `data_type` resolves to `"ENUM"`).

### `resourcesIFCSchema.json` — exact shape Script 2 must produce
Top level: `{ "classes": [ … ] }`. Two kinds of entry:
- **Scalar/measure type:** `{ "name": "IfcLabel", "inputType": "text", "dataType": "STRING" }`.
- **Enumeration type (`PEnum_*` or any enum):**
  `{ "name": "PEnum_ElementStatus", "inputType": "select", "options": ["DEMOLISH", …], "dataType": "ENUM" }`.

The set of `name`s must be the **union** of every distinct `dataType` string emitted across all
properties in `ifcPropertySchema.json` (completeness requirement, finding #3).

### Authoritative HTML-mapping table (corrects the spec)
Resolve the type name through `<xs:restriction base=…>` (following `ifc:`-prefixed bases
recursively) until a native `xs:` base or an enumeration is reached, then map:

| Resolved XSD base / shape                              | `inputType`        | `dataType` |
|--------------------------------------------------------|--------------------|------------|
| `xs:boolean`                                           | `boolean`          | `BOOLEAN`  |
| `xs:long`, `xs:integer`, `xs:int`                      | `number`           | `INTEGER`  |
| `xs:double`, `xs:float`, `xs:decimal`                  | `number`           | `REAL`     |
| `xs:normalizedString`, `xs:string`, `xs:anyURI`        | `text`             | `STRING`   |
| `xs:date`                                              | `date`             | `DATE`     |
| `xs:dateTime`                                          | `datetime-local`   | `DATETIME` |
| simpleType with `<xs:enumeration>` children            | `select` (+options)| `ENUM`     |
| `PEnum_*` (items collected inline from the pset XML)   | `select` (+options)| `ENUM`     |
| `IfcQuantityCount`                                     | `number`           | `INTEGER`  |
| `IfcQuantityLength/Area/Volume/Weight/Time` (+ other `IfcQuantity*`) | `number` | `REAL`     |

Notes:
- **`boolean`, not `checkbox`** — the spec's `checkbox` is wrong; the component keys off
  `"boolean"`.
- `date` is already proven in the current file (passes through as `<input type="date">`).
  `datetime-local` is a valid HTML5 input type and passes through the same else-branch, but is
  **unproven** in this codebase — see Open Question 4 (fallback: map `IfcDateTime` → `text`/`STRING`).
- `IfcQuantity*` types are **entities**, not measure `simpleType`s, so they have no restriction
  chain to follow — they must be mapped by an explicit fallback table, not by XSD resolution.
- Any type that resolves to none of the above → fallback `text`/`STRING`, and **log** it with a
  count so unmapped types are visible (DoD).

### "Migration"
None in the DB sense. These are build-time source files committed to the repo. Regeneration is a
full overwrite. Both prior JSON files are explicitly authorised to be erased and rebuilt; the
only data lost is the current hand-curated content (e.g. the `typeDrivenOverride` field and the
manually added `Pset_InstallationOccurrence` on `IfcElectricAppliance`) — see Open Question 2.

## npm-command design (replaces "Route design")
No HTTP routes. Three `package.json` scripts under `"scripts"`:
- `generate:ifc-schema` — **repointed** from the webifc script to
  `node scripts/generate-ifc-schema-from-xsd.cjs` (Script 1).
- `generate:psets` — **new**: `node scripts/generate-psets-from-xml.cjs` (Script 2).
- `generate:ifc-full` — **new**: runs both in order
  (`npm run generate:ifc-schema && npm run generate:psets`).

Ordering is enforced by `generate:ifc-full` because Script 2 reads the file Script 1 writes. The
existing webifc script file is left on disk (orphaned) unless the user wants it removed — Open
Question 1. `web-ifc` stays a runtime dependency regardless (the viewer uses it); only the
generation step stops depending on it.

## UI-integration design (replaces "Template design")
No new templates. One **recommended, to-be-confirmed** modification, planned here because the
user's original request asked for it even though the written spec scoped it out.

### Modified (recommended): `frontend/src/pages/IFCPage/NodeDetails/IFCNodeDetails.tsx`
- **What exists now:** the pset header renders `<strong>{pset.name}</strong>` (≈ line 550); each
  property renders `<label …>{property.name}</label>` (≈ line 579). The `PSetSpec` and
  `PropertySpec` TS types (lines 11–30) do **not** include `definition`.
- **What changes:**
  1. Add an optional `definition?: string` to `PSetSpec` and `PropertySpec` (purely a type
     widening; the JSON already carries it after regeneration).
  2. Next to the pset name and each property label, render a small info indicator (e.g. a
     `material-icons-round` "info" glyph, matching the existing icon usage at lines 483/506)
     wrapped/attributed with the definition text as a native `title` so it appears on hover. A
     native `title` tooltip is the lowest-risk option (no new dependency, no positioning logic).
  3. Guard on presence: render the indicator only when `definition` is a non-empty string.
- **What is deliberately NOT changed:** form state, submit payload, pset/property iteration, and
  the input-rendering branches all stay as-is. The change is presentational and additive.
- **Why separable:** the data (definitions) is produced by the generators regardless; this UI
  step can land in the same PR or a follow-up without affecting the generated files.

## Logic design (script algorithms — prose only, no code)

### Shared XSD parsing core (used by both scripts)
- **Responsibility:** turn the XSD text into (a) a map of class → `{ parent, isAbstract }`, (b) an
  `isDescendantOf(class, ancestor)` predicate, and (c) a `PredefinedType`-enum resolver.
- **Inputs:** the XSD file contents (UTF-8 string).
- **Outputs:** the maps/predicate above; for the enum resolver, a class → string[] of enum values.
- **Decision tree / method:**
  - Scan every `<xs:element name="IfcXxx" … substitutionGroup="ifc:IfcYyy" …>` declaration. The
    `name` attribute is the class; the local part of `substitutionGroup` (strip `ifc:`) is the
    parent; `abstract="true"` on that element marks it abstract. (The sibling
    `<xs:complexType name="IfcXxx" abstract="true">` carries the same flag — either source works;
    use the element declarations as the spine since they always carry `substitutionGroup`.)
  - `isDescendantOf` walks `parent` links upward with a visited-set guard (mirrors the webifc
    script's existing implementation).
  - **PredefinedType enum:** in the `<xs:complexType name="IfcXxx">` block find
    `<xs:attribute name="PredefinedType" type="ifc:IfcXxxTypeEnum" …>`; resolve
    `IfcXxxTypeEnum` to its `<xs:simpleType name="IfcXxxTypeEnum">` and collect all
    `<xs:enumeration value="…"/>`. If the class has no direct `PredefinedType`, walk up the
    inheritance chain to the nearest ancestor that declares one. Default `["NOTDEFINED"]`.
- **Side effects:** none (pure parsing).

### Script 1 — `generate-ifc-schema-from-xsd.cjs`
- **Responsibility:** write the class skeleton of `ifcPropertySchema.json`.
- **Inputs:** the XSD file.
- **Output:** `ifcPropertySchema.json` with `classes` sorted by `name`; each class
  `{ name, predefinedTypes, propertySets: [] }`.
- **Decision tree:**
  - Include a class iff: **not** abstract, **and** name does **not** end with `Type`, **and** it
    `isDescendantOf("IfcElement")`. (Mirrors the webifc script's intent but sourced from the XSD;
    the webifc script's extra `IfcRoot` check is unnecessary here since the IfcElement subtree is
    already rooted under IfcProduct→IfcRoot.)
  - For each included class, attach `predefinedTypes` from the enum resolver.
  - **Recommended divergence from the written spec (R1):** do **not** merge-preserve existing
    `propertySets`. Write `propertySets: []` for every class. Rationale: the user authorised
    "erase and start from scratch", Script 2 rebuilds all psets from the XML corpus, and a fresh
    skeleton makes `generate:ifc-full` fully deterministic/idempotent. (Merging would resurrect
    stale hand-edits and make output depend on prior state.)
- **Side effects:** one file write.

### Script 2 — `generate-psets-from-xml.cjs`
Runs after Script 1.

- **Phase A — hierarchy:** rebuild the XSD class map (via the shared core) including abstract
  nodes, so applicable-class expansion can resolve abstract roots to concrete descendants. Also
  load the **set of concrete class names** from Script 1's `ifcPropertySchema.json` (the
  attachment targets).
- **Phase B — parse each `psets/*.xml`:**
  - **Inputs:** each XML file's text.
  - **Classify:** root `<PropertySetDef>` ⇒ Pset; root `<QtoSetDef>` ⇒ Qto.
  - **Common fields:** `name` = `<Name>`; `definition` = normalised `<Definition>` (decode XML
    entities `&quot; &amp; &lt; &gt; &apos;` + numeric refs, collapse internal whitespace/newlines
    to single spaces, trim).
  - **Applicable classes:** collect `<ApplicableClasses>/<ClassName>`; **drop** any ending in
    `Type`; for each remaining name, if it is one of our concrete classes keep it directly, and if
    it is an (abstract or concrete) class with descendants, expand to **all** concrete descendants
    present in our class set. Union the results, de-duplicated.
  - **Pset properties** (`<PropertyDefs>/<PropertyDef>`): `name`, normalised `definition`, and
    `dataType` by property-type variant:
    - `TypePropertySingleValue` / `TypePropertyBoundedValue` → `DataType@type` (e.g. `IfcLabel`).
    - `TypePropertyListValue` → the inner `ListValue/DataType@type` (treated as its scalar type).
    - `TypePropertyEnumeratedValue` → `dataType` = the `EnumList@name` (`PEnum_*`); also emit the
      inline `options` from `<EnumItem>`; register the PEnum (name+items) for resources.
    - `TypePropertyTableValue` → fallback to the `DefinedValue/DataType@type` (the dependent
      quantity) so the user edits a single value; record the type for resources. (Tables are not
      fully editable in this UI; this is a pragmatic single-value fallback — Open Question 5.)
    - `TypePropertyReferenceValue` / `TypeComplexProperty` (if any appear) → **skip** with a logged
      count; they are object references / nested structures the flat form can't represent.
  - **Qto quantities** (`<QtoDefs>/<QtoDef>`): `name`, normalised `definition`, and `dataType`
    mapped from `<QtoType>`: `Q_LENGTH→IfcQuantityLength`, `Q_AREA→IfcQuantityArea`,
    `Q_VOLUME→IfcQuantityVolume`, `Q_WEIGHT→IfcQuantityWeight`, `Q_COUNT→IfcQuantityCount`,
    `Q_TIME→IfcQuantityTime`, `Q_NUMBER→IfcReal` (any unknown `Q_*` → `IfcReal` + log).
  - **Outputs per file:** a set object `{ name, definition, properties:[…] }` plus its expanded
    applicable-class list; accumulate every distinct `dataType` and every `PEnum_*` definition.
  - **Side effects:** none yet (in-memory accumulation).
- **Phase C — attach & write schema:**
  - Load Script 1's `ifcPropertySchema.json`; set every class's `propertySets = []` (idempotency).
  - For each parsed set, for each expanded applicable class, push a copy of the set object onto
    that class's `propertySets`, **deduped by set `name`** (replace if already present).
  - Write `ifcPropertySchema.json` (preserve the sorted class order from Script 1; optionally sort
    each class's `propertySets` by name for stable diffs).
  - **Side effects:** one file write.
- **Phase D — build & write resources:**
  - For each distinct scalar/measure `dataType`: resolve through the XSD restriction chain to a
    native base (recursively following `ifc:`-prefixed bases), then map via the table above; for
    `IfcQuantity*` use the explicit fallback (no restriction chain exists).
  - For each `PEnum_*`: emit `select`/`ENUM` with its inline `options`. **Dedupe by name**; if two
    files define the same PEnum with **different** item lists, log a warning and keep the first
    (Open Question 6).
  - Unresolved types → `text`/`STRING` + logged count.
  - Write `resourcesIFCSchema.json` (sorted by name for stable diffs).
  - **Side effects:** one file write; console summary (counts of classes, sets attached, distinct
    data types, PEnums, skipped properties, unresolved types).

### Parsing approach (both scripts)
Use only Node built-ins (`fs`, `path`) — **no third-party XML/XSD parser**, matching the webifc
script and the spec. The XSD is parsed with targeted regex / `indexOf` block-scanning (as the
existing script already does for the `.d.ts`). The pset XML files are small, flat, and
machine-generated with a fixed structure, so a regex/tag-walk extractor per known element
(`<Name>`, `<Definition>`, `<ApplicableClasses>`, `<PropertyDef>`, `<DataType type=…>`,
`<EnumList name=…>`, `<EnumItem>`, `<QtoDef>`, `<QtoType>`) is sufficient and avoids a dependency.
Definition text must have entities decoded and whitespace normalised (Phase B).

## Dependency and integration notes
- **No new runtime or dev dependencies.** Both scripts use only Node built-ins. `web-ifc` remains
  in `dependencies` for the viewer; it is simply no longer used by the (repointed) generation
  script.
- **Inputs are committed sources:** the XSD at `frontend/public/ifc-schema/IFC4X3_DEV_dcfeedc.xsd`
  and `frontend/public/ifc-schema/psets/*.xml`. (Note: the spec's prose references
  `frontend/public/ifc/IFC4X3_DEV_dcfeedc.xsd` for data types in one place and
  `frontend/public/ifc-schema/…` elsewhere — the actual file confirmed present is under
  `ifc-schema/`. Both scripts should read the `ifc-schema/` path. Open Question 7.)
- **Integration point:** `IFCNodeDetails.tsx` imports both JSON files directly
  (`import … from "./ifcPropertySchema.json"` / `"./resourcesIFCSchema.json"`), so regenerated
  files are picked up by Vite on next build/dev with no other wiring.

## Security checklist
- **Authentication / Authorisation:** not applicable — these are offline, developer-run build
  scripts producing static repo files; no request handling, no user data, no auth surface.
- **Input validation / sanitisation:** inputs are trusted, version-controlled schema files from
  buildingSMART, not user uploads. The scripts should still fail loudly (non-zero exit, clear
  message) on a missing/malformed input file rather than emitting a half-written JSON, and must
  decode XML entities so definition text can't inject stray markup into the JSON strings.
- **Injection (SQL/SPARQL):** not applicable — no queries are constructed; output is JSON written
  with `JSON.stringify`, which safely escapes all string content.
- **CSRF:** not applicable — no HTTP.
- **Sensitive data handling:** none — schema metadata only.
- **Output-trust note for the UI:** because definitions become tooltip text, the (recommended)
  UI phase should render them via a native `title`/`textContent` (not `dangerouslySetInnerHTML`),
  so even if a definition contained markup it is shown as inert text.

## Open questions
1. **Delete the old webifc script?** `generate-ifc-schema-from-webifc.cjs` becomes orphaned once
   `generate:ifc-schema` is repointed.
   - *Assumption:* leave it on disk (harmless), repoint the npm script.
   - *Impact if wrong:* trivial — a dead file. Easy to delete if the user prefers a clean tree.
2. **Loss of hand-curated psets.** Rebuilding from scratch drops the manual
   `typeDrivenOverride` field and the manually added sets (e.g. `Pset_InstallationOccurrence` on
   `IfcElectricAppliance`, `Pset_ElementAssemblyTypeHeadSpan`) not derivable from the XML corpus.
   - *Assumption:* acceptable — the user said "feel free to erase … and start from scratch", and
     `typeDrivenOverride` has no XML source.
   - *Impact if wrong:* features relying on `typeDrivenOverride` (if any downstream code reads it)
     lose that data. A grep found the field only in the JSON, not in `IFCNodeDetails.tsx`, so the
     risk appears low — but confirm no other consumer exists.
3. **Taxonomy root = `IfcElement` only.** Psets applicable solely to spatial/other roots
   (`Pset_SpaceCommon`, `Pset_BuildingCommon`, `Pset_SiteCommon`, zone/system psets) have **no**
   concrete `IfcElement`-descendant targets and will attach to nothing.
   - *Assumption:* in scope as-is — the GLTF-derived hierarchy is physical elements
     (`IfcElement` descendants), matching the webifc script's `IfcElement` filter.
   - *Impact if wrong:* if the user later wants spatial classes selectable, broaden the root set
     (e.g. also include `IfcSpatialElement` descendants) in both scripts — a contained change.
4. **`IfcDateTime` mapping.** `datetime-local` is valid HTML5 and passes through the component's
   else-branch, but is unproven in this codebase (only `date` is currently used).
   - *Assumption:* map `IfcDateTime` → `datetime-local`/`DATETIME`.
   - *Impact if wrong:* a datetime field could render oddly in some browser; safe fallback is to
     map it to `text`/`STRING`. Low impact, easily flipped.
5. **`TypePropertyTableValue` representation.** A table (defining→defined value curve) can't be
   edited as one field in the flat form.
   - *Assumption:* expose it as a single editable value using the `DefinedValue` data type.
   - *Impact if wrong:* the property is editable but semantically lossy (no curve). Alternative:
     skip table properties entirely. ~121 occurrences, so the choice is visible; recommend the
     single-value fallback so nothing silently disappears, with the skipped/approximated count
     logged.
6. **Divergent `PEnum_*` definitions across files.** If the same PEnum name carries different
   `EnumItem` lists in different psets.
   - *Assumption:* dedupe by name, keep first, log a warning on divergence.
   - *Impact if wrong:* a property could show a slightly wrong option list. Warnings make any real
     divergence visible for manual resolution.
7. **XSD path discrepancy in the spec.** The spec text names two different paths for the data-type
   XSD (`public/ifc/…` vs `public/ifc-schema/…`); only `public/ifc-schema/IFC4X3_DEV_dcfeedc.xsd`
   is confirmed to exist.
   - *Assumption:* both scripts read `public/ifc-schema/IFC4X3_DEV_dcfeedc.xsd`.
   - *Impact if wrong:* if a second XSD exists under `public/ifc/` with different content, type
     resolution could differ; confirm there is a single source of truth.
8. **Tooltip scope conflict (spec vs. original request).** The written spec scoped the info-label
   tooltips out; the user's `/create-spec` request explicitly asked for them on both pset and
   property names.
   - *Assumption:* generate the `definition` data now (so it's ready) and treat the
     `IFCNodeDetails.tsx` tooltip rendering as a recommended phase to confirm.
   - *Impact if wrong:* if the user wants tooltips in this deliverable, include the UI phase; if
     not, the extra `definition` keys are harmless and ignored.

## Definition of done (design review)
- [ ] The JSON output shapes above are confirmed against `IFCNodeDetails.tsx`, specifically:
      booleans use `inputType: "boolean"` (not `checkbox`); enumerated properties carry an inline
      `options` array; and every property `dataType` has a matching `resourcesIFCSchema.json` entry.
- [ ] It is agreed Script 1 writes a **fresh** skeleton with empty `propertySets` (no
      merge-preserve), making `generate:ifc-full` deterministic (refinement R1) — and the loss of
      hand-curated psets / `typeDrivenOverride` is accepted (Open Question 2).
- [ ] The inclusion/exclusion rule is agreed: emit concrete, non-`*Type` descendants of
      `IfcElement` only; abstract classes and `*Type` classes are excluded but abstract classes
      still serve as expansion roots for applicable-class resolution.
- [ ] The data-type → HTML mapping table (including the `IfcQuantity*` explicit fallback and the
      `IfcDateTime` decision, Open Question 4) is agreed.
- [ ] The handling of each property-type variant is agreed: SingleValue/BoundedValue/ListValue →
      scalar type; EnumeratedValue → `PEnum_*` + inline options; TableValue → single-value
      fallback (Open Question 5); ReferenceValue/ComplexProperty → skipped with logged count.
- [ ] The two-script split and the three npm commands (`generate:ifc-schema` repointed,
      `generate:psets` new, `generate:ifc-full` new) are agreed, including the run-order dependency
      and the decision on the orphaned webifc script (Open Question 1).
- [ ] Decisions are recorded on: taxonomy root = `IfcElement` only (Open Question 3), the single
      XSD source path (Open Question 7), and whether the tooltip UI phase is in scope for this
      deliverable (Open Question 8).
- [ ] Definition-text handling is agreed: XML entities decoded, whitespace normalised, rendered as
      inert `title` text in the (recommended) UI phase.
