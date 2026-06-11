import * as Router from "react-router-dom";
import { MessagePanel, StatusString } from "./MessagePanel";
import { useProject } from "../../context/ProjectContext";

type SidebarProps = {
  message: { status: StatusString; text: string } | null;
};

export function Sidebar({ message }: SidebarProps) {
  const { activeProject } = useProject();

  return (
    <div>
      <aside id="sidebar">
        <img src="./elettra-logo.png" alt="" />
        <img src="./psi-logo.png" alt="" />

        {activeProject && (
          <span
            className="active-project-label"
            style={{
              fontSize: "0.75em",
              color: "var(--grey-2)",
              padding: "2px 8px",
              display: "block",
              textAlign: "center",
              wordBreak: "break-word",
            }}>
            {activeProject.name}
          </span>
        )}

        <ul id="nav-buttons">
          <Router.Link to="/STEP">
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
              <span className="material-icons-round" style={{ fontSize: 20 }}>
                shopping_cart
              </span>
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
          <Router.Link to="/Projects">
            <li>
              <span className="material-icons-round" style={{ fontSize: 20 }}>
                folder
              </span>
              Other projects
            </li>
          </Router.Link>
          <MessagePanel message={message} />
        </ul>
      </aside>
    </div>
  );
}
