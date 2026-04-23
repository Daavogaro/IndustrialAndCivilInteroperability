import { or } from "three/src/nodes/TSL.js";

export type TreeNode = {
  id: string;
  cadType: string;
  metadata: string;
  dimensions?: string;
  toBeDeleted?: boolean;
  toBeSimplified?: boolean;
  isFundamental?: boolean;
  ifcClass?: string;
  psets?: {
    [psetName: string]: { [propertyName: string]: string | number | boolean };
  };
  predefinedType?: string;
  objectType?: string;
  fileUrl?: string;
  children: TreeNode[];
};

export function buildTree(
  edges: {
    parent: string;
    child: string;
    cadType: string;
    metadata: string;
    visible?: string;
    display?: string;
    dimensions?: string;
    attrib?: string;
    fileUrl?: string;
  }[],
  roots: {
    uri: string;
    cadType: string;
    metadata: string;
    dimensions?: string;
    visible?: string;
    display?: string;
    attrib?: string;
    fileUrl?: string;
  }[],
  ifcData: {
    node: string;
    ifcClass: string;
    predefinedType: string;
    objectType: string;
  }[],
  ifcPsetData: {
    node: string;
    psetName: string;
    propName: string;
    propValue: string | number | boolean;
    datatype: string;
  }[],
): TreeNode[] {
  const map = new Map<string, TreeNode>();

  // Get or create a node
  function getNode(id: string): TreeNode {
    let node = map.get(id);
    if (!node) {
      node = {
        id,
        cadType: "ERROR",
        metadata: "ERROR",
        children: [],
      };
      map.set(id, node);
    }
    return node;
  }
  // Build edges
  for (const {
    parent,
    child,
    cadType,
    metadata,
    visible,
    display,
    dimensions,
    attrib,
    fileUrl,
  } of edges) {
    const parentNode = getNode(parent);
    const childNode = getNode(child);
    childNode.cadType = cadType;
    childNode.metadata = metadata;
    if (fileUrl) {
      childNode.fileUrl = fileUrl;
    }

    if (!parentNode.children.includes(childNode)) {
      parentNode.children.push(childNode);
    }

    if (visible === "false" || visible === "0") {
      childNode.toBeDeleted = true;
    }

    if (display === "true" || display === "1") {
      childNode.toBeSimplified = true;
    }
    if (dimensions) {
      childNode.dimensions = dimensions;
    }

    if (attrib === "Fundamental_Node") {
      childNode.isFundamental = true;
    }
  }
  // Update nodes with IFC data
  for (const { node, ifcClass, predefinedType, objectType } of ifcData) {
    const treeNode = getNode(node);
    treeNode.ifcClass = ifcClass;
    treeNode.predefinedType = predefinedType;
    if (objectType) {
      treeNode.objectType = objectType;
    }
  }

  for (const { node, psetName, propName, propValue, datatype } of ifcPsetData) {
    const treeNode = getNode(node);
    if (!treeNode.psets) {
      treeNode.psets = {};
    }
    if (!treeNode.psets[psetName]) {
      treeNode.psets[psetName] = {};
    }
    if (datatype.split("#")[1] === "string") {
      treeNode.psets[psetName][propName] = String(propValue);
    } else if (
      datatype.split("#")[1] === "integer" ||
      datatype.split("#")[1] === "double" ||
      datatype.split("#")[1] === "real"
    ) {
      treeNode.psets[psetName][propName] = Number(propValue);
    } else if (datatype.split("#")[1] === "boolean") {
      if (
        propValue === "true" ||
        propValue === true ||
        propValue === "1" ||
        propValue === 1
      ) {
        treeNode.psets[psetName][propName] = true;
      } else {
        treeNode.psets[psetName][propName] = false;
      }
    }
  }

  // Resolve roots
  return roots.map(
    ({
      uri,
      cadType,
      metadata,
      dimensions,
      visible,
      display,
      attrib,
      fileUrl,
    }) => {
      const rootNode = getNode(uri);
      rootNode.cadType = cadType;
      rootNode.metadata = metadata;
      if (dimensions) {
        rootNode.dimensions = dimensions;
      }

      if (visible === "false" || visible === "0") {
        rootNode.toBeDeleted = true;
      }
      if (display === "true" || display === "1") {
        rootNode.toBeSimplified = true;
      }
      if (attrib === "Fundamental_Node") {
        rootNode.isFundamental = true;
      }
      if (fileUrl) {
        rootNode.fileUrl = fileUrl;
      }

      return rootNode;
    },
  );
}
