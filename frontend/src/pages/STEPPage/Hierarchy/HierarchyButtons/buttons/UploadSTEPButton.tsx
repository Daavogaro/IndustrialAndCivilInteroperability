import { toogleModal } from "../../../../../utils/htmlFunctions";

export function UploadSTEPButton() {
  return (
    <span
      className="generalButton material-icons-round"
      style={{
        padding: "2px",
        borderRadius: "5px",
        cursor: "pointer",
      }}
      onClick={() => toogleModal("upload-step-modal")}>
      upload_file
    </span>
  );
}
