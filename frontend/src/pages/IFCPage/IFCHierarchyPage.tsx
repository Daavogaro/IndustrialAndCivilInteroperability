import { StatusString } from "../../components/Sidebar/MessagePanel";
import { Topbar } from "../../components/Topbar";
import { TreeNode } from "../STEPPage/Hierarchy/buildTree";
import { UpdateHierarchyButton } from "../STEPPage/Hierarchy/HierarchyButtons/buttons/UpdateHierarchyButton";
import { buildFundamentalTree } from "./Hierarchy/builtIFCTree";
import { IfcTreeList } from "./Hierarchy/IFCTreeList";
import { IFCNodeDetails } from "./NodeDetails/IFCNodeDetails";

type IFCHierarchyPageProps = {
  setTree: (tree: TreeNode[]) => void;
  tree: TreeNode[];
  setNodeUri: (uri: string | null) => void;
  nodeUri: string | null;
  setMessage: (message: { status: StatusString; text: string }) => void;
};

export function IFCHierarchyPage({
  setMessage: setMessage,
  setTree,
  tree,
  setNodeUri,
  nodeUri,
}: IFCHierarchyPageProps) {
  const graphName = "http://localhost:8890/Elettra2/";

  const handleSelectNode = async (uri: string) => {
    setNodeUri(uri);
  };
  const fundamentalTree = buildFundamentalTree(tree);

  return (
    <div
      style={{
        display: "grid",
        gridTemplateRows: "auto auto 1fr",
        height: "100vh",
        overflow: "hidden",
      }}>
      <Topbar title="IFC Hierarchy" />

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
        <div style={{ display: "grid", gridTemplateRows: "auto 1fr", minHeight: 0 }}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 10,
              marginBottom: 10,
            }}>
            <h2>Hierarchy</h2>
            <UpdateHierarchyButton setTree={setTree} setMessage={setMessage} />
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
            {fundamentalTree.length > 0 ? (
              <IfcTreeList
                tree={fundamentalTree}
                handleSelectNode={handleSelectNode}
              />
            ) : (
              <p>No hierarchy built yet.</p>
            )}
          </div>
        </div>

        <div style={{}}>
          <h2>Node Details</h2>
          <div
            style={{
              minHeight: 0,
              overflowY: "auto",
            }}
            className="panel-scroll">
            {nodeUri ? (
              <IFCNodeDetails
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
    </div>
  );
}
