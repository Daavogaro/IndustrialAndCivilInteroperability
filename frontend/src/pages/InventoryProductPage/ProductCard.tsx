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
  obsolete,
  lastEditor,
  lastEditDate,
}: ProductCardProps) {
  const incomplete = ifcClass === null;
  const [hovered, setHovered] = useState(false);

  // Obsolete (yellow) takes visual precedence over incomplete (red).
  const statusStyle: React.CSSProperties = obsolete
    ? { backgroundColor: "#f1c40f", color: "#1a1a1a" }
    : incomplete
    ? { backgroundColor: "#c0392b", color: "white" }
    : {};

  const cardStyle: React.CSSProperties = {
    padding: 16,
    borderRadius: 10,
    display: "block",
    cursor: "pointer",
    transition: "transform 150ms ease, box-shadow 150ms ease, filter 150ms ease",
    transform: hovered ? "translateY(-3px)" : "translateY(0)",
    boxShadow: hovered ? "0 6px 18px rgba(0,0,0,0.4)" : "0 2px 4px rgba(0,0,0,0.2)",
    filter: hovered ? "brightness(1.12)" : "brightness(1)",
    ...statusStyle,
  };

  const titleColor = obsolete ? "#1a1a1a" : "white";
  const subColor = obsolete ? "#1a1a1a" : "var(--grey-6)";

  return (
    <Link
      to={`/product/${encodeURIComponent(label)}`}
      style={{ textDecoration: "none" }}>
      <div
        className={obsolete || incomplete ? undefined : "ifc-card"}
        style={cardStyle}
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
      >
        {obsolete && (
          <p
            style={{
              fontWeight: "bold",
              fontSize: "var(--font-sm)",
              marginBottom: 4,
              color: "#1a1a1a",
            }}>
            ⚠ Obsolete — needs review
          </p>
        )}
        <p
          style={{
            fontWeight: "bold",
            fontSize: "var(--font-xl)",
            marginBottom: 6,
            color: titleColor,
          }}>
          {label}
        </p>

        <span
          style={{
            display: "inline-block",
            backgroundColor: obsolete
              ? "rgba(0,0,0,0.15)"
              : incomplete
              ? "rgba(0,0,0,0.2)"
              : "var(--background-200)",
            color: obsolete ? "#1a1a1a" : incomplete ? "white" : "var(--grey-6)",
            borderRadius: 4,
            padding: "2px 6px",
            fontSize: "var(--font-sm)",
            marginBottom: 8,
          }}>
          {cadType}
        </span>

        <p style={{ marginBottom: 4, color: subColor }}>
          <strong>Instances:</strong> {count}
        </p>
        <p style={{ marginBottom: 4, color: subColor }}>
          <strong>IFC Class:</strong> {ifcClass ?? "—"}
        </p>
        <p
          style={{
            marginBottom: 4,
            color: subColor,
            fontSize: "var(--font-sm)",
            opacity: 0.85,
          }}>
          <strong>Edited by:</strong> {lastEditor}
        </p>
        <p
          style={{
            fontSize: "var(--font-sm)",
            opacity: 0.85,
            color: subColor,
          }}>
          <strong>Last edit:</strong> {formatDate(lastEditDate)}
        </p>
      </div>
    </Link>
  );
}
