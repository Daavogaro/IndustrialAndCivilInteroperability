import { toogleModal } from "../../../../../utils/htmlFunctions";

export function AddChildButton() {
  return (
    <span
      className="generalButton material-icons-round"
      style={{
        padding: "2px",
        borderRadius: "5px",
        cursor: "pointer",
      }}
      onClick={() => toogleModal("add-child-modal")}>
      add
    </span>
  );
}
