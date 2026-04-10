import { Topbar } from "../../components/Topbar";
import { GLTFViewer } from "../STEPPage/NodeDetails/gLTFViewer/gLTFViewer";

type STEPViewerPageProps = {};

export function STEPViewerPage({}: STEPViewerPageProps) {
  return (
    <div>
      <Topbar title="STEP Viewer" />
    </div>
  );
}
