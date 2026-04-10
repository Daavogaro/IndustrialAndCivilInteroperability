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

function extractIfcEntityClasses(dtsContent) {
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

  const ifc4x3Block = dtsContent.slice(blockStart + 1, blockEnd);

  const classNames = new Set();
  const extendsMap = new Map();
  const abstractMap = new Map();
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

  return Array.from(classNames)
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
}

function main() {
  if (!fs.existsSync(schemaDtsPath)) {
    console.error(`Cannot find IFC schema declaration file at ${schemaDtsPath}`);
    process.exit(1);
  }

  const dtsContent = fs.readFileSync(schemaDtsPath, "utf8");
  const extractedClasses = extractIfcEntityClasses(dtsContent);

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

    return {
      name,
      predefinedTypes: existing?.predefinedTypes || defaultClassConfig.predefinedTypes,
      // Preserve only existing pset definitions. Do not auto-generate new psets.
      propertySets: existing?.propertySets || defaultClassConfig.propertySets,
    };
  });

  const output = { classes };
  fs.writeFileSync(outputJsonPath, JSON.stringify(output, null, 2) + "\n", "utf8");

  console.log(`Generated ${classes.length} IFC classes in ${path.relative(projectRoot, outputJsonPath)}`);
}

main();
