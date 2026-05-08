import { Route, Routes } from "react-router-dom";
import { Sidebar } from "./components/Sidebar/Sidebar";
import { STEPPage } from "./pages/STEPPage/STEPPage";
import { useEffect, useState } from "react";
import { StatusString } from "./components/Sidebar/MessagePanel";
import { IFCHierarchyPage } from "./pages/IFCPage/IFCHierarchyPage";
import { TreeNode } from "./pages/STEPPage/Hierarchy/buildTree";
import { IFCViewerPage } from "./pages/IFCViewerPage/IFCViewerPage";
import { UpdateFilesPage } from "./pages/UpdateFilesPage/UpdateFilesPage";
import { InventoryProductPage } from "./pages/InventoryProductPage/InventoryProductPage";

function App() {
  const [message, setMessage] = useState<{
    status: StatusString;
    text: string;
  } | null>(null);
  const [nodeUri, setNodeUri] = useState<string | null>(null);

  const [tree, setTree] = useState<TreeNode[]>([]);

  useEffect(() => {
    if (!message) return;

    const timer = setTimeout(() => {
      setMessage(null);
    }, 10000);

    return () => clearTimeout(timer); // cleanup
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
          <Route path="/IFCViewer" element={<IFCViewerPage />} />
          <Route path="/FileUpdate" element={<UpdateFilesPage setMessage={setMessage} />} />
          <Route path="/ProductInventory" element={<InventoryProductPage />} />
        </Routes>
      </main>
    </div>
  );
}

export default App;
