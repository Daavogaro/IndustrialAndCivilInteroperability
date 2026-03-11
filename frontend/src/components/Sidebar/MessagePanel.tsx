export type StatusString = "info" | "error" | "success" | "uploaded" | "wip";

export function MessagePanel({
  message,
}: {
  message: { status: StatusString; text: string } | null;
}) {
  if (!message) return null;
  //   console.log("Rendering MessagePanel with message:", message);

  return (
    <div id="message-panel" style={{ position: "absolute", bottom: 10 }}>
      {message.status === "uploaded" ? (
        <div style={{ display: "flex", alignItems: "center", gap: "5px" }}>
          <span className="material-icons-round" style={{ color: "lightblue" }}>
            cloud_done
          </span>
          <p style={{ color: "lightblue" }}>{message.text}</p>
        </div>
      ) : message.status === "wip" ? (
        <div style={{ display: "flex", alignItems: "center", gap: "5px" }}>
          <span className="material-icons-round" style={{ color: "orange" }}>
            hourglass_bottom
          </span>
          <p style={{ color: "orange" }}>{message.text}</p>
        </div>
      ) : message.status === "success" ? (
        <div style={{ display: "flex", alignItems: "center", gap: "5px" }}>
          <span className="material-icons-round" style={{ color: "green" }}>
            check_circle
          </span>
          <p style={{ color: "green" }}>{message.text}</p>
        </div>
      ) : message.status === "error" ? (
        <div style={{ display: "flex", alignItems: "center", gap: "5px" }}>
          <span className="material-icons-round" style={{ color: "red" }}>
            error
          </span>
          <p style={{ color: "red" }}>{message.text}</p>
        </div>
      ) : message.status === "info" ? (
        <div style={{ display: "flex", alignItems: "center", gap: "5px" }}>
          <span className="material-icons-round" style={{ color: "grey" }}>
            info_outline
          </span>
          <p style={{ color: "grey" }}>{message.text}</p>
        </div>
      ) : null}
    </div>
  );
}
