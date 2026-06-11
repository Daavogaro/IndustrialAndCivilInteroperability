import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Topbar } from "../../components/Topbar";
import {
  StatusString,
  MessagePanel,
} from "../../components/Sidebar/MessagePanel";
import { NodeDetails } from "./NodeDetails/NodeDetails";
import { IFCNodeDetails } from "../IFCPage/NodeDetails/IFCNodeDetails";
import { CollapsiblePanel } from "./CollapsiblePanel";
import { ProductGLTFViewer } from "./ProductGLTFViewer";
import { useProductHierarchy } from "./useProductHierarchy";
import { ObsolescenceBanner } from "./ObsolescenceBanner";
import { useProject } from "../../context/ProjectContext";

type ProductPageProps = {
  setMessage: (message: { status: StatusString; text: string }) => void;
};
export function ProductDetailPage({ setMessage }: ProductPageProps) {
  const { label = "" } = useParams<{ label: string }>();
  const navigate = useNavigate();
  const { activeProject } = useProject();

  const {
    rootUri,
    tree,
    setTree,
    loading,
    error,
    refresh,
    obsolete,
    obsoleteFiles,
    addedEntities,
    removedEntities,
  } = useProductHierarchy(label, activeProject?.graphUri);

  const [selectedNodeUri, setSelectedNodeUri] = useState<string | null>(null);
  const [hoveredUri, setHoveredUri] = useState<string | null>(null);
  const [reviewing, setReviewing] = useState(false);

  const handleMarkReviewed = async () => {
    const metadata = tree[0]?.metadata;
    if (!metadata || !activeProject?.graphUri) return;
    setReviewing(true);
    try {
      const res = await fetch("/api/mark-reviewed", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          graph: activeProject.graphUri,
          metadata,
        }),
      });
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
      const data = await res.json();
      setMessage({ status: "success", text: data.text ?? "Marked as reviewed" });
      refresh();
    } catch (err) {
      setMessage({
        status: "error",
        text: err instanceof Error ? err.message : "Mark as reviewed failed",
      });
    } finally {
      setReviewing(false);
    }
  };

  const [viewerCollapsed, setViewerCollapsed] = useState(false);
  const [ifcCollapsed, setIfcCollapsed] = useState(false);

  // Initialise selection to the root once the hierarchy is loaded
  useEffect(() => {
    if (rootUri && !selectedNodeUri) {
      setSelectedNodeUri(rootUri);
    }
  }, [rootUri]);


  // Trigger viewer resize when its panel is expanded/collapsed
  useEffect(() => {
    window.dispatchEvent(new Event("resize"));
  }, [viewerCollapsed]);

  const handleLocalMessage = (msg: { status: StatusString; text: string }) => {
    setMessage(msg);
  };

  // --- Loading / error states ---
  if (loading) {
    return (
      <div
        style={{
          display: "grid",
          gridTemplateRows: "auto 1fr",
          height: "100vh",
          overflow: "hidden",
        }}>
        <Topbar title={label} />
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}>
          <p>Loading product hierarchy…</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div
        style={{
          display: "grid",
          gridTemplateRows: "auto 1fr",
          height: "100vh",
          overflow: "hidden",
        }}>
        <Topbar title={label} />
        <div style={{ padding: 16 }}>
          <p style={{ color: "#c0392b", marginBottom: 12 }}>Error: {error}</p>
          <span
            className="generalButton"
            onClick={refresh}
            style={{ display: "inline-block", marginRight: 8 }}>
            Retry
          </span>
          <span
            className="generalButton"
            onClick={() => navigate(-1)}
            style={{ display: "inline-block" }}>
            ← Back to Inventory
          </span>
        </div>
      </div>
    );
  }

  // --- Loaded state ---
  return (
    <div
      style={{
        display: "grid",
        gridTemplateRows: obsolete ? "auto auto auto 1fr" : "auto auto 1fr",
        height: "100vh",
        overflow: "hidden",
      }}>
      {/* Row 1: Topbar */}
      <Topbar title={label} />

      {/* Obsolescence banner (only when the product is flagged) */}
      {obsolete && (
        <ObsolescenceBanner
          obsoleteFiles={obsoleteFiles}
          addedEntities={addedEntities}
          removedEntities={removedEntities}
          busy={reviewing}
          onMarkReviewed={handleMarkReviewed}
        />
      )}

      {/* Row 2: Back navigation */}
      <div
        style={{
          padding: "6px 10px",
          display: "flex",
          alignItems: "center",
          gap: 8,
        }}>
        <span
          className="generalButton"
          onClick={() => navigate(-1)}
          style={{ display: "inline-block" }}>
          ← Back to Inventory
        </span>
        {selectedNodeUri && selectedNodeUri !== rootUri && rootUri && (
          <span
            className="generalButton"
            onClick={() => setSelectedNodeUri(rootUri)}
            style={{ display: "inline-block" }}>
            ↩ Product root
          </span>
        )}
      </div>

      {/* Row 3: Two-column body */}
      <div
        style={{
          display: "flex",
          flexDirection: "row",
          minHeight: 0,
          overflow: "hidden",
        }}>
        {/* Left column: NodeDetails (40%) */}
        <div
          style={{
            width: "40%",
            flexShrink: 0,
            display: "flex",
            flexDirection: "column",
            minHeight: 0,
            overflow: "hidden",
            borderRight: "1px solid var(--grey-2)",
            padding: 10,
          }}>
          {selectedNodeUri ? (
            <NodeDetails
              uri={selectedNodeUri}
              tree={tree}
              setTree={setTree}
              setNodeUri={setSelectedNodeUri}
              setMessage={handleLocalMessage}
              setHoveredUri={setHoveredUri}
            />
          ) : (
            <p>Loading…</p>
          )}
        </div>

        {/* Right column: two collapsible panels (flex: 1) */}
        <div
          style={{
            flex: 1,
            display: "flex",
            flexDirection: "column",
            minHeight: 0,
            overflow: "hidden",
          }}>
          {/* Top panel: 3D viewer */}
          <CollapsiblePanel
            title="Product Viewer"
            collapsed={viewerCollapsed}
            onToggle={() => setViewerCollapsed((v) => !v)}>
            <ProductGLTFViewer productLabel={label} hoveredUri={hoveredUri} rootUri={rootUri} />
          </CollapsiblePanel>

          {/* Bottom panel: IFC properties */}
          <CollapsiblePanel
            title="IFC Properties"
            collapsed={ifcCollapsed}
            onToggle={() => setIfcCollapsed((v) => !v)}>
            <div style={{ height: "100%", overflowY: "auto" }}>
              <IFCNodeDetails
                uris={selectedNodeUri ? [selectedNodeUri] : []}
                tree={tree}
                setTree={setTree}
                setMessage={handleLocalMessage}
                onClearSelection={() => setSelectedNodeUri(rootUri)}
              />
            </div>
          </CollapsiblePanel>
        </div>
      </div>
    </div>
  );
}
