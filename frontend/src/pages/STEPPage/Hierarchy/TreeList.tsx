import { useState } from "react";
import { TreeNode } from "./buildTree";
import { SelectNode } from "./HierarchyButtons/buttons/SelectNode";

type TreeListProps = {
  tree: TreeNode[];
  level?: number;
  maxLevel?: number;
  handleSelectNode: (uri: string) => void;
};

export function TreeList({
  tree,
  level = 0,
  maxLevel = 4,
  handleSelectNode,
}: TreeListProps) {
  return (
    <ul style={{ paddingLeft: level === 0 ? 0 : 20 }}>
      {tree.map((node) => (
        <TreeItem
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

type TreeItemProps = {
  node: TreeNode;
  level: number;
  maxLevel: number;
  handleSelectNode: (uri: string) => void;
};

function TreeItem({ node, level, maxLevel, handleSelectNode }: TreeItemProps) {
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
          {/* Always reserve arrow space */}
          <span style={{ display: "inline-block", width: 16 }}>
            {hasChildren ? (isOpen ? "▼" : "▶") : ""}
          </span>
          <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
            <span
              className="material-icons-round"
              style={{
                fontSize: 16,
                color: "var(--grey-5)",
                rotate: "270deg",
              }}>
              {node.dimensions ? "square" : "schema"}
            </span>
            {node.id.split("#")[1]}
            {node.isFundamental && (
              <div>
                <img src="./IFC-logo.png" style={{ height: 16, width: 16 }} />
              </div>
            )}
            {node.toBeDeleted && (
              <span
                className="material-icons-round"
                style={{ fontSize: 16, color: "red" }}>
                clear
              </span>
            )}
            {node.toBeSimplified && (
              <span
                className="material-icons-round"
                style={{ fontSize: 16, color: "var(--primary)" }}>
                crop_square
              </span>
            )}
          </div>
        </div>
        <SelectNode uri={node.id} onClick={(uri) => handleSelectNode(uri)} />
        {/* <HierarchyButtons uri={node.id} onAddChild={handleOpenAddChild} /> */}
      </div>
      {hasChildren && isOpen && (
        <TreeList
          tree={node.children}
          level={level + 1}
          maxLevel={maxLevel}
          handleSelectNode={handleSelectNode}
        />
      )}
    </li>
  );
}
