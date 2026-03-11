import React, { useEffect, useState } from "react";
import { TreeNode } from "../../STEPPage/Hierarchy/buildTree";
import { StatusString } from "../../../components/Sidebar/MessagePanel";
import { DownloadIFCButton } from "./DownloadIFCButton";

type IFCNodeDetailsProps = {
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

export function IFCNodeDetails({
  uri,
  tree,
  setNodeUri,
  setMessage,
}: IFCNodeDetailsProps) {
  const [treeNodeData, setTreeNodeData] = useState<TreeNode | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const graphName = "http://localhost:8890/Elettra2/";

  const onIFCPropertiesFormSubmit = async (e: React.FormEvent) => {
    const form = document.getElementById(
      "ifc-properties-form",
    ) as HTMLFormElement;
    if (!form) return;
    e.preventDefault();
    const formData = new FormData(form);
    const ifcClass = formData.get("ifcClass") as string;
    const predefinedType = formData.get("predefinedType") as string;
    const userdefinedType = formData.get("userdefinedTypeInput") as string;
    if (ifcClass === "None") {
      setMessage({ status: "error", text: "Please select an IFC Class" });
      return;
    }

    // TODO: aggiungere logiche per editing esistenti e non solo per aggiungere nuovi nodi
    const res = await fetch("/api/add-ifc-properties", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        graph: graphName,
        metadata: treeNodeData?.metadata,
        ifc_class: ifcClass,
        predefined_type: predefinedType,
        userdefined_type: userdefinedType,
      }),
    });

    const data = await res.json();
    setMessage({ status: "success", text: data.text });
    const cancelButton = document.getElementById("cancel-button");
    if (!(cancelButton && cancelButton instanceof HTMLElement)) {
      return;
    }

    cancelButton.click();
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
        <DownloadIFCButton node={treeNodeData} setMessage={setMessage} />
      </div>
      <form
        id="ifc-properties-form"
        onSubmit={(e) => onIFCPropertiesFormSubmit(e)}
        style={{
          border: "1px solid var(--grey-4)",
          padding: 10,
          borderRadius: 10,
        }}>
        <h4 style={{ paddingBottom: 10 }}>Basic properties</h4>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr 1fr",
            gap: 10,
          }}>
          <div className="ifc-card">
            <h5 style={{ paddingBottom: 10 }}>IFC Class</h5>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <img src="./IFC-logo.png" style={{ height: 30, width: 30 }} />
              <select name="ifcClass" id="ifcClass" style={{ height: 23 }}>
                <option value="None">None</option>
                <option value="IfcElementAssembly">IfcElementAssembly</option>
                <option value="IfcWall">IfcWall</option>
                <option value="IfcSlab">IfcSlab</option>
              </select>
            </div>
          </div>
          <div className="ifc-card">
            <h5 style={{ paddingBottom: 10 }}>Predefined Type</h5>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <span className="material-icons-round" style={{ fontSize: 28 }}>
                local_offer
              </span>
              <select
                name="predefinedType"
                id="predefinedType"
                style={{ height: 23 }}>
                <option value="NOTDEFINED">NOTDEFINED</option>
                <option value="USERDEFINED">USERDEFINED</option>
              </select>
            </div>
          </div>
          <div className="ifc-card">
            <h5 style={{ paddingBottom: 10 }}>Userdefined Type</h5>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <span className="material-icons-round" style={{ fontSize: 28 }}>
                notes
              </span>
              <input
                id="userdefinedTypeInput"
                name="userdefinedTypeInput"
                type="text"
                placeholder="Only for USERDEFINED"
                style={{ height: 19 }}
              />
            </div>
          </div>
        </div>
        <div
          style={{
            display: "flex",
            columnGap: 10,
            justifyContent: "flex-end",
            marginTop: 10,
          }}>
          <button
            id="cancel-button"
            style={{ backgroundColor: "grey" }}
            type="reset"
            onClick={() => {}}>
            <span className="material-icons-round">cancel</span>
            Cancel
          </button>
          <button
            style={{ backgroundColor: "rgb(18, 145, 18)" }}
            type="submit"
            onClick={() => {}}>
            <span className="material-icons-round">check</span>
            Apply
          </button>
        </div>
      </form>
    </div>
  );
}
