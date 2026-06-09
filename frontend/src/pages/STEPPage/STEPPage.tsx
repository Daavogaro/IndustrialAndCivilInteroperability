import { Topbar } from "../../components/Topbar";
import { TreeNode } from "./Hierarchy/buildTree";
import { TreeList } from "./Hierarchy/TreeList";
import { AddChildModal } from "./AddChildModal";
import { HierarchyButtons } from "./Hierarchy/HierarchyButtons/HierarchyButtons";
import { UploadSTEPModal } from "./UploadSTEPModal";
import { StatusString } from "../../components/Sidebar/MessagePanel";
import { GLTFViewer } from "./NodeDetails/gLTFViewer/gLTFViewer";
import { useEffect, useState } from "react";
import { refreshStepHierarchy } from "./Hierarchy/HierarchyButtons/buttons/UpdateHierarchyButton";
import { FundamentalNodeButton } from "./NodeDetails/FundamentalNodeButton";
import { findNode } from "./NodeDetails/NodeDetails";

type STEPPageProps = {
  setTree: (tree: TreeNode[]) => void;
  tree: TreeNode[];
  setNodeUri: (uri: string | null) => void;
  nodeUri: string | null;
  setMessage: (message: { status: StatusString; text: string }) => void;
};

export function STEPPage({
  setMessage: setMessage,
  setTree,
  setNodeUri,
  tree,
  nodeUri,
}: STEPPageProps) {
  const graphName = "http://localhost:8890/Elettra2/";
  const [hoveredUri, setHoveredUri] = useState<string | null>(null);
  const [treeNodeData, setTreeNodeData] = useState<TreeNode | null>(null);
  const nodeData = findNode(tree, nodeUri);

  useEffect(() => {
    if (!nodeUri) {
      setHoveredUri(null);
    }
  }, [nodeUri]);

  useEffect(() => {
    refreshStepHierarchy(setTree, setMessage);
  }, [setTree, setMessage]);

  const handleSelectNode = async (uri: string) => {
    setNodeUri(uri);
  };

  return (
    <div
      style={{
        display: "grid",
        gridTemplateRows: "auto auto 1fr",
        height: "100vh",
        overflow: "hidden",
      }}>
      <AddChildModal uri={nodeUri} />
      <UploadSTEPModal uri={nodeUri} setMessage={setMessage} />
      <Topbar title="STEP Hierarchy" />

      <div style={{ padding: "10px" }}>
        <p>
          <strong>Graph URI:</strong> {graphName}
        </p>
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          minHeight: 0,
          margin: "0px 10px 10px 10px",
          gap: "10px",
        }}>
        <div
          style={{
            display: "grid",
            gridTemplateRows: "auto 1fr",
            minHeight: 0,
          }}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "0.5rem",
              marginBottom: "0.5rem",
            }}>
            <h2>Hierarchy</h2>
            <HierarchyButtons setTree={setTree} setMessage={setMessage} />
          </div>
          <div
            style={{
              minHeight: 0,
              border: "1px solid var(--grey-2)",
              borderRadius: 5,
              backgroundColor: "var(--background-100)",
              padding: "8px",
            }}
            className="panel-scroll">
            {tree.length > 0 ? (
              <TreeList tree={tree} handleSelectNode={handleSelectNode} />
            ) : (
              <p>No hierarchy built yet.</p>
            )}
          </div>
        </div>

        <div
          style={{
            display: "grid",
            gridTemplateRows: "auto 1fr",
            minHeight: 0,
          }}>
          <div
            style={{
              minHeight: 0,
              overflow: "hidden",
            }}>
            {nodeUri ? (
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <h2>{nodeData?.metadata.split("#")[1]}</h2>
                <FundamentalNodeButton
                  metadata={nodeData?.metadata || ""}
                  setMessage={setMessage}
                  onUpdated={() => refreshStepHierarchy(setTree, setMessage)}
                />
              </div>
            ) : (
              <p>Select a node to see details.</p>
            )}
          </div>
          <div
            style={{
              marginTop: 10,
              minHeight: 0,
              border: "1px solid var(--grey-2)",
              borderRadius: 5,
              backgroundColor: "var(--background-100)",
              padding: "8px",
            }}>
            <GLTFViewer uri={nodeUri} hoverUri={hoveredUri} />
          </div>
        </div>
      </div>
    </div>
  );
}
