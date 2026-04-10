import * as Router from "react-router-dom";
import { MessagePanel, StatusString } from "./MessagePanel";

type SidebarProps = {
  message: { status: StatusString; text: string } | null;
};

export function Sidebar({ message }: SidebarProps) {
  return (
    <div>
      <aside id="sidebar">
        <img src="./psi-logo.png" alt="" />

        <ul id="nav-buttons">
          <Router.Link to="/">
            <li>
              <span className="material-icons-round">view_in_ar</span>
              STEP Hierarchy
            </li>
          </Router.Link>
          <Router.Link to="/IFCHierarchy">
            <li>
              <img src="./IFC-logo.png" alt="" style={{ height: 20 }} />
              IFC Hierarchy
            </li>
          </Router.Link>
          <Router.Link to="/STEPViewer">
            <li>
              <img src="./STEP-logo.png" alt="" style={{ height: 20 }} />
              STEP Viewer
            </li>
          </Router.Link>

          <MessagePanel message={message} />
        </ul>
      </aside>
    </div>
  );
}
