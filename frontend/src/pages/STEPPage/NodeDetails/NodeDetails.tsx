import { useEffect, useState } from "react";
import { StatusString } from "../../../components/Sidebar/MessagePanel";
import { FundamentalNodeButton } from "./FundamentalNodeButton";
import { AssemblyView } from "./AssemblyView/AssemblyView";
import { FundamentalNodeView } from "./FundamentalNodeView/FundamentalNodeView";
import { TreeNode } from "../Hierarchy/buildTree";

type NodeDetailsProps = {
  uri: string | null;
  tree: TreeNode[];
  setNodeUri: (uri: string | null) => void;
  setMessage: (message: { status: StatusString; text: string }) => void;
};
const findNode = (nodes: TreeNode[], uri: string | null): TreeNode | null => {
  for (const node of nodes) {
    if (node.id === uri) return node;

    const foundInChildren = findNode(node.children, uri);
    if (foundInChildren) return foundInChildren;
  }
  return null;
};
export const getDescendantsWithDimensions = (
  tree: TreeNode[],
  uri: string | null,
): TreeNode[] => {
  if (!uri) return [];

  // Step 2: Collect all descendants with hasDimensions === true
  const collectDescendants = (node: TreeNode): TreeNode[] => {
    let result: TreeNode[] = [];

    for (const child of node.children) {
      // Skip traversal inside fundamental nodes
      if (child.isFundamental) {
        continue;
      }

      if (child.dimensions) {
        result.push(child);
      }

      result = result.concat(collectDescendants(child));
    }

    return result;
  };

  const targetNode = findNode(tree, uri);
  if (!targetNode) return [];

  return collectDescendants(targetNode);
};

export function NodeDetails({
  uri,
  tree,
  setNodeUri,
  setMessage,
}: NodeDetailsProps) {
  const [treeNodeData, setTreeNodeData] = useState<TreeNode | null>(null);
  const [childrenNodes, setChildrenNodes] = useState<TreeNode[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onChangeToBeDeleted = async (metadata: string, value: boolean) => {
    const res = await fetch("/api/update-deletion", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        metadata,
        toBeDeleted: value,
      }),
    });

    const responseData = await res.json();
    setMessage({ status: responseData.status, text: responseData.text });

    // Optimistic local update
    setChildrenNodes((prev) =>
      prev.map((child) =>
        child.metadata === metadata ? { ...child, toBeDeleted: value } : child,
      ),
    );
  };

  const onChangeToBeSimplified = async (metadata: string, value: boolean) => {
    const res = await fetch("/api/update-simplification", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        metadata,
        toBeSimplified: value,
      }),
    });

    const responseData = await res.json();
    setMessage({ status: responseData.status, text: responseData.text });

    // Optimistic local update
    setChildrenNodes((prev) =>
      prev.map((child) =>
        child.metadata === metadata
          ? { ...child, toBeSimplified: value }
          : child,
      ),
    );
  };

  useEffect(() => {
    if (!uri) return;

    const fetchData = async () => {
      try {
        setLoading(true);
        setError(null);

        const nodeData = findNode(tree, uri);
        setTreeNodeData(nodeData);
      } catch (err) {
        setError("Failed to fetch node data");
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [uri]);

  if (!uri) return <p>No node selected.</p>;
  if (loading) return <p>Loading...</p>;
  if (error) return <p>{error}</p>;
  if (!treeNodeData) return null;

  function onAssemblyViewClick() {
    const assemblyView = document.getElementById("assembly-view");
    const assemblyViewContent = document.getElementById(
      "assembly-view-content",
    );
    const fundamentalView = document.getElementById("fundamental-view");
    const fundamentalViewContent = document.getElementById(
      "fundamental-view-content",
    );
    if (
      assemblyView &&
      fundamentalView &&
      assemblyViewContent &&
      fundamentalViewContent
    ) {
      assemblyView.className = "toogle-view active";
      fundamentalView.className = "toogle-view";
      assemblyViewContent.style.display = "block";
      fundamentalViewContent.style.display = "none";
    }
  }

  function onFundamentalViewClick() {
    const assemblyView = document.getElementById("assembly-view");
    const assemblyViewContent = document.getElementById(
      "assembly-view-content",
    );
    const fundamentalView = document.getElementById("fundamental-view");
    const fundamentalViewContent = document.getElementById(
      "fundamental-view-content",
    );
    if (
      assemblyView &&
      fundamentalView &&
      assemblyViewContent &&
      fundamentalViewContent
    ) {
      assemblyView.className = "toogle-view";
      fundamentalView.className = "toogle-view active";
      assemblyViewContent.style.display = "none";
      fundamentalViewContent.style.display = "block";
    }
  }
  const assemblyChildren =
    findNode(tree, uri)?.children.filter((child) => {
      return child.cadType.includes("CADPart");
    }) || [];

  return (
    <div
      style={{
        backgroundColor: "var(--background-100)",
        padding: 10,
        border: "1px solid var(--grey-2)",
        borderRadius: 5,
        marginTop: 10,
      }}>
      <div style={{ display: "flex", justifyContent: "space-between" }}>
        <h3 style={{ marginBottom: 10 }}>
          {treeNodeData.metadata.split("#")[1]}
        </h3>
        <FundamentalNodeButton
          metadata={treeNodeData.metadata}
          setMessage={setMessage}
        />
      </div>
      {treeNodeData.cadType ===
        "https://www.web3d.org/specifications/X3dOntology4.0#CADPart" && (
        <div>
          <p>
            <strong>To be deleted:</strong>{" "}
            {treeNodeData.toBeDeleted ? "Yes" : "No"}
          </p>

          <p>
            <strong>To be simplified:</strong>{" "}
            {treeNodeData.toBeSimplified ? "Yes" : "No"}
          </p>

          <p>
            <strong>Size:</strong> {treeNodeData.dimensions}
          </p>
        </div>
      )}
      {treeNodeData.cadType ===
        "https://www.web3d.org/specifications/X3dOntology4.0#CADAssembly" && (
        <>
          <div style={{ marginTop: 10, display: "flex" }}>
            <h5
              id="fundamental-view"
              className="toogle-view active"
              style={{
                borderTopLeftRadius: 10,
              }}
              onClick={onFundamentalViewClick}>
              Fundamental Node
            </h5>
            <h5
              id="assembly-view"
              className="toogle-view "
              style={{ borderTopRightRadius: 10, borderLeft: "none" }}
              onClick={onAssemblyViewClick}>
              Assembly
            </h5>
          </div>

          <div id="fundamental-view-content">
            <FundamentalNodeView
              childrenNodes={getDescendantsWithDimensions(tree, uri)}
              onSelectNode={setNodeUri}
              onToggleDelete={onChangeToBeDeleted}
              onToggleSimplify={onChangeToBeSimplified}
            />
          </div>
          <div id="assembly-view-content" style={{ display: "none" }}>
            <AssemblyView
              childrenNodes={assemblyChildren}
              onSelectNode={setNodeUri}
              onToggleDelete={onChangeToBeDeleted}
              onToggleSimplify={onChangeToBeSimplified}
            />
          </div>
        </>
      )}
    </div>
  );
}
