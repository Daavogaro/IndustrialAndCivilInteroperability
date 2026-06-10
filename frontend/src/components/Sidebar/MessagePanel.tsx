export type StatusString = "info" | "error" | "success" | "uploaded" | "wip";

export function MessagePanel({
  message,
}: {
  message: { status: StatusString; text: string; progress?: number } | null;
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
        <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "5px" }}>
            <span className="material-icons-round" style={{ color: "orange" }}>
              hourglass_bottom
            </span>
            <p style={{ color: "orange" }}>{message.text}</p>
          </div>
          {message.progress !== undefined && (
            <div
              style={{
                width: "100%",
                height: "6px",
                backgroundColor: "rgba(255,165,0,0.25)",
                borderRadius: "3px",
                overflow: "hidden",
              }}
            >
              <div
                style={{
                  width: `${message.progress}%`,
                  height: "100%",
                  backgroundColor: "orange",
                  borderRadius: "3px",
                  transition: "width 0.3s ease",
                }}
              />
            </div>
          )}
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
