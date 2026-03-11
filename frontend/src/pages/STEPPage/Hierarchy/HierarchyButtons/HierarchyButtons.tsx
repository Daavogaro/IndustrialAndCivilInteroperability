import { StatusString } from "../../../../components/Sidebar/MessagePanel";
import { AddChildButton } from "./buttons/AddChildButton";
import { UpdateHierarchyButton } from "./buttons/UpdateHierarchyButton";
import { UploadSTEPButton } from "./buttons/UploadSTEPButton";

export type HierarchyButtonsProps = {
  setTree: (tree: any) => void;
  setMessage: (message: { status: StatusString; text: string }) => void;
};

export function HierarchyButtons({
  setTree,
  setMessage,
}: HierarchyButtonsProps) {
  return (
    <div className="hierarchy-buttons" style={{ display: "flex", gap: "5px" }}>
      <UpdateHierarchyButton setTree={setTree} setMessage={setMessage} />
      <AddChildButton />
      <UploadSTEPButton />
    </div>
  );
}
