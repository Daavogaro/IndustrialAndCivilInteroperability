import { useState } from "react";
import { apiWebSocketUrl } from "../../utils/apiWebSocket";
import { toogleModal } from "../../utils/htmlFunctions";
import { StatusString } from "../../components/Sidebar/MessagePanel";
import { useProject } from "../../context/ProjectContext";

type UploadSTEPModalProps = {
  uri: string | null;

  setMessage: (message: { status: StatusString; text: string; progress?: number }) => void;
};

export function UploadSTEPModal({ uri, setMessage }: UploadSTEPModalProps) {
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
  const handleUpload = async (uri: string | null) => {
    if (!file) return;

    setUploading(true);
    setMessage({ status: "info", text: "Uploading file..." });

    try {
      const formData = new FormData();
      formData.append("file", file);
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
      const websocket = new WebSocket(apiWebSocketUrl("/api/ws/convert"));
      websocket.onopen = () => {
        setMessage({ status: "info", text: "WebSocket connected" });
        websocket.send(
          JSON.stringify({
            filename: uploadedFilename,
            graph_name: graphName,
            project_id: activeProject?.id ?? null,
            parent_uri: uri,
            ownerFirstName: ownerFirstName,
            ownerLastName: ownerLastName,
            time: time,
          }),
        );
      };

      websocket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        setMessage({ status: data.status, text: data.text, progress: data.progress });
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
    toogleModal("upload-step-modal");
  };

  return (
    <dialog
      id="upload-step-modal"
      style={{
        backgroundColor: "var(--background-100)",
        padding: 10,
        borderRadius: 10,
      }}>
      <div>
        <h3 style={{ color: "white", paddingBottom: 10 }}>
          Upload a STEP file to add its hierarchy to the graph:
        </h3>
        {uri ? (
          <p style={{ color: "white", marginBottom: 10 }}>
            Parent node: {uri.split("#")[1]}
          </p>
        ) : (
          <p style={{ color: "white", marginBottom: 10 }}>
            No parent node selected, creation of a new root node
          </p>
        )}
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
              toogleModal("upload-step-modal");
              setFile(null);
            }}>
            <span className="material-icons-round">cancel</span>
            Cancel
          </button>
          <button
            style={{ backgroundColor: "rgb(18, 145, 18)" }}
            disabled={!file || uploading}
            onClick={() => {
              handleUpload(uri);
            }}>
            <span className="material-icons-round">check</span>
            Upload
          </button>
        </div>
      </div>
    </dialog>
  );
}
