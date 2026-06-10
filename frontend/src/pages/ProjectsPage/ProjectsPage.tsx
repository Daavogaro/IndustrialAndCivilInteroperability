import { useState } from "react";
import { Topbar } from "../../components/Topbar";
import { useProject, type Project } from "../../context/ProjectContext";

function formatDate(iso: string): string {
  try {
    const d = new Date(iso);
    const dd = String(d.getDate()).padStart(2, "0");
    const mm = String(d.getMonth() + 1).padStart(2, "0");
    const yyyy = d.getFullYear();
    return `${dd}/${mm}/${yyyy}`;
  } catch {
    return iso;
  }
}

export function ProjectsPage() {
  const { projects, activeProject, setActiveProject, loadProjects } =
    useProject();
  const [newName, setNewName] = useState("");
  const [createError, setCreateError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    const name = newName.trim();
    if (!name) {
      setCreateError("Project name cannot be empty");
      return;
    }
    setCreating(true);
    setCreateError(null);
    try {
      const res = await fetch("/api/projects", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        setCreateError(err.detail ?? `Error ${res.status}`);
        return;
      }
      const created: Project = await res.json();
      await loadProjects();
      setActiveProject(created);
      setNewName("");
    } catch {
      setCreateError("Network error");
    } finally {
      setCreating(false);
    }
  };

  const handleDelete = async (project: Project) => {
    if (!confirm(`Delete project "${project.name}"? This will drop its Virtuoso graph permanently.`)) return;
    try {
      const res = await fetch(`/api/projects/${project.id}`, {
        method: "DELETE",
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        alert(err.detail ?? `Error ${res.status}`);
        return;
      }
      await loadProjects();
    } catch {
      alert("Network error");
    }
  };

  return (
    <div
      style={{
        display: "grid",
        gridTemplateRows: "auto 1fr",
        height: "100vh",
        overflow: "hidden",
      }}>
      <Topbar title="Projects" />

      <div className="panel-scroll" style={{ padding: "16px" }}>
        {/* New project form */}
        <form
          onSubmit={handleCreate}
          style={{ display: "flex", gap: "8px", alignItems: "center", marginBottom: "20px" }}>
          <input
            type="text"
            placeholder="New project name…"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            style={{
              flex: 1,
              padding: "6px 10px",
              background: "var(--background-100)",
              border: "1px solid var(--grey-2)",
              borderRadius: 5,
              color: "inherit",
            }}
          />
          <button
            type="submit"
            className="generalButton"
            disabled={creating}
            style={{ padding: "6px 14px" }}>
            {creating ? "Creating…" : "Create Project"}
          </button>
        </form>
        {createError && (
          <p style={{ color: "#e74c3c", marginBottom: "12px" }}>{createError}</p>
        )}

        {/* Project cards */}
        {projects.length === 0 ? (
          <p style={{ color: "var(--grey-2)" }}>
            No projects yet. Create one above.
          </p>
        ) : (
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))",
              gap: "12px",
            }}>
            {projects.map((project) => {
              const isActive = activeProject?.id === project.id;
              return (
                <div
                  key={project.id}
                  style={{
                    background: isActive ? "var(--primary-300)" : "var(--background-100)",
                    border: `1px solid ${isActive ? "var(--primary-300)" : "var(--grey-2)"}`,
                    borderRadius: 8,
                    padding: "14px",
                    display: "flex",
                    flexDirection: "column",
                    gap: "6px",
                  }}>
                  <strong style={{ fontSize: "1.1em" }}>{project.name}</strong>
                  <span style={{ fontSize: "0.8em", color: "var(--grey-2)", wordBreak: "break-all" }}>
                    {project.graphUri}
                  </span>
                  <span style={{ fontSize: "0.8em" }}>
                    Created: {formatDate(project.createdAt)}
                  </span>
                  <div style={{ display: "flex", gap: "8px", marginTop: "8px" }}>
                    <button
                      className="generalButton"
                      disabled={isActive}
                      onClick={() => setActiveProject(project)}
                      style={{ flex: 1, padding: "4px 0" }}>
                      {isActive ? "Active" : "Activate"}
                    </button>
                    <button
                      className="generalButton"
                      disabled={isActive}
                      onClick={() => handleDelete(project)}
                      style={{
                        flex: 1,
                        padding: "4px 0",
                        opacity: isActive ? 0.4 : 1,
                      }}>
                      Delete
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
