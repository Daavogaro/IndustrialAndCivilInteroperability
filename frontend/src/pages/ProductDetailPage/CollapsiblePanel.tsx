import React from "react";

type CollapsiblePanelProps = {
  title: string;
  collapsed: boolean;
  onToggle: () => void;
  children: React.ReactNode;
};

export function CollapsiblePanel({
  title,
  collapsed,
  onToggle,
  children,
}: CollapsiblePanelProps) {
  return (
    <div
      style={{
        flex: collapsed ? "0 0 36px" : "1 1 0%",
        minHeight: 0,
        overflow: "hidden",
        display: "flex",
        flexDirection: "column",
        borderBottom: "1px solid var(--grey-2)",
      }}
    >
      {/* Title bar */}
      <div
        onClick={onToggle}
        style={{
          flex: "0 0 36px",
          display: "flex",
          alignItems: "center",
          gap: 8,
          padding: "0 12px",
          cursor: "pointer",
          backgroundColor: "var(--background-200)",
          borderBottom: "1px solid var(--grey-2)",
          userSelect: "none",
        }}
      >
        <span
          className="material-icons-round"
          style={{ fontSize: 16, color: "var(--grey-6)" }}
        >
          {collapsed ? "chevron_right" : "expand_more"}
        </span>
        <span style={{ fontWeight: 600, fontSize: "var(--font-base)" }}>
          {title}
        </span>
      </div>

      {/* Body — never display:none so Three.js canvas stays in layout */}
      <div
        style={{
          flex: collapsed ? "0 0 0px" : "1 1 0%",
          overflow: "hidden",
          minHeight: 0,
        }}
      >
        {children}
      </div>
    </div>
  );
}
