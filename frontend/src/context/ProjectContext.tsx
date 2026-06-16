import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

export type Project = {
  id: string;
  name: string;
  graphUri: string;
  createdAt: string;
};

type ProjectContextValue = {
  projects: Project[];
  activeProject: Project | null;
  setActiveProject: (project: Project) => void;
  loadProjects: () => Promise<void>;
};

export const ProjectContext = createContext<ProjectContextValue>({
  projects: [],
  activeProject: null,
  setActiveProject: () => {},
  loadProjects: async () => {},
});

export function useProject(): ProjectContextValue {
  return useContext(ProjectContext);
}

export function ProjectProvider({ children }: { children: ReactNode }) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [activeProject, setActiveProjectState] = useState<Project | null>(null);

  const loadProjects = useCallback(async () => {
    try {
      const res = await fetch("/api/projects");
      if (!res.ok) return;
      const data: Project[] = await res.json();
      setProjects(data);

      const storedId = localStorage.getItem("activeProjectId");
      const match = data.find((p) => p.id === storedId) ?? data[0] ?? null;
      if (match) {
        setActiveProjectState(match);
        localStorage.setItem("activeProjectId", match.id);
      } else {
        setActiveProjectState(null);
      }
    } catch {
      // network failure — leave state as-is
    }
  }, []);

  const setActiveProject = useCallback((project: Project) => {
    setActiveProjectState(project);
    localStorage.setItem("activeProjectId", project.id);
  }, []);

  useEffect(() => {
    loadProjects();
  }, [loadProjects]);

  return (
    <ProjectContext.Provider
      value={{ projects, activeProject, setActiveProject, loadProjects }}>
      {children}
    </ProjectContext.Provider>
  );
}
