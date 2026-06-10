import { Route, Routes } from "react-router-dom";
import { Sidebar } from "./components/Sidebar/Sidebar";
import { STEPPage } from "./pages/STEPPage/STEPPage";
import { useEffect, useState } from "react";
import { StatusString } from "./components/Sidebar/MessagePanel";
import { IFCHierarchyPage } from "./pages/IFCPage/IFCHierarchyPage";
import { TreeNode } from "./pages/STEPPage/Hierarchy/buildTree";
import { UpdateFilesPage } from "./pages/UpdateFilesPage/UpdateFilesPage";
import { InventoryProductPage } from "./pages/InventoryProductPage/InventoryProductPage";
import { ProductDetailPage } from "./pages/ProductDetailPage/ProductDetailPage";

function App() {
  const [message, setMessage] = useState<{
    status: StatusString;
    text: string;
    progress?: number;
  } | null>(null);
  const [nodeUri, setNodeUri] = useState<string | null>(null);

  const [tree, setTree] = useState<TreeNode[]>([]);

  useEffect(() => {
    if (!message) return;
    if (message.status === "wip") return; // keep alive until next message replaces it

    const timer = setTimeout(() => {
      setMessage(null);
    }, 5000);

    return () => clearTimeout(timer);
  }, [message]);
  return (
    <div id="app">
      <Sidebar message={message} />
      <main style={{ minHeight: 0, overflow: "hidden" }}>
        <Routes>
          <Route
            path="/"
            element={
              <STEPPage
                setMessage={setMessage}
                tree={tree}
                setTree={setTree}
                nodeUri={nodeUri}
                setNodeUri={setNodeUri}
              />
            }
          />
          <Route
            path="/IFCHierarchy"
            element={
              <IFCHierarchyPage
                setMessage={setMessage}
                tree={tree}
                setTree={setTree}
                nodeUri={nodeUri}
                setNodeUri={setNodeUri}
              />
            }
          />
          <Route path="/FileUpdate" element={<UpdateFilesPage setMessage={setMessage} tree={tree}/>} />
          <Route path="/ProductInventory" element={<InventoryProductPage />} />
          <Route path="/product/:label" element={<ProductDetailPage setMessage={setMessage} />} />
        </Routes>
      </main>
    </div>
  );
}

export default App;
