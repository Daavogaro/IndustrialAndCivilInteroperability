import { StatusString } from "../../../components/Sidebar/MessagePanel";
import { TreeNode } from "../../STEPPage/Hierarchy/buildTree";

type DownloadIFCButtonProps = {
  node: TreeNode;
  setMessage: (message: { status: StatusString; text: string }) => void;
};

export function DownloadIFCButton({
  node,
  setMessage,
}: DownloadIFCButtonProps) {
  const saveBlend = false;

  const handleConversion = async (node: TreeNode) => {
    setMessage({ status: "info", text: "Start converting in IFC file..." });
    console.log("Starting IFC conversion for node:", node);
    try {
      const websocket = new WebSocket(
        "ws://localhost:8000/api/ws/blender_run_scripts",
      );
      websocket.onopen = () => {
        setMessage({ status: "info", text: "WebSocket connected" });
        websocket.send(
          JSON.stringify({
            node: node,
            save_blend: saveBlend,
          }),
        );
      };

      websocket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        setMessage({ status: data.status, text: data.text });
      };

      websocket.onclose = () => {};

      websocket.onerror = () => {
        setMessage({ status: "error", text: "WebSocket connection error" });
      };
    } catch (err) {
      setMessage({ status: "error", text: "IFC conversion error: " + err });
    }
  };

  return (
    <>
      <span
        className="generalButton material-icons-round "
        onClick={() => handleConversion(node)}>
        download
      </span>
    </>
  );
}
