import { Route, Routes } from "react-router-dom";
import { Sidebar } from "./components/Sidebar/Sidebar";
import { STEPPage } from "./pages/STEPPage/STEPPage";
import { useEffect, useState } from "react";
import { StatusString } from "./components/Sidebar/MessagePanel";
import { IFCHierarchyPage } from "./pages/IFCPage/IFCHierarchyPage";
import { TreeNode } from "./pages/STEPPage/Hierarchy/buildTree";

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
      </Routes>
    </div>
  );
}

export default App;
