import { useState } from "react";
import { StatusString } from "../../components/Sidebar/MessagePanel";
import { Topbar } from "../../components/Topbar";
import { TreeNode } from "../STEPPage/Hierarchy/buildTree";
import { UpdateHierarchyButton } from "../STEPPage/Hierarchy/HierarchyButtons/buttons/UpdateHierarchyButton";
import { buildFundamentalTree } from "./Hierarchy/builtIFCTree";
import { IfcTreeList } from "./Hierarchy/IFCTreeList";
import { IFCNodeDetails } from "./NodeDetails/IFCNodeDetails";
import { useProject } from "../../context/ProjectContext";

type IFCHierarchyPageProps = {
  setTree: (tree: TreeNode[]) => void;
  tree: TreeNode[];
  setNodeUri: (uri: string | null) => void;
  nodeUri: string | null;
  setMessage: (message: { status: StatusString; text: string }) => void;
};

const getNodeName = (uri: string) => uri.split("#")[1] ?? uri;
const getBaseName = (name: string) => name.replace(/\.\d+$/, "");

const collectUrisByBaseName = (nodes: TreeNode[], baseName: string): string[] => {
  const result: string[] = [];
  const visit = (ns: TreeNode[]) => {
    for (const node of ns) {
      if (getBaseName(getNodeName(node.id)) === baseName) {
        result.push(node.id);
      }
      visit(node.children);
    }
  };
  visit(nodes);
  return result;
};

export function IFCHierarchyPage({
  setMessage,
  setTree,
  tree,
}: IFCHierarchyPageProps) {
  const { activeProject } = useProject();
  const [selectedUris, setSelectedUris] = useState<string[]>([]);

  const fundamentalTree = buildFundamentalTree(tree);

  const handleToggleSelect = (uri: string) => {
    const baseName = getBaseName(getNodeName(uri));
    const relatedUris = collectUrisByBaseName(fundamentalTree, baseName);

    setSelectedUris((prev) => {
      if (prev.includes(uri)) {
        return prev.filter((u) => !relatedUris.includes(u));
      }
      const toAdd = relatedUris.filter((u) => !prev.includes(u));
      return [...prev, ...toAdd];
    });
  };

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
          <strong>Project:</strong>{" "}
          {activeProject ? `${activeProject.name} — ${activeProject.graphUri}` : "No project selected"}
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
                selectedUris={selectedUris}
                onToggleSelect={handleToggleSelect}
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
            {selectedUris.length > 0 ? (
              <IFCNodeDetails
                uris={selectedUris}
                tree={tree}
                setTree={setTree}
                setMessage={setMessage}
                onClearSelection={() => setSelectedUris([])}
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
