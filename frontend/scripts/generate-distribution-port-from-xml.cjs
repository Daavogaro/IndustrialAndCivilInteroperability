const fs = require("fs");
const path = require("path");

// ---------------------------------------------------------------------------
// Script 3 — Extract the IfcDistributionPort "connector" schema:
//   (1) its three attribute enums (PredefinedType / SystemType / FlowDirection)
//       from the XSD, UPPERCASED to match the project convention;
//   (2) the property sets applicable to IfcDistributionPort from the pset XML
//       corpus, in the SAME shape as ifcPropertySchema.json's propertySets so
//       the existing IFCNodeDetails pset renderer/handlers work unchanged.
//
// Writes ifcDistributionPort.json next to ifcPropertySchema.json.
//
// NOTE: the data types referenced by these psets are registered in
// resourcesIFCSchema.json by generate-psets-from-xml.cjs (it scans ALL pset
// files), so run `generate:psets` at least once for the resources catalogue to
// be complete. Node built-ins only; no XML/XSD parser dependency.
// ---------------------------------------------------------------------------

const projectRoot = path.resolve(__dirname, "..");
const xsdPath = path.join(
  projectRoot,
  "public",
  "ifc-schema",
  "IFC4X3_DEV_dcfeedc.xsd",
);
const psetsDir = path.join(projectRoot, "public", "ifc-schema", "psets");
const outputJsonPath = path.join(
  projectRoot,
  "src",
  "pages",
  "IFCPage",
  "NodeDetails",
  "ifcDistributionPort.json",
);

const PORT_CLASS = "IfcDistributionPort";
// XSD enum simpleType -> attribute key exposed to the UI.
const ATTRIBUTE_ENUMS = {
  PredefinedType: "IfcDistributionPortTypeEnum",
  SystemType: "IfcDistributionSystemEnum",
  FlowDirection: "IfcFlowDirectionEnum",
};

// ---------------------------------------------------------------------------
// XML / text helpers (mirrored from generate-psets-from-xml.cjs to keep this
// script standalone, matching the original generator style).
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
// XSD enum parsing — GENERIC `Ifc...Enum` matcher (the existing schema
// generators only match `...TypeEnum`, which would miss IfcDistributionSystemEnum
// and IfcFlowDirectionEnum). Values are UPPERCASED, preserving XSD order.
// ---------------------------------------------------------------------------

function parseEnumValues(xsd) {
  const enums = new Map();
  const regex = /<xs:simpleType name="(Ifc[A-Za-z0-9_]+Enum)">([\s\S]*?)<\/xs:simpleType>/g;
  let match;
  while ((match = regex.exec(xsd)) !== null) {
    const enumName = match[1];
    const body = match[2];
    const values = [];
    const seen = new Set();
    const valRegex = /<xs:enumeration value="([^"]*)"\s*\/>/g;
    let valMatch;
    while ((valMatch = valRegex.exec(body)) !== null) {
      const value = valMatch[1].toUpperCase();
      if (!seen.has(value)) {
        seen.add(value);
        values.push(value);
      }
    }
    if (values.length > 0) {
      enums.set(enumName, values);
    }
  }
  return enums;
}

// ---------------------------------------------------------------------------
// Pset XML parsing — same logic as generate-psets-from-xml.cjs (enumerated ->
// inline options + PEnum_* dataType; table -> DefinedValue; reference/complex
// skipped). The resources catalogue is owned by generate:psets, so PEnum names
// are collected only locally and discarded.
// ---------------------------------------------------------------------------

function extractDataTypeAttr(block) {
  const m = block.match(/<DataType type="([^"]+)"\s*\/>/);
  return m ? m[1] : null;
}

function parsePropertyDef(block, penums) {
  const name = normalizeDefinition(firstTagText(block, "Name"));
  const definition = normalizeDefinition(firstTagText(block, "Definition"));
  if (!name) {
    return null;
  }

  if (block.includes("<TypePropertyReferenceValue")) {
    return null; // object reference — not representable in the flat form
  }
  if (block.includes("<TypeComplexProperty")) {
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
    if (!penums.has(enumName)) {
      penums.set(enumName, options);
    }
    return { name, definition, dataType: enumName, options };
  }

  if (block.includes("<TypePropertyTableValue")) {
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

const QTO_TYPE_MAP = {
  Q_LENGTH: "IfcQuantityLength",
  Q_AREA: "IfcQuantityArea",
  Q_VOLUME: "IfcQuantityVolume",
  Q_WEIGHT: "IfcQuantityWeight",
  Q_COUNT: "IfcQuantityCount",
  Q_TIME: "IfcQuantityTime",
  Q_NUMBER: "IfcReal",
};

function parseQtoDef(block) {
  const name = normalizeDefinition(firstTagText(block, "Name"));
  const definition = normalizeDefinition(firstTagText(block, "Definition"));
  const qtoTypeMatch = block.match(/<QtoType>([\s\S]*?)<\/QtoType>/);
  const qtoType = qtoTypeMatch ? qtoTypeMatch[1].trim() : null;
  if (!name || !qtoType) {
    return null;
  }
  const dataType = QTO_TYPE_MAP[qtoType] || "IfcReal";
  return { name, definition, dataType };
}

// Parse one pset/qto file -> { name, definition, applicableClasses, properties } | null
function parsePsetFile(xml, penums) {
  const isPset = xml.includes("<PropertySetDef");
  const isQto = xml.includes("<QtoSetDef");
  if (!isPset && !isQto) {
    return null;
  }

  const defsIndex = isPset ? xml.indexOf("<PropertyDefs") : xml.indexOf("<QtoDefs");
  const header = defsIndex >= 0 ? xml.slice(0, defsIndex) : xml;

  const name = normalizeDefinition(firstTagText(header, "Name"));
  const definition = normalizeDefinition(firstTagText(header, "Definition"));
  if (!name) {
    return null;
  }

  // Each <ClassName> is "IfcFoo" or "IfcFoo/PREDEFINEDTYPE" (the latter restricts
  // the set to occurrences of that predefined type).
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

  return { name, definition, applicableClasses, properties };
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

function main() {
  for (const p of [xsdPath, psetsDir]) {
    if (!fs.existsSync(p)) {
      console.error(`Missing required input: ${p}`);
      process.exit(1);
    }
  }

  const xsd = fs.readFileSync(xsdPath, "utf8");
  const enumValues = parseEnumValues(xsd);

  // Attributes — read the three enums; ensure a NOTDEFINED fallback always exists.
  const attributes = {};
  for (const [attrKey, enumName] of Object.entries(ATTRIBUTE_ENUMS)) {
    const values = (enumValues.get(enumName) || []).slice();
    if (values.length === 0) {
      console.warn(`[generate-distribution-port] Enum ${enumName} not found in XSD.`);
    }
    if (!values.includes("NOTDEFINED")) {
      values.push("NOTDEFINED");
    }
    attributes[attrKey] = values;
  }

  // Property sets applicable to IfcDistributionPort.
  const penums = new Map();
  const files = fs
    .readdirSync(psetsDir)
    .filter((f) => f.toLowerCase().endsWith(".xml"))
    .sort((a, b) => a.localeCompare(b));

  const propertySets = [];
  for (const file of files) {
    const xml = fs.readFileSync(path.join(psetsDir, file), "utf8");
    const parsed = parsePsetFile(xml, penums);
    if (!parsed) {
      continue;
    }

    // Keep only sets that directly apply to IfcDistributionPort (ports are not
    // an IfcElement subtree, so no descendant expansion is needed).
    const portEntries = parsed.applicableClasses.filter(
      (c) => c.base === PORT_CLASS,
    );
    if (portEntries.length === 0) {
      continue;
    }

    const properties = parsed.properties.map((p) => {
      const obj = { name: p.name, definition: p.definition, dataType: p.dataType };
      if (p.options && p.options.length > 0) {
        obj.options = p.options;
      }
      return obj;
    });

    const setObject = { name: parsed.name, definition: parsed.definition, properties };

    // If every IfcDistributionPort reference is predefined-type-constrained,
    // expose that restriction (e.g. Pset_DistributionPortTypeCable -> ["CABLE"]).
    const unconstrained = portEntries.some((e) => e.predefinedType === null);
    if (!unconstrained) {
      const predefinedTypes = Array.from(
        new Set(portEntries.map((e) => e.predefinedType)),
      ).sort((a, b) => a.localeCompare(b));
      if (predefinedTypes.length > 0) {
        setObject.predefinedTypes = predefinedTypes;
      }
    }

    propertySets.push(setObject);
  }

  propertySets.sort((a, b) => a.name.localeCompare(b.name));

  const output = { name: PORT_CLASS, attributes, propertySets };
  fs.writeFileSync(outputJsonPath, JSON.stringify(output, null, 2) + "\n", "utf8");

  console.log("[generate-distribution-port] Summary:");
  for (const [attrKey, enumName] of Object.entries(ATTRIBUTE_ENUMS)) {
    console.log(`  ${attrKey} (${enumName}): ${attributes[attrKey].length} values`);
  }
  console.log(`  property sets applicable to ${PORT_CLASS}: ${propertySets.length}`);
  console.log(`  wrote ${path.relative(projectRoot, outputJsonPath)}`);
}

main();
