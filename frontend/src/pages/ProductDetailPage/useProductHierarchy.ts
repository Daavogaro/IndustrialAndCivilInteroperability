import { useCallback, useEffect, useState } from "react";
import { buildTree, TreeNode } from "../STEPPage/Hierarchy/buildTree";

type UseProductHierarchy = {
  rootUri: string | null;
  tree: TreeNode[];
  setTree: React.Dispatch<React.SetStateAction<TreeNode[]>>;
  loading: boolean;
  error: string | null;
  refresh: () => void;
  obsolete: boolean;
  obsoleteFiles: string[];
  addedEntities: string[];
  removedEntities: string[];
};

export function useProductHierarchy(
  label: string,
  graphUri: string | null | undefined,
): UseProductHierarchy {
  const [rootUri, setRootUri] = useState<string | null>(null);
  const [tree, setTree] = useState<TreeNode[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);
  const [obsolete, setObsolete] = useState(false);
  const [obsoleteFiles, setObsoleteFiles] = useState<string[]>([]);
  const [addedEntities, setAddedEntities] = useState<string[]>([]);
  const [removedEntities, setRemovedEntities] = useState<string[]>([]);

  const refresh = useCallback(() => setTick((t) => t + 1), []);

  useEffect(() => {
    if (!label || !graphUri) return;
    let cancelled = false;

    const fetchHierarchy = async () => {
      setLoading(true);
      setError(null);
      try {
        const url = `/api/product-hierarchy/${encodeURIComponent(label)}?graph=${encodeURIComponent(graphUri)}`;
        const res = await fetch(url);
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
        setObsolete(data.obsolete ?? false);
        setObsoleteFiles(data.obsoleteFiles ?? []);
        setAddedEntities(data.addedEntities ?? []);
        setRemovedEntities(data.removedEntities ?? []);
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
  }, [label, graphUri, tick]);

  return {
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
  };
}
