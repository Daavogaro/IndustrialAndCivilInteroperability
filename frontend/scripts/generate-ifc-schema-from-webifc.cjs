const fs = require("fs");
const path = require("path");

const projectRoot = path.resolve(__dirname, "..");
const schemaDtsPath = path.join(projectRoot, "node_modules", "web-ifc", "ifc-schema.d.ts");
const outputJsonPath = path.join(
  projectRoot,
  "src",
  "pages",
  "IFCPage",
  "NodeDetails",
  "ifcPropertySchema.json",
);

const defaultClassConfig = {
  predefinedTypes: ["NOTDEFINED"],
  propertySets: [],
};

function readJson(filePath) {
  if (!fs.existsSync(filePath)) {
    return { classes: [] };
  }

  try {
    return JSON.parse(fs.readFileSync(filePath, "utf8"));
  } catch (error) {
    console.error(`Failed to parse JSON at ${filePath}:`, error);
    process.exit(1);
  }
}

function getIfc4x3Block(dtsContent) {
  const namespaceToken = "export declare namespace IFC4X3";
  const namespaceStartIndex = dtsContent.indexOf(namespaceToken);

  if (namespaceStartIndex === -1) {
    console.error("IFC4X3 namespace not found in ifc-schema.d.ts.");
    process.exit(1);
  }

  const blockStart = dtsContent.indexOf("{", namespaceStartIndex);
  if (blockStart === -1) {
    console.error("Cannot find IFC4X3 namespace block start.");
    process.exit(1);
  }

  let depth = 0;
  let blockEnd = -1;

  for (let i = blockStart; i < dtsContent.length; i += 1) {
    const ch = dtsContent[i];
    if (ch === "{") {
      depth += 1;
    } else if (ch === "}") {
      depth -= 1;
      if (depth === 0) {
        blockEnd = i;
        break;
      }
    }
  }

  if (blockEnd === -1) {
    console.error("Cannot find IFC4X3 namespace block end.");
    process.exit(1);
  }

  return dtsContent.slice(blockStart + 1, blockEnd);
}

function extractIfcSchemaData(dtsContent) {
  const ifc4x3Block = getIfc4x3Block(dtsContent);

  const classNames = new Set();
  const extendsMap = new Map();
  const abstractMap = new Map();
  const classBodyMap = new Map();
  const classRegex = /(abstract\s+)?class\s+(Ifc[A-Za-z0-9_]+)\s+extends\s+(Ifc[A-Za-z0-9_]+)/g;

  let match;
  while ((match = classRegex.exec(ifc4x3Block)) !== null) {
    const isAbstract = Boolean(match[1]);
    const className = match[2];
    const baseClass = match[3];

    extendsMap.set(className, baseClass);
    abstractMap.set(className, isAbstract);

    classNames.add(className);
  }

  const classBlockRegex = /(?:abstract\s+)?class\s+(Ifc[A-Za-z0-9_]+)(?:\s+extends\s+Ifc[A-Za-z0-9_]+)?\s*\{([\s\S]*?)\n\s*\}/g;
  while ((match = classBlockRegex.exec(ifc4x3Block)) !== null) {
    classBodyMap.set(match[1], match[2]);
  }

  const enumValuesByName = new Map();
  for (const [className, body] of classBodyMap.entries()) {
    if (!className.endsWith("TypeEnum")) {
      continue;
    }

    const values = [];
    const seen = new Set();
    const staticValueRegex = /static\s+([A-Z0-9_]+)\s*:/g;
    let staticMatch;

    while ((staticMatch = staticValueRegex.exec(body)) !== null) {
      const value = staticMatch[1];
      if (!seen.has(value)) {
        seen.add(value);
        values.push(value);
      }
    }

    if (values.length > 0) {
      enumValuesByName.set(className, values);
    }
  }

  const isDescendantOf = (className, ancestorName) => {
    let current = className;
    const visited = new Set();

    while (current && !visited.has(current)) {
      if (current === ancestorName) {
        return true;
      }
      visited.add(current);
      current = extendsMap.get(current);
    }

    return false;
  };

  const classes = Array.from(classNames)
    .filter((className) => {
      // Exclude abstract classes.
      if (abstractMap.get(className)) {
        return false;
      }

      // Exclude Ifc*Type classes.
      if (className.endsWith("Type")) {
        return false;
      }

      // Keep only classes in IfcElement taxonomy.
      if (!isDescendantOf(className, "IfcElement")) {
        return false;
      }

      // Ensure class inherits from IfcRoot (therefore has GlobalId semantics).
      if (!isDescendantOf(className, "IfcRoot")) {
        return false;
      }

      return true;
    })
    .sort((a, b) => a.localeCompare(b));

  const predefinedTypesByClass = new Map();
  const predefinedTypeRegex = /\bPredefinedType\s*:\s*(Ifc[A-Za-z0-9_]*TypeEnum)/;

  for (const className of classes) {
    let current = className;
    const visited = new Set();
    let predefinedTypes = null;

    while (current && !visited.has(current)) {
      visited.add(current);
      const body = classBodyMap.get(current);

      if (body) {
        const predefinedMatch = body.match(predefinedTypeRegex);
        if (predefinedMatch) {
          const enumName = predefinedMatch[1];
          const enumValues = enumValuesByName.get(enumName);
          if (enumValues && enumValues.length > 0) {
            predefinedTypes = enumValues;
          }
          break;
        }
      }

      current = extendsMap.get(current);
    }

    if (predefinedTypes && predefinedTypes.length > 0) {
      predefinedTypesByClass.set(className, predefinedTypes);
    }
  }

  return {
    classes,
    predefinedTypesByClass,
  };
}

function main() {
  if (!fs.existsSync(schemaDtsPath)) {
    console.error(`Cannot find IFC schema declaration file at ${schemaDtsPath}`);
    process.exit(1);
  }

  const dtsContent = fs.readFileSync(schemaDtsPath, "utf8");
  const schemaData = extractIfcSchemaData(dtsContent);
  const extractedClasses = schemaData.classes;

  if (extractedClasses.length === 0) {
    console.error("No IFC classes were extracted from ifc-schema.d.ts.");
    process.exit(1);
  }

  const currentSchema = readJson(outputJsonPath);
  const existingByName = new Map(
    (currentSchema.classes || []).map((item) => [item.name, item]),
  );

  const classes = extractedClasses.map((name) => {
    const existing = existingByName.get(name);
    const generatedPredefinedTypes = schemaData.predefinedTypesByClass.get(name);
    const mergedPredefinedTypes = generatedPredefinedTypes
      ? Array.from(new Set([...(generatedPredefinedTypes || []), ...(existing?.predefinedTypes || [])]))
      : (existing?.predefinedTypes || defaultClassConfig.predefinedTypes);

    return {
      name,
      predefinedTypes: mergedPredefinedTypes,
      // Preserve only existing pset definitions. Do not auto-generate new psets.
      propertySets: existing?.propertySets || defaultClassConfig.propertySets,
    };
  });

  const output = { classes };
  fs.writeFileSync(outputJsonPath, JSON.stringify(output, null, 2) + "\n", "utf8");

  console.log(`Generated ${classes.length} IFC classes in ${path.relative(projectRoot, outputJsonPath)}`);
}

main();
