import { useState } from "react";
import { apiWebSocketUrl } from "../../utils/apiWebSocket";
import { toogleModal } from "../../utils/htmlFunctions";
import { StatusString } from "../../components/Sidebar/MessagePanel";
import { TreeNode } from "../STEPPage/Hierarchy/buildTree";
import { useProject } from "../../context/ProjectContext";

type UpdateSTEPModalProps = {
  fileName: string 
  tree: TreeNode[];

  setMessage: (message: { status: StatusString; text: string }) => void;
};

export function UpdateSTEPModal({ fileName, tree, setMessage }: UpdateSTEPModalProps) {
  const { activeProject } = useProject();
  const graphName = activeProject?.graphUri ?? "";
  const ownerFirstName = "Davide";
  const ownerLastName = "Avogaro";
  const time = new Date().toISOString();
  
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setFile(e.target.files[0]);
    }
  };

  // Step 2: upload via HTTP
  const handleUpload = async (fileName: string) => {
    if (!file) return;

    setUploading(true);
    setMessage({ status: "info", text: "Uploading file..." });

    try {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("fileName", fileName.replace(".gltf", ".stp"));
      if (activeProject?.id) formData.append("projectId", activeProject.id);

      const res = await fetch("/api/upload-step", {
        method: "POST",
        body: formData,
      });

      const uploadData = await res.json();

      if (uploadData.status !== "uploaded") {
        setMessage({ status: "error", text: uploadData.text });
        setUploading(false);
        return;
      }

      setMessage({ status: "success", text: "File uploaded successfully" });
      const uploadedFilename = uploadData.filename;

      // Step 3: apri WebSocket per conversione + gerarchia
      const websocket = new WebSocket(apiWebSocketUrl("/api/ws/update"));
      websocket.onopen = () => {
        setMessage({ status: "info", text: "WebSocket connected" });
         websocket.send(
           JSON.stringify({
             filename: uploadedFilename,
             graph_name: graphName,
             project_id: activeProject?.id ?? null,
             tree: tree,
             ownerFirstName: ownerFirstName,
             ownerLastName: ownerLastName,
             time: time,
           }),
         );
      };
// 
     websocket.onmessage = (event) => {
       const data = JSON.parse(event.data);
       setMessage({ status: data.status, text: data.text });
     };

     websocket.onclose = () => {
       setMessage({ status: "info", text: "WebSocket connection closed" });
       setUploading(false);
     };

     websocket.onerror = (err) => {
       setMessage({ status: "error", text: "WebSocket error: " + err });
       setUploading(false);
     };
    } catch (err) {
      setMessage({ status: "error", text: "Upload error: " + err });
      setUploading(false);
    }
    toogleModal("update-step-modal");
  };

  return (
    <dialog
      id="update-step-modal"
      style={{
        backgroundColor: "var(--background-100)",
        padding: 10,
        borderRadius: 10,
      }}>
      <div>
        <h3 style={{ color: "white", paddingBottom: 10 }}>
          Update a STEP file to update {fileName}
        </h3>
        <input
          type="file"
          accept=".stp"
          onChange={handleFileChange}
          style={{ color: "white", paddingBottom: 10 }}
        />

        <div
          style={{
            display: "flex",
            columnGap: 10,
            justifyContent: "flex-end",
          }}>
          <button
            id="cancel-button"
            style={{ backgroundColor: "grey" }}
            onClick={() => {
              toogleModal("update-step-modal");
              setFile(null);
            }}>
            <span className="material-icons-round">cancel</span>
            Cancel
          </button>
          <button
            style={{ backgroundColor: "rgb(18, 145, 18)" }}
            disabled={!file || uploading}
            onClick={() => {
              handleUpload(fileName);
            }}>
            <span className="material-icons-round">check</span>
            Upload
          </button>
        </div>
      </div>
    </dialog>
  );
}
