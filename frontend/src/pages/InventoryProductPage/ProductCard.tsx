import { useState } from "react";
import { Link } from "react-router-dom";
import { InventoryItem } from "./useProductInventory";

function formatDate(iso: string): string {
  try {
    const d = new Date(iso);
    if (isNaN(d.getTime())) return iso;
    const dd = String(d.getDate()).padStart(2, "0");
    const mm = String(d.getMonth() + 1).padStart(2, "0");
    const yyyy = d.getFullYear();
    const hh = String(d.getHours()).padStart(2, "0");
    const min = String(d.getMinutes()).padStart(2, "0");
    return `${dd}/${mm}/${yyyy} ${hh}:${min}`;
  } catch {
    return iso;
  }
}

type ProductCardProps = InventoryItem;

export function ProductCard({
  label,
  count,
  cadType,
  ifcClass,
  hasAddedEntities,
  hasRemovedEntities,
  lastEditor,
  lastEditDate,
}: ProductCardProps) {
  const incomplete = ifcClass === null;
  const hasChanges = hasAddedEntities || hasRemovedEntities;
  const changed = hasChanges && !incomplete;
  const [hovered, setHovered] = useState(false);

  const changeChipText = hasAddedEntities && hasRemovedEntities
    ? "Structure changed: entities added & removed"
    : hasAddedEntities
      ? "Structure changed: entities added"
      : "Structure changed: entities removed";

  const cardStyle: React.CSSProperties = {
    padding: 16,
    borderRadius: 10,
    display: "block",
    cursor: "pointer",
    transition: "transform 150ms ease, box-shadow 150ms ease, filter 150ms ease",
    transform: hovered ? "translateY(-3px)" : "translateY(0)",
    boxShadow: hovered ? "0 6px 18px rgba(0,0,0,0.4)" : "0 2px 4px rgba(0,0,0,0.2)",
    filter: hovered ? "brightness(1.12)" : "brightness(1)",
    ...(incomplete
      ? { backgroundColor: "#c0392b", color: "white" }
      : changed
        ? { backgroundColor: "#c8860a", color: "white" }
        : {}),
  };

  return (
    <Link
      to={`/product/${encodeURIComponent(label)}`}
      style={{ textDecoration: "none" }}>
      <div
        className={incomplete || changed ? undefined : "ifc-card"}
        style={cardStyle}
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
      >
        <p
          style={{
            fontWeight: "bold",
            fontSize: "var(--font-xl)",
            marginBottom: 6,
            color: "white",
          }}>
          {label}
        </p>

        <span
          style={{
            display: "inline-block",
            backgroundColor: incomplete
              ? "rgba(0,0,0,0.2)"
              : "var(--background-200)",
            color: incomplete ? "white" : "var(--grey-6)",
            borderRadius: 4,
            padding: "2px 6px",
            fontSize: "var(--font-sm)",
            marginBottom: 8,
          }}>
          {cadType}
        </span>

        {changed && (
          <span
            style={{
              display: "block",
              backgroundColor: "rgba(0,0,0,0.25)",
              color: "white",
              borderRadius: 4,
              padding: "2px 6px",
              fontSize: "var(--font-sm)",
              marginBottom: 8,
            }}>
            ⚠ {changeChipText}
          </span>
        )}

        <p style={{ marginBottom: 4, color: "var(--grey-6)" }}>
          <strong>Instances:</strong> {count}
        </p>
        <p style={{ marginBottom: 4, color: "var(--grey-6)" }}>
          <strong>IFC Class:</strong> {ifcClass ?? "—"}
        </p>
        <p
          style={{
            marginBottom: 4,
            color: "var(--grey-6)",
            fontSize: "var(--font-sm)",
            opacity: 0.85,
          }}>
          <strong>Edited by:</strong> {lastEditor}
        </p>
        <p
          style={{
            fontSize: "var(--font-sm)",
            opacity: 0.85,
            color: "var(--grey-6)",
          }}>
          <strong>Last edit:</strong> {formatDate(lastEditDate)}
        </p>
      </div>
    </Link>
  );
}
