import { useCallback, useEffect, useState } from "react";
import { buildTree, TreeNode } from "../STEPPage/Hierarchy/buildTree";

type UseProductHierarchy = {
  rootUri: string | null;
  tree: TreeNode[];
  setTree: React.Dispatch<React.SetStateAction<TreeNode[]>>;
  loading: boolean;
  error: string | null;
  refresh: () => void;
};

export function useProductHierarchy(label: string): UseProductHierarchy {
  const [rootUri, setRootUri] = useState<string | null>(null);
  const [tree, setTree] = useState<TreeNode[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  const refresh = useCallback(() => setTick((t) => t + 1), []);

  useEffect(() => {
    if (!label) return;
    let cancelled = false;

    const fetchHierarchy = async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await fetch(`/api/product-hierarchy/${encodeURIComponent(label)}`);
        if (!res.ok) {
          throw new Error(`${res.status} ${res.statusText}`);
        }
        const data = await res.json();

        if (cancelled) return;

        const built = buildTree(
          data.edges,
          data.roots,
          data.ifcData,
          data.ifcPsetData,
        );

        setRootUri(data.rootUri);
        setTree(built);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Unknown error");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    fetchHierarchy();
    return () => {
      cancelled = true;
    };
  }, [label, tick]);

  return { rootUri, tree, setTree, loading, error, refresh };
}
