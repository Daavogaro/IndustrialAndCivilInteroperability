import * as Router from "react-router-dom";
import { MessagePanel, StatusString } from "./MessagePanel";

type SidebarProps = {
  message: { status: StatusString; text: string } | null;
};

export function Sidebar({ message }: SidebarProps) {
  return (
    <div>
      <aside id="sidebar">
        <img src="./elettra-logo.png" alt="" />
        <img src="./psi-logo.png" alt="" />

        <ul id="nav-buttons">
          <Router.Link to="/">
            <li>
              <img src="./STEP-logo.png" alt="" style={{ height: 20 }} />
              STEP Hierarchy
            </li>
          </Router.Link>
          <Router.Link to="/IFCHierarchy">
            <li>
              <img src="./IFC-logo.png" alt="" style={{ height: 20 }} />
              IFC Hierarchy
            </li>
          </Router.Link>
          <Router.Link to="/ProductInventory">
            <li>
              <img src="./STEP-logo.png" alt="" style={{ height: 20 }} />
              Product Inventory
            </li>
          </Router.Link>
          <Router.Link to="/FileUpdate">
            <li>
              <span className="material-icons-round" style={{ fontSize: 20 }}>
                restore_page
              </span>
              File Update
            </li>
          </Router.Link>
          {/* <Router.Link to="/IFCViewer">
            <li>
              <img src="./IFC-logo.png" alt="" style={{ height: 20 }} />
              IFC Viewer
            </li>
          </Router.Link> */}

          <MessagePanel message={message} />
        </ul>
      </aside>
    </div>
  );
}
