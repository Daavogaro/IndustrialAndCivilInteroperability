import { useState } from "react";
import { TreeNode } from "../../STEPPage/Hierarchy/buildTree";
import { SelectNode } from "../../STEPPage/Hierarchy/HierarchyButtons/buttons/SelectNode";

type IfcTreeListProps = {
  tree: TreeNode[];
  level?: number;
  maxLevel?: number;
  handleSelectNode: (uri: string) => void;
};

export function IfcTreeList({
  tree,
  level = 0,
  maxLevel = 4,
  handleSelectNode,
}: IfcTreeListProps) {
  return (
    <ul style={{ paddingLeft: level === 0 ? 0 : 20 }}>
      {tree.map((node) => (
        <IFCTreeItem
          key={node.id}
          node={node}
          level={level}
          maxLevel={maxLevel}
          handleSelectNode={handleSelectNode}
        />
      ))}
    </ul>
  );
}

type IFCTreeItemProps = {
  node: TreeNode;
  level: number;
  maxLevel: number;
  handleSelectNode: (uri: string) => void;
};

function IFCTreeItem({
  node,
  level,
  maxLevel,
  handleSelectNode,
}: IFCTreeItemProps) {
  const hasChildren = node.children.length > 0;

  const [isOpen, setIsOpen] = useState(level < maxLevel);

  return (
    <li>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
        className="tree-row">
        <div
          style={{
            cursor: hasChildren ? "pointer" : "default",
            display: "flex",
            alignItems: "center",
            gap: 8,
          }}
          onClick={() => hasChildren && setIsOpen((prev) => !prev)}>
          <span style={{ display: "inline-block", width: 16 }}>
            {hasChildren ? (isOpen ? "▼" : "▶") : ""}
          </span>
          <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
            {node.id.split("#")[1]}
            {node.ifcClass && (
              <div>
                <img src="./IFC-logo.png" style={{ height: 16, width: 16 }} />
              </div>
            )}
          </div>
        </div>
        <SelectNode uri={node.id} onClick={(uri) => handleSelectNode(uri)} />
      </div>
      {hasChildren && isOpen && (
        <IfcTreeList
          tree={node.children}
          level={level + 1}
          maxLevel={maxLevel}
          handleSelectNode={handleSelectNode}
        />
      )}
    </li>
  );
}
