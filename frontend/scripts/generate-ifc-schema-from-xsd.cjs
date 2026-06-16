const fs = require("fs");
const path = require("path");

// ---------------------------------------------------------------------------
// Script 1 — Generate the IFC class skeleton of ifcPropertySchema.json directly
// from the IFC XSD (no web-ifc dependency).
//
// Emits ONLY concrete (non-abstract), non-"*Type" classes that descend from
// IfcElement, each with its PredefinedType enum values (UPPERCASED) and an
// EMPTY propertySets array. Script 2 (generate-psets-from-xml.cjs) attaches the
// property sets afterwards.
// ---------------------------------------------------------------------------

const projectRoot = path.resolve(__dirname, "..");
const xsdPath = path.join(
  projectRoot,
  "public",
  "ifc-schema",
  "IFC4X3_DEV_dcfeedc.xsd",
);
const outputJsonPath = path.join(
  projectRoot,
  "src",
  "pages",
  "IFCPage",
  "NodeDetails",
  "ifcPropertySchema.json",
);

const ROOT_CLASS = "IfcElement";

// ---------------------------------------------------------------------------
// XSD parsing core (shared in spirit with Script 2; duplicated to keep each
// script standalone, matching the original single-file generator style).
// ---------------------------------------------------------------------------

// Map: className -> { parent, isAbstract }
function parseClassHierarchy(xsd) {
  const hierarchy = new Map();
  // Each class is declared by an <xs:element name="IfcXxx" ... /> tag whose
  // substitutionGroup attribute names its parent and which may carry
  // abstract="true". Capture the full attribute string of every element tag.
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
    const parent = parentMatch ? parentMatch[1] : null;
    const isAbstract = /\babstract="true"/i.test(attrs);
    // First declaration wins (element declarations are unique per class).
    if (!hierarchy.has(name)) {
      hierarchy.set(name, { parent, isAbstract });
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

// Map: complexType name -> inner block text
function parseComplexTypeBlocks(xsd) {
  const blocks = new Map();
  const regex = /<xs:complexType name="(Ifc[A-Za-z0-9_]+)"[^>]*>([\s\S]*?)<\/xs:complexType>/g;
  let match;
  while ((match = regex.exec(xsd)) !== null) {
    blocks.set(match[1], match[2]);
  }
  return blocks;
}

// Map: enum simpleType name (IfcXxxTypeEnum) -> UPPERCASED string[]
function parseEnumValues(xsd) {
  const enums = new Map();
  const regex = /<xs:simpleType name="(Ifc[A-Za-z0-9_]+TypeEnum)">([\s\S]*?)<\/xs:simpleType>/g;
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

// Resolve PredefinedType enum values for a class, walking up the inheritance
// chain to the nearest ancestor that declares a PredefinedType attribute.
function resolvePredefinedTypes(className, hierarchy, complexTypeBlocks, enumValues) {
  let current = className;
  const visited = new Set();
  const attrRegex = /<xs:attribute name="PredefinedType" type="ifc:(Ifc[A-Za-z0-9_]+)"/;
  while (current && !visited.has(current)) {
    visited.add(current);
    const body = complexTypeBlocks.get(current);
    if (body) {
      const attrMatch = body.match(attrRegex);
      if (attrMatch) {
        const values = enumValues.get(attrMatch[1]);
        if (values && values.length > 0) {
          return values;
        }
        // PredefinedType declared but enum not found — stop walking.
        break;
      }
    }
    const entry = hierarchy.get(current);
    current = entry ? entry.parent : null;
  }
  return ["NOTDEFINED"];
}

function main() {
  if (!fs.existsSync(xsdPath)) {
    console.error(`Cannot find IFC XSD at ${xsdPath}`);
    process.exit(1);
  }

  const xsd = fs.readFileSync(xsdPath, "utf8");

  const hierarchy = parseClassHierarchy(xsd);
  const isDescendantOf = makeIsDescendantOf(hierarchy);
  const complexTypeBlocks = parseComplexTypeBlocks(xsd);
  const enumValues = parseEnumValues(xsd);

  const includedNames = Array.from(hierarchy.keys())
    .filter((name) => {
      const entry = hierarchy.get(name);
      if (entry.isAbstract) {
        return false; // exclude abstract classes
      }
      if (name.endsWith("Type")) {
        return false; // exclude Ifc*Type classes
      }
      if (!isDescendantOf(name, ROOT_CLASS)) {
        return false; // keep only the IfcElement taxonomy
      }
      return true;
    })
    .sort((a, b) => a.localeCompare(b));

  if (includedNames.length === 0) {
    console.error("No concrete IfcElement descendants were extracted from the XSD.");
    process.exit(1);
  }

  const classes = includedNames.map((name) => ({
    name,
    predefinedTypes: resolvePredefinedTypes(
      name,
      hierarchy,
      complexTypeBlocks,
      enumValues,
    ),
    propertySets: [], // fresh skeleton; Script 2 fills this in.
  }));

  const output = { classes };
  fs.writeFileSync(outputJsonPath, JSON.stringify(output, null, 2) + "\n", "utf8");

  console.log(
    `[generate-ifc-schema-from-xsd] Wrote ${classes.length} concrete ${ROOT_CLASS} descendants ` +
      `to ${path.relative(projectRoot, outputJsonPath)}`,
  );
}

main();
