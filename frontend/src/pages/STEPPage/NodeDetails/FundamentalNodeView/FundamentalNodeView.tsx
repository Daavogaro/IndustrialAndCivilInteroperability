import { TreeNode } from "../../Hierarchy/buildTree";

type FundamentalNodeViewProps = {
  childrenNodes: TreeNode[];
  onSelectNode: (uri: string) => void;
  onToggleDelete: (metadata: string, value: boolean) => void;
  onToggleSimplify: (metadata: string, value: boolean) => void;
  onRowHover: (uri: string | null) => void;
};

export function FundamentalNodeView({
  childrenNodes,
  onSelectNode,
  onToggleDelete,
  onToggleSimplify,
  onRowHover,
}: FundamentalNodeViewProps) {
  if (!childrenNodes.length) {
    return (
      <table>
        <thead>
          <tr>
            <th>CAD Type</th>
            <th>Child Name</th>
            <th>To be deleted</th>
            <th>To be simplified</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td colSpan={4} style={{ textAlign: "center" }}>
              No CADPart children
            </td>
          </tr>
        </tbody>
      </table>
    );
  }

  const seenMetadata = new Set<string>();
  const filteredChildrenNodes = childrenNodes
    .filter((child) => {
      if (seenMetadata.has(child.metadata)) return false;
      seenMetadata.add(child.metadata);
      return true;
    })
    .sort((nodeA, nodeB) => {
      if (nodeA.toBeDeleted && !nodeB.toBeDeleted) return 1;
      if (!nodeA.toBeDeleted && nodeB.toBeDeleted) return -1;
      return 0;
    });

  const allDeleted = filteredChildrenNodes.every(
    (child) => !!child.toBeDeleted,
  );
  const simplifiableChildren = filteredChildrenNodes.filter(
    (child) => child.cadType.split("#")[1] !== "CADAssembly",
  );
  const allSimplified =
    simplifiableChildren.length > 0 &&
    simplifiableChildren.every((child) => !!child.toBeSimplified);

  const handleToggleAllDelete = () => {
    const newValue = !allDeleted;
    filteredChildrenNodes.forEach((child) =>
      onToggleDelete(child.metadata, newValue),
    );
  };

  const handleToggleAllSimplify = () => {
    const newValue = !allSimplified;
    simplifiableChildren.forEach((child) =>
      onToggleSimplify(child.metadata, newValue),
    );
  };

  return (
    <table>
      <thead>
        <tr>
          <th>CAD Type</th>
          <th>Child Name</th>
          <th>
            <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
              To be deleted{" "}
              <span
                className="generalButton material-icons-round"
                onClick={handleToggleAllDelete}>
                {allDeleted ? "clear_all" : "done_all"}
              </span>
            </div>
          </th>
          <th>
            <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
              To be simplified{" "}
              <span
                className={`generalButton material-icons-round ${
                  simplifiableChildren.length === 0 ? "disabled" : ""
                }`}
                onClick={handleToggleAllSimplify}>
                {allSimplified ? "clear_all" : "done_all"}
              </span>
            </div>
          </th>
        </tr>
      </thead>
      <tbody>
        {filteredChildrenNodes.map((child) => {
          const cadTypeLabel = child.cadType.split("#")[1];
          const metadataLabel = child.metadata.split("#")[1];

          return (
            <tr
              key={child.id}
              onMouseEnter={() => onRowHover(child.id)}
              onMouseLeave={() => onRowHover(null)}>
              <td>{cadTypeLabel}</td>

              <td onClick={() => onSelectNode(child.id)}>
                <u style={{ cursor: "pointer", textUnderlineOffset: 3 }}>
                  {metadataLabel}
                </u>
              </td>

              <td style={{ textAlign: "center" }}>
                <input
                  type="checkbox"
                  checked={!!child.toBeDeleted}
                  onChange={(e) =>
                    onToggleDelete(child.metadata, e.target.checked)
                  }
                />
              </td>

              <td style={{ textAlign: "center" }}>
                <input
                  type="checkbox"
                  checked={!!child.toBeSimplified}
                  disabled={cadTypeLabel === "CADAssembly"}
                  onChange={(e) =>
                    onToggleSimplify(child.metadata, e.target.checked)
                  }
                />
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
