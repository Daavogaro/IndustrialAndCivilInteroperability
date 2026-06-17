import { StatusString } from "../../../components/Sidebar/MessagePanel";
import { useProject } from "../../../context/ProjectContext";

type FundamentalNodeButtonProps = {
  metadata: string;
  isFundamental: boolean;
  hasIfcData?: boolean;
  setMessage: (message: { status: StatusString; text: string }) => void;
  onUpdated: () => Promise<void>;
};

export function FundamentalNodeButton({
  metadata: metadata,
  isFundamental,
  hasIfcData = false,
  setMessage,
  onUpdated,
}: FundamentalNodeButtonProps) {
  const { activeProject } = useProject();
  const graphName = activeProject?.graphUri ?? "";

  const addFundamentalNode = async (graph: string, metadata: string) => {
    const res = await fetch("/api/add-fundamental-node", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ graph, metadata }),
    });
    await fetch("/api/update-deletion", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        metadata: metadata,
        toBeDeleted: false,
        graph: graph,
      }),
    });

    const data = await res.json();
    setMessage({ status: data.status, text: data.text });
    await onUpdated();
  };

  const removeFundamentalNode = async (graph: string, metadata: string) => {
    let removeIfc = false;
    if (hasIfcData) {
      const confirmed = window.confirm(
        "This node has IFC data. Undoing the fundamental node will also remove " +
          "its IFC data. Do you want to continue?",
      );
      if (!confirmed) {
        return;
      }
      removeIfc = true;
    }

    const res = await fetch("/api/remove-fundamental-node", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ graph, metadata, remove_ifc: removeIfc }),
    });

    const data = await res.json();
    setMessage({ status: data.status, text: data.text });
    await onUpdated();
  };

  const toggleFundamentalNode = () => {
    if (isFundamental) {
      return removeFundamentalNode(graphName, metadata);
    }
    return addFundamentalNode(graphName, metadata);
  };

  return (
    <div
      className="generalButton"
      style={{
        padding: 5,
        border: "1px solid var(--grey-2)",
        borderRadius: 10,
        cursor: "pointer",
      }}
      title={isFundamental ? "Undo fundamental node" : "Set as fundamental node"}
      onClick={toggleFundamentalNode}>
      {isFundamental ? (
        <span className="material-icons-round generalButton" style={{ height: 30, lineHeight: "30px", display: "block" }}>
          undo
        </span>
      ) : (
        <img src="../IFC-logo.png" style={{ height: 30 }} />
      )}
    </div>
  );
}
