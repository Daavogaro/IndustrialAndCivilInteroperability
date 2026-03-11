import { Topbar } from "../../components/Topbar";
import { TreeNode } from "./Hierarchy/buildTree";
import { TreeList } from "./Hierarchy/TreeList";
import { AddChildModal } from "./AddChildModal";
import { HierarchyButtons } from "./Hierarchy/HierarchyButtons/HierarchyButtons";
import { UploadSTEPModal } from "./UploadSTEPModal";
import { StatusString } from "../../components/Sidebar/MessagePanel";
import { NodeDetails } from "./NodeDetails/NodeDetails";

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

  const handleSelectNode = async (uri: string) => {
    setNodeUri(uri);
  };

  return (
    <div>
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
          margin: "0px 10px 10px 10px",
          gap: "10px",
        }}>
        <div>
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
          {tree.length > 0 ? (
            <TreeList tree={tree} handleSelectNode={handleSelectNode} />
          ) : (
            <p>No hierarchy built yet.</p>
          )}
        </div>

        <div style={{}}>
          <h2>Node Details</h2>
          {nodeUri ? (
            <NodeDetails
              uri={nodeUri}
              tree={tree}
              setNodeUri={setNodeUri}
              setMessage={setMessage}
            />
          ) : (
            <p>Select a node to see details.</p>
          )}
        </div>
      </div>
    </div>
  );
}
