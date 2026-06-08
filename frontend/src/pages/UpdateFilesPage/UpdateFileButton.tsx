import { toogleModal } from "../../utils/htmlFunctions";
import { TreeNode } from "../STEPPage/Hierarchy/buildTree";

export function UpdateFileButton({setFileName,fileName,tree}: {setFileName: (fileName: string) => void, fileName: string, tree: TreeNode[]}) {
  return (
    <span
      className="generalButton material-icons-round"
      style={{
        padding: "2px",
        borderRadius: "5px",
        cursor: "pointer",
      }}
      onClick={() => {
        setFileName(fileName)
        toogleModal("update-step-modal");
      }}>
      autorenew
    </span>
  );
}
