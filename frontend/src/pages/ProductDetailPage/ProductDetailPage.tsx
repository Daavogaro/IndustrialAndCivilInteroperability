import { useParams } from "react-router-dom";
import { Topbar } from "../../components/Topbar";

export function ProductDetailPage() {
  const { label } = useParams<{ label: string }>();

  return (
    <div>
      <Topbar title={label ?? "Product"} />
      <div style={{ padding: 16 }}>
        <p>Product detail coming soon.</p>
      </div>
    </div>
  );
}
