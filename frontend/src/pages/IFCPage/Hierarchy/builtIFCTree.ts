import { TreeNode } from "../../STEPPage/Hierarchy/buildTree";

export function buildFundamentalTree(tree: TreeNode[]): TreeNode[] {
  const result: TreeNode[] = [];

  for (const node of tree) {
    const extracted = extractFundamental(node);
    result.push(...extracted);
  }

  return result;
}

function extractFundamental(node: TreeNode): TreeNode[] {
  const fundamentalChildren: TreeNode[] = [];

  for (const child of node.children) {
    const extractedChildren = extractFundamental(child);
    fundamentalChildren.push(...extractedChildren);
  }

  if (node.isFundamental) {
    // Recreate node with only fundamental children
    return [
      {
        ...node,
        children: fundamentalChildren,
      },
    ];
  }

  // If not fundamental → bubble children up
  return fundamentalChildren;
}
