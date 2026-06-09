import { useMemo, useState } from "react";
import { Topbar } from "../../components/Topbar";
import { useProductInventory, InventoryItem } from "./useProductInventory";
import { ProductCard } from "./ProductCard";
import { StatusString } from "../../components/Sidebar/MessagePanel";

type SortKey = "name" | "lastEdit" | "status" | "author";

const SORT_LABELS: { key: SortKey; label: string }[] = [
  { key: "name", label: "Name" },
  { key: "lastEdit", label: "Last Edit" },
  { key: "status", label: "Status" },
  { key: "author", label: "Author" },
];

function sortItems(items: InventoryItem[], key: SortKey): InventoryItem[] {
  const copy = items.slice();
  switch (key) {
    case "name":
      return copy.sort((a, b) => a.label.localeCompare(b.label));
    case "lastEdit":
      return copy.sort((a, b) => b.lastEditDate.localeCompare(a.lastEditDate));
    case "status":
      return copy.sort((a, b) => {
        const aIncomplete = a.ifcClass === null ? 0 : 1;
        const bIncomplete = b.ifcClass === null ? 0 : 1;
        return aIncomplete - bIncomplete;
      });
    case "author":
      return copy.sort((a, b) => a.lastEditor.localeCompare(b.lastEditor));
  }
}



export function InventoryProductPage() {
  const { items, loading, error, refresh } = useProductInventory();
  const [search, setSearch] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("name");

  const displayItems = useMemo(() => {
    const filtered = search
      ? items.filter((item) => item.label.toLowerCase().includes(search.toLowerCase()))
      : items;
    return sortItems(filtered, sortKey);
  }, [items, search, sortKey]);

  return (
    <div style={{ display: "grid", gridTemplateRows: "auto 1fr", height: "100vh", overflow: "hidden" }}>
      <Topbar title="Product Inventory" />

      <div className="panel-scroll" style={{ padding: 10 }}>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            marginBottom: 12,
            flexWrap: "wrap",
          }}
        >
          <input
            type="text"
            placeholder="Search by name…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            style={{
              padding: "4px 8px",
              borderRadius: 4,
              border: "1px solid var(--grey-3)",
              backgroundColor: "var(--background-200)",
              color: "white",
              fontSize: "var(--font-base)",
              minWidth: 200,
            }}
          />

          <div style={{ display: "flex", gap: 4 }}>
            {SORT_LABELS.map(({ key, label }) => (
              <span
                key={key}
                className={`toogle-view${sortKey === key ? " active" : ""}`}
                style={{ padding: "4px 10px", fontSize: "var(--font-sm)", cursor: "pointer" }}
                onClick={() => setSortKey(key)}
              >
                {label}
              </span>
            ))}
          </div>
        </div>

        {loading && <p>Loading…</p>}

        {error && !loading && (
          <div>
            <p style={{ color: "#c0392b" }}>Error: {error}</p>
            <span className="generalButton" onClick={refresh} style={{ display: "inline-block", marginTop: 6 }}>
              Retry
            </span>
          </div>
        )}

        {!loading && !error && displayItems.length === 0 && (
          <p>No fundamental node components found.</p>
        )}

        {!loading && !error && displayItems.length > 0 && (
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))",
              gap: 12,
            }}
          >
            {displayItems.map((item) => (
              <ProductCard key={item.metadata} {...item} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
