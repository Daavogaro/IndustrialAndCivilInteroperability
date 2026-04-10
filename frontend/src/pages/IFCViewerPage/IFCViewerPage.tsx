import { Topbar } from "../../components/Topbar";
import { GLTFViewer } from "../STEPPage/NodeDetails/gLTFViewer/gLTFViewer";

type IFCViewerPageProps = {};

export function IFCViewerPage({}: IFCViewerPageProps) {
  return (
    <div>
      <Topbar title="IFC Viewer" />
    </div>
  );
}
