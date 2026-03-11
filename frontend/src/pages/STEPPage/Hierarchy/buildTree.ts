export type TreeNode = {
  id: string;
  cadType: string;
  metadata: string;
  dimensions?: string;
  toBeDeleted?: boolean;
  toBeSimplified?: boolean;
  isFundamental?: boolean;
  ifcClass?: string;
  predefinedType?: string;
  userdefinedType?: string;
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
    userdefinedType: string;
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
  for (const { node, ifcClass, predefinedType, userdefinedType } of ifcData) {
    const treeNode = getNode(node);
    treeNode.ifcClass = ifcClass;
    treeNode.predefinedType = predefinedType;
    if (userdefinedType) {
      treeNode.userdefinedType = userdefinedType;
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
