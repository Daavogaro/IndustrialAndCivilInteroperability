import { useState } from "react";
import { TreeNode } from "../../STEPPage/Hierarchy/buildTree";

type IfcTreeListProps = {
  tree: TreeNode[];
  level?: number;
  maxLevel?: number;
  selectedUris: string[];
  onToggleSelect: (uri: string) => void;
};

export function IfcTreeList({
  tree,
  level = 0,
  maxLevel = 4,
  selectedUris,
  onToggleSelect,
}: IfcTreeListProps) {
  return (
    <ul style={{ paddingLeft: level === 0 ? 0 : 20 }}>
      {tree.map((node) => (
        <IFCTreeItem
          key={node.id}
          node={node}
          level={level}
          maxLevel={maxLevel}
          selectedUris={selectedUris}
          onToggleSelect={onToggleSelect}
        />
      ))}
    </ul>
  );
}

type IFCTreeItemProps = {
  node: TreeNode;
  level: number;
  maxLevel: number;
  selectedUris: string[];
  onToggleSelect: (uri: string) => void;
};

function IFCTreeItem({
  node,
  level,
  maxLevel,
  selectedUris,
  onToggleSelect,
}: IFCTreeItemProps) {
  const hasChildren = node.children.length > 0;
  const isSelected = selectedUris.includes(node.id);
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
            display: "flex",
            alignItems: "center",
            gap: 8,
          }}>
          <input
            type="checkbox"
            checked={isSelected}
            onChange={() => onToggleSelect(node.id)}
            onClick={(e) => e.stopPropagation()}
            style={{ cursor: "pointer", flexShrink: 0 }}
          />
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
        </div>
      </div>
      {hasChildren && isOpen && (
        <IfcTreeList
          tree={node.children}
          level={level + 1}
          maxLevel={maxLevel}
          selectedUris={selectedUris}
          onToggleSelect={onToggleSelect}
        />
      )}
    </li>
  );
}
