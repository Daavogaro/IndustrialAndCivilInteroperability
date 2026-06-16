const fs = require("fs");
const path = require("path");

// ---------------------------------------------------------------------------
// Script 2 — Parse every Pset/Qto XML in public/ifc-schema/psets/ and:
//   (1) attach property sets to the concrete classes emitted by Script 1,
//       writing ifcPropertySchema.json;
//   (2) build the data-type -> HTML-input catalogue resourcesIFCSchema.json
//       by resolving each referenced IFC type through the XSD restriction chain.
//
// MUST run after generate-ifc-schema-from-xsd.cjs (it reads that file's output).
// Node built-ins only; no XML/XSD parser dependency.
// ---------------------------------------------------------------------------

const projectRoot = path.resolve(__dirname, "..");
const xsdPath = path.join(
  projectRoot,
  "public",
  "ifc-schema",
  "IFC4X3_DEV_dcfeedc.xsd",
);
const psetsDir = path.join(projectRoot, "public", "ifc-schema", "psets");
const nodeDetailsDir = path.join(
  projectRoot,
  "src",
  "pages",
  "IFCPage",
  "NodeDetails",
);
const schemaJsonPath = path.join(nodeDetailsDir, "ifcPropertySchema.json");
const resourcesJsonPath = path.join(nodeDetailsDir, "resourcesIFCSchema.json");

// ---------------------------------------------------------------------------
// XML / text helpers
// ---------------------------------------------------------------------------

function decodeEntities(text) {
  return text
    .replace(/&quot;/g, '"')
    .replace(/&apos;/g, "'")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&#x([0-9a-fA-F]+);/g, (_, h) => String.fromCodePoint(parseInt(h, 16)))
    .replace(/&#(\d+);/g, (_, d) => String.fromCodePoint(parseInt(d, 10)))
    // &amp; must be decoded last so it doesn't double-decode.
    .replace(/&amp;/g, "&");
}

function normalizeDefinition(raw) {
  if (raw == null) {
    return "";
  }
  return decodeEntities(raw).replace(/\s+/g, " ").trim();
}

function firstTagText(xml, tag) {
  const m = xml.match(new RegExp(`<${tag}>([\\s\\S]*?)<\\/${tag}>`));
  return m ? m[1] : null;
}

// ---------------------------------------------------------------------------
// XSD parsing — class hierarchy + simpleType restriction chains
// ---------------------------------------------------------------------------

function parseClassHierarchy(xsd) {
  const hierarchy = new Map(); // name -> { parent }
  const elementRegex = /<xs:element\s+([^>]*?)\/?>/g;
  let match;
  while ((match = elementRegex.exec(xsd)) !== null) {
    const attrs = match[1];
    const nameMatch = attrs.match(/\bname="(Ifc[A-Za-z0-9_]+)"/);
    if (!nameMatch) {
      continue;
    }
    const name = nameMatch[1];
    const parentMatch = attrs.match(/\bsubstitutionGroup="ifc:(Ifc[A-Za-z0-9_]+)"/);
    if (!hierarchy.has(name)) {
      hierarchy.set(name, { parent: parentMatch ? parentMatch[1] : null });
    }
  }
  return hierarchy;
}

function makeIsDescendantOf(hierarchy) {
  return function isDescendantOf(className, ancestorName) {
    let current = className;
    const visited = new Set();
    while (current && !visited.has(current)) {
      if (current === ancestorName) {
        return true;
      }
      visited.add(current);
      const entry = hierarchy.get(current);
      current = entry ? entry.parent : null;
    }
    return false;
  };
}

// Parse every simpleType: name -> { base, options } where base is the
// restriction base (e.g. "xs:double" or "ifc:IfcLengthMeasure") and options is
// the array of enumeration values if any (UPPERCASED).
function parseSimpleTypes(xsd) {
  const simpleTypes = new Map();
  const regex = /<xs:simpleType name="([A-Za-z0-9_]+)">([\s\S]*?)<\/xs:simpleType>/g;
  let match;
  while ((match = regex.exec(xsd)) !== null) {
    const name = match[1];
    const body = match[2];
    const baseMatch = body.match(/<xs:restriction base="([^"]+)"/);
    const base = baseMatch ? baseMatch[1] : null;
    const options = [];
    const enumRegex = /<xs:enumeration value="([^"]*)"\s*\/>/g;
    let em;
    while ((em = enumRegex.exec(body)) !== null) {
      options.push(em[1].toUpperCase());
    }
    simpleTypes.set(name, { base, options });
  }
  return simpleTypes;
}

// ---------------------------------------------------------------------------
// Data-type resolution: IFC type name -> { inputType, dataType, options? }
// ---------------------------------------------------------------------------

// Explicit semantic overrides checked before chain resolution. The XSD bases of
// these are normalizedString, which would otherwise misclassify them as text.
const SEMANTIC_OVERRIDES = {
  IfcBoolean: { inputType: "boolean", dataType: "BOOLEAN" },
  IfcLogical: { inputType: "boolean", dataType: "BOOLEAN" }, // 3-valued, edited as boolean
  IfcDate: { inputType: "date", dataType: "DATE" },
  IfcDateTime: { inputType: "datetime-local", dataType: "DATETIME" },
  IfcTime: { inputType: "text", dataType: "STRING" },
  IfcDuration: { inputType: "text", dataType: "STRING" }, // ISO 8601 duration string
};

// IfcQuantity* are entities (no simpleType restriction chain), mapped explicitly.
function resolveQuantityType(name) {
  if (name === "IfcQuantityCount") {
    return { inputType: "number", dataType: "INTEGER" };
  }
  if (name.startsWith("IfcQuantity")) {
    return { inputType: "number", dataType: "REAL" };
  }
  return null;
}

function mapNativeBase(base) {
  switch (base) {
    case "xs:boolean":
      return { inputType: "boolean", dataType: "BOOLEAN" };
    case "xs:long":
    case "xs:integer":
    case "xs:int":
    case "xs:nonNegativeInteger":
    case "xs:positiveInteger":
      return { inputType: "number", dataType: "INTEGER" };
    case "xs:double":
    case "xs:float":
    case "xs:decimal":
      return { inputType: "number", dataType: "REAL" };
    case "xs:normalizedString":
    case "xs:string":
    case "xs:token":
    case "xs:anyURI":
      return { inputType: "text", dataType: "STRING" };
    case "xs:date":
      return { inputType: "date", dataType: "DATE" };
    case "xs:dateTime":
      return { inputType: "datetime-local", dataType: "DATETIME" };
    default:
      return null;
  }
}

function makeResolveDataType(simpleTypes, unresolved) {
  return function resolveDataType(typeName) {
    if (SEMANTIC_OVERRIDES[typeName]) {
      return { ...SEMANTIC_OVERRIDES[typeName] };
    }
    const quantity = resolveQuantityType(typeName);
    if (quantity) {
      return quantity;
    }

    let current = typeName;
    const visited = new Set();
    while (current && !visited.has(current)) {
      visited.add(current);

      // Native XSD base reached directly.
      if (current.startsWith("xs:")) {
        const mapped = mapNativeBase(current);
        if (mapped) {
          return mapped;
        }
        break;
      }

      const entry = simpleTypes.get(current);
      if (!entry) {
        break;
      }
      // Enumeration simpleType -> select with inline options.
      if (entry.options.length > 0 && (!entry.base || entry.base.startsWith("xs:"))) {
        return { inputType: "select", dataType: "ENUM", options: entry.options };
      }
      if (!entry.base) {
        break;
      }
      // Follow ifc:-prefixed base, or map a native base.
      if (entry.base.startsWith("xs:")) {
        const mapped = mapNativeBase(entry.base);
        if (mapped) {
          return mapped;
        }
        break;
      }
      current = entry.base.replace(/^ifc:/, "");
    }

    unresolved.set(typeName, (unresolved.get(typeName) || 0) + 1);
    return { inputType: "text", dataType: "STRING" };
  };
}

// ---------------------------------------------------------------------------
// QtoType -> IFC quantity entity name
// ---------------------------------------------------------------------------

const QTO_TYPE_MAP = {
  Q_LENGTH: "IfcQuantityLength",
  Q_AREA: "IfcQuantityArea",
  Q_VOLUME: "IfcQuantityVolume",
  Q_WEIGHT: "IfcQuantityWeight",
  Q_COUNT: "IfcQuantityCount",
  Q_TIME: "IfcQuantityTime",
  Q_NUMBER: "IfcReal",
};

// ---------------------------------------------------------------------------
// Per-file XML parsing
// ---------------------------------------------------------------------------

const stats = {
  files: 0,
  psets: 0,
  qtos: 0,
  skippedReference: 0,
  skippedComplex: 0,
  unknownQto: 0,
};

function extractDataTypeAttr(block) {
  const m = block.match(/<DataType type="([^"]+)"\s*\/>/);
  return m ? m[1] : null;
}

// Parse a single <PropertyDef> block -> { name, definition, dataType, options? } | null
function parsePropertyDef(block, penums) {
  const name = normalizeDefinition(firstTagText(block, "Name"));
  const definition = normalizeDefinition(firstTagText(block, "Definition"));
  if (!name) {
    return null;
  }

  if (block.includes("<TypePropertyReferenceValue")) {
    stats.skippedReference += 1;
    return null; // object reference — not representable in the flat form
  }
  if (block.includes("<TypeComplexProperty")) {
    stats.skippedComplex += 1;
    return null; // nested structure — not representable
  }

  if (block.includes("<TypePropertyEnumeratedValue")) {
    const enumListMatch = block.match(/<EnumList\s+name="([^"]+)"/);
    const enumName = enumListMatch ? enumListMatch[1] : `PEnum_${name}`;
    const options = [];
    const itemRegex = /<EnumItem>([\s\S]*?)<\/EnumItem>/g;
    let im;
    while ((im = itemRegex.exec(block)) !== null) {
      options.push(decodeEntities(im[1]).trim().toUpperCase());
    }
    // Register the PEnum for the resources catalogue (dedupe handled by caller).
    if (!penums.has(enumName)) {
      penums.set(enumName, options);
    } else if (JSON.stringify(penums.get(enumName)) !== JSON.stringify(options) && options.length > 0) {
      console.warn(
        `[generate-psets] PEnum "${enumName}" has divergent items across files; keeping first.`,
      );
    }
    return { name, definition, dataType: enumName, options };
  }

  if (block.includes("<TypePropertyTableValue")) {
    // Use the DefinedValue (dependent) data type as a single editable value.
    const definedMatch = block.match(/<DefinedValue>([\s\S]*?)<\/DefinedValue>/);
    const dataType = definedMatch ? extractDataTypeAttr(definedMatch[1]) : null;
    if (!dataType) {
      return null;
    }
    return { name, definition, dataType };
  }

  // SingleValue / BoundedValue / ListValue all expose a scalar <DataType type=.../>.
  const dataType = extractDataTypeAttr(block);
  if (!dataType) {
    return null;
  }
  return { name, definition, dataType };
}

function parseQtoDef(block) {
  const name = normalizeDefinition(firstTagText(block, "Name"));
  const definition = normalizeDefinition(firstTagText(block, "Definition"));
  const qtoTypeMatch = block.match(/<QtoType>([\s\S]*?)<\/QtoType>/);
  const qtoType = qtoTypeMatch ? qtoTypeMatch[1].trim() : null;
  if (!name || !qtoType) {
    return null;
  }
  let dataType = QTO_TYPE_MAP[qtoType];
  if (!dataType) {
    dataType = "IfcReal";
    stats.unknownQto += 1;
    console.warn(`[generate-psets] Unknown QtoType "${qtoType}" -> IfcReal.`);
  }
  return { name, definition, dataType };
}

// Parse one pset/qto file -> { name, definition, applicableClasses, properties } | null
function parsePsetFile(xml, penums) {
  const isPset = xml.includes("<PropertySetDef");
  const isQto = xml.includes("<QtoSetDef");
  if (!isPset && !isQto) {
    return null;
  }

  // Header is everything before the property/quantity list.
  const defsIndex = isPset ? xml.indexOf("<PropertyDefs") : xml.indexOf("<QtoDefs");
  const header = defsIndex >= 0 ? xml.slice(0, defsIndex) : xml;

  const name = normalizeDefinition(firstTagText(header, "Name"));
  const definition = normalizeDefinition(firstTagText(header, "Definition"));
  if (!name) {
    return null;
  }

  // Each <ClassName> is either "IfcFoo" or "IfcFoo/PREDEFINEDTYPE" (the latter
  // restricts the set to occurrences of that predefined type). We drop the
  // Ifc*Type variants and keep { base, predefinedType } for the rest.
  const applicableClasses = [];
  const acBlockMatch = header.match(/<ApplicableClasses>([\s\S]*?)<\/ApplicableClasses>/);
  if (acBlockMatch) {
    const cnRegex = /<ClassName>([\s\S]*?)<\/ClassName>/g;
    let cm;
    while ((cm = cnRegex.exec(acBlockMatch[1])) !== null) {
      const cn = cm[1].trim();
      if (!cn) {
        continue;
      }
      const slashIdx = cn.indexOf("/");
      const base = slashIdx >= 0 ? cn.slice(0, slashIdx).trim() : cn;
      const predefinedType =
        slashIdx >= 0 ? cn.slice(slashIdx + 1).trim().toUpperCase() : null;
      if (base.endsWith("Type")) {
        continue; // drop Ifc*Type variants
      }
      applicableClasses.push({ base, predefinedType });
    }
  }

  const properties = [];
  if (isPset) {
    const defRegex = /<PropertyDef>([\s\S]*?)<\/PropertyDef>/g;
    let dm;
    while ((dm = defRegex.exec(xml)) !== null) {
      const prop = parsePropertyDef(dm[1], penums);
      if (prop) {
        properties.push(prop);
      }
    }
  } else {
    const defRegex = /<QtoDef>([\s\S]*?)<\/QtoDef>/g;
    let dm;
    while ((dm = defRegex.exec(xml)) !== null) {
      const prop = parseQtoDef(dm[1]);
      if (prop) {
        properties.push(prop);
      }
    }
  }

  return { name, definition, applicableClasses, properties, kind: isPset ? "pset" : "qto" };
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

function main() {
  for (const p of [xsdPath, psetsDir, schemaJsonPath]) {
    if (!fs.existsSync(p)) {
      console.error(`Missing required input: ${p}`);
      process.exit(1);
    }
  }

  const xsd = fs.readFileSync(xsdPath, "utf8");
  const hierarchy = parseClassHierarchy(xsd);
  const isDescendantOf = makeIsDescendantOf(hierarchy);
  const simpleTypes = parseSimpleTypes(xsd);
  const unresolved = new Map();
  const resolveDataType = makeResolveDataType(simpleTypes, unresolved);

  // Concrete attachment targets from Script 1.
  const schema = JSON.parse(fs.readFileSync(schemaJsonPath, "utf8"));
  const concreteNames = schema.classes.map((c) => c.name);
  const concreteSet = new Set(concreteNames);

  // Phase B — parse all pset/qto files.
  const penums = new Map(); // PEnum name -> options[]
  const dataTypesUsed = new Set();
  const parsedSets = [];

  const files = fs
    .readdirSync(psetsDir)
    .filter((f) => f.toLowerCase().endsWith(".xml"))
    .sort((a, b) => a.localeCompare(b));

  for (const file of files) {
    const xml = fs.readFileSync(path.join(psetsDir, file), "utf8");
    const parsed = parsePsetFile(xml, penums);
    if (!parsed) {
      continue;
    }
    stats.files += 1;
    if (parsed.kind === "pset") {
      stats.psets += 1;
    } else {
      stats.qtos += 1;
    }
    for (const prop of parsed.properties) {
      dataTypesUsed.add(prop.dataType);
    }
    parsedSets.push(parsed);
  }

  // Expand applicable classes to concrete descendants present in our class set.
  // Returns Map<concreteClass, { unconstrained, predefinedTypes:Set }>:
  // - unconstrained = the set applies to the class regardless of predefined type
  // - predefinedTypes = the union of predefined-type constraints (only meaningful
  //   when unconstrained is false).
  function expandApplicable(applicableClasses) {
    const targets = new Map();
    for (const entry of applicableClasses) {
      for (const concrete of concreteNames) {
        if (concrete === entry.base || isDescendantOf(concrete, entry.base)) {
          let t = targets.get(concrete);
          if (!t) {
            t = { unconstrained: false, predefinedTypes: new Set() };
            targets.set(concrete, t);
          }
          if (entry.predefinedType === null) {
            t.unconstrained = true;
          } else {
            t.predefinedTypes.add(entry.predefinedType);
          }
        }
      }
    }
    return targets;
  }

  // Phase C — attach psets to classes.
  const classByName = new Map(schema.classes.map((c) => [c.name, c]));
  for (const c of schema.classes) {
    c.propertySets = [];
  }

  for (const set of parsedSets) {
    const properties = set.properties.map((p) => {
      const obj = { name: p.name, definition: p.definition, dataType: p.dataType };
      if (p.options && p.options.length > 0) {
        obj.options = p.options;
      }
      return obj;
    });
    const targets = expandApplicable(set.applicableClasses);
    for (const [target, constraint] of targets) {
      const cls = classByName.get(target);
      if (!cls) {
        continue;
      }
      const setObject = {
        name: set.name,
        definition: set.definition,
        properties,
      };
      // Attach a predefined-type constraint only when this class is never
      // referenced unconstrained for this set.
      if (!constraint.unconstrained && constraint.predefinedTypes.size > 0) {
        setObject.predefinedTypes = Array.from(constraint.predefinedTypes).sort(
          (a, b) => a.localeCompare(b),
        );
      }
      const existingIdx = cls.propertySets.findIndex((s) => s.name === setObject.name);
      if (existingIdx >= 0) {
        cls.propertySets[existingIdx] = setObject; // dedupe by name (replace)
      } else {
        cls.propertySets.push(setObject);
      }
    }
  }

  // Stable order: sort each class's propertySets by name.
  for (const c of schema.classes) {
    c.propertySets.sort((a, b) => a.name.localeCompare(b.name));
  }

  fs.writeFileSync(schemaJsonPath, JSON.stringify(schema, null, 2) + "\n", "utf8");

  // Phase D — build resources catalogue.
  const resources = [];
  const resourceNames = new Set();

  for (const typeName of dataTypesUsed) {
    if (penums.has(typeName)) {
      // PEnum handled below to guarantee inline options.
      continue;
    }
    const resolved = resolveDataType(typeName);
    const entry = { name: typeName, inputType: resolved.inputType, dataType: resolved.dataType };
    if (resolved.options && resolved.options.length > 0) {
      entry.options = resolved.options;
    }
    resources.push(entry);
    resourceNames.add(typeName);
  }

  for (const [enumName, options] of penums.entries()) {
    if (resourceNames.has(enumName)) {
      continue;
    }
    resources.push({ name: enumName, inputType: "select", dataType: "ENUM", options });
    resourceNames.add(enumName);
  }

  resources.sort((a, b) => a.name.localeCompare(b.name));
  fs.writeFileSync(
    resourcesJsonPath,
    JSON.stringify({ classes: resources }, null, 2) + "\n",
    "utf8",
  );

  // Summary.
  const setsAttached = schema.classes.reduce((n, c) => n + c.propertySets.length, 0);
  console.log("[generate-psets] Summary:");
  console.log(`  files parsed:        ${stats.files} (psets ${stats.psets}, qtos ${stats.qtos})`);
  console.log(`  pset instances attached to classes: ${setsAttached}`);
  console.log(`  distinct data types: ${dataTypesUsed.size}`);
  console.log(`  PEnums:              ${penums.size}`);
  console.log(`  resource entries:    ${resources.length}`);
  console.log(`  skipped ReferenceValue: ${stats.skippedReference}, ComplexProperty: ${stats.skippedComplex}`);
  console.log(`  unknown QtoTypes:    ${stats.unknownQto}`);
  if (unresolved.size > 0) {
    console.log(`  unresolved types -> text/STRING fallback (${unresolved.size}):`);
    for (const [name, count] of unresolved.entries()) {
      console.log(`    - ${name} (${count})`);
    }
  }
  console.log(
    `  wrote ${path.relative(projectRoot, schemaJsonPath)} and ${path.relative(projectRoot, resourcesJsonPath)}`,
  );
}

main();
