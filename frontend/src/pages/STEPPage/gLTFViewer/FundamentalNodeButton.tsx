import { StatusString } from "../../../components/Sidebar/MessagePanel";

type FundamentalNodeButtonProps = {
  metadata: string;
  setMessage: (message: { status: StatusString; text: string }) => void;
  onUpdated: () => Promise<void>;
};

export function FundamentalNodeButton({
  metadata: metadata,
  setMessage,
  onUpdated,
}: FundamentalNodeButtonProps) {
  const graphName = "http://localhost:8890/Elettra2/";
  const fetchFundamentalNode = async (graph: string, metadata: string) => {
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
      }),
    });

    const data = await res.json();
    setMessage({ status: data.status, text: data.text });
    await onUpdated();
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
      onClick={() => fetchFundamentalNode(graphName, metadata)}>
      <img src="../IFC-logo.png" style={{ height: 30 }} />
    </div>
  );
}
