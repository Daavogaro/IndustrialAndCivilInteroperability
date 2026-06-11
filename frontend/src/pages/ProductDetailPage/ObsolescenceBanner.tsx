type ObsolescenceBannerProps = {
  obsoleteFiles: string[];
  addedEntities: string[];
  removedEntities: string[];
  busy: boolean;
  onMarkReviewed: () => void;
};

export function ObsolescenceBanner({
  obsoleteFiles,
  addedEntities,
  removedEntities,
  busy,
  onMarkReviewed,
}: ObsolescenceBannerProps) {
  return (
    <div
      style={{
        backgroundColor: "#f1c40f",
        color: "#1a1a1a",
        padding: "10px 14px",
        borderRadius: 8,
        margin: "0 10px 4px",
        display: "flex",
        flexDirection: "column",
        gap: 6,
      }}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 10,
        }}>
        <strong style={{ fontSize: "var(--font-lg)" }}>
          ⚠ This product is obsolete
        </strong>
        <button
          onClick={onMarkReviewed}
          disabled={busy}
          style={{
            backgroundColor: "#1a1a1a",
            color: "#f1c40f",
            border: "none",
            borderRadius: 6,
            padding: "6px 12px",
            cursor: busy ? "default" : "pointer",
            opacity: busy ? 0.6 : 1,
            display: "inline-flex",
            alignItems: "center",
            gap: 4,
          }}>
          <span className="material-icons-round" style={{ fontSize: 18 }}>
            done
          </span>
          {busy ? "Reviewing…" : "Mark as reviewed"}
        </button>
      </div>

      {obsoleteFiles.length > 0 && (
        <div>
          <strong>Files to update:</strong> {obsoleteFiles.join(", ")}
        </div>
      )}
      {addedEntities.length > 0 && (
        <div>
          <strong>Added:</strong> {addedEntities.join(", ")}
        </div>
      )}
      {removedEntities.length > 0 && (
        <div>
          <strong>Removed:</strong> {removedEntities.join(", ")}
        </div>
      )}
    </div>
  );
}
