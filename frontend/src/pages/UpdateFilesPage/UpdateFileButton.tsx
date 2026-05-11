import { toogleModal } from "../../utils/htmlFunctions";

export function UpdateFileButton({setFileName,fileName}: {setFileName: (fileName: string) => void, fileName: string}) {
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
