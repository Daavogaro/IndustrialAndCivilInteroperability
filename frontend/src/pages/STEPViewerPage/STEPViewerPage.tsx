import { Topbar } from "../../components/Topbar";
import { GLTFViewer } from "./gLTFViewer/gLTFViewer";

type STEPViewerPageProps = {};

export function STEPViewerPage({}: STEPViewerPageProps) {
  return (
    <div>
      <Topbar title="STEP Viewer" />
      <GLTFViewer />
    </div>
  );
}
