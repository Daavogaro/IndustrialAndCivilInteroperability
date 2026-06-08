import { useCallback, useEffect, useState } from "react";

export type InventoryItem = {
  label: string;
  metadata: string;
  count: number;
  cadType: string;
  ifcClass: string | null;
  lastEditor: string;
  lastEditDate: string;
};

type UseProductInventory = {
  items: InventoryItem[];
  loading: boolean;
  error: string | null;
  refresh: () => void;
};

export function useProductInventory(): UseProductInventory {
  const [items, setItems] = useState<InventoryItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  const refresh = useCallback(() => setTick((t) => t + 1), []);

  useEffect(() => {
    let cancelled = false;

    const fetchInventory = async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await fetch("/api/product-inventory");
        if (!res.ok) {
          throw new Error(`${res.status} ${res.statusText}`);
        }
        const data: InventoryItem[] = await res.json();
        if (!cancelled) setItems(data);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Unknown error");
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    fetchInventory();
    return () => { cancelled = true; };
  }, [tick]);

  return { items, loading, error, refresh };
}
