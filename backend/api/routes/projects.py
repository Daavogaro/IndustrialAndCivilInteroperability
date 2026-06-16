import json
import re
import threading
from datetime import datetime, timezone
from pathlib import Path

import requests
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..models.models import VIRTUOSO_URL

router = APIRouter()

_LOCK = threading.Lock()
_PROJECTS_FILE = Path(__file__).resolve().parents[4] / "tmp" / "projects.json"

_SEED = [
    {
        "id": "elettra2",
        "name": "Elettra 2.0",
        "graphUri": "http://localhost:8890/Elettra2/",
        "createdAt": "2024-01-01T00:00:00+00:00",
    }
]


def _read_projects() -> list[dict]:
    with _LOCK:
        if not _PROJECTS_FILE.exists() or _PROJECTS_FILE.stat().st_size == 0:
            _PROJECTS_FILE.parent.mkdir(parents=True, exist_ok=True)
            _PROJECTS_FILE.write_text(json.dumps(_SEED, indent=2))
            return list(_SEED)
        return json.loads(_PROJECTS_FILE.read_text())


def _write_projects(projects: list[dict]) -> None:
    with _LOCK:
        _PROJECTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        _PROJECTS_FILE.write_text(json.dumps(projects, indent=2))


def assert_known_graph(graph: str) -> None:
    projects = _read_projects()
    known = {p["graphUri"] for p in projects}
    if graph not in known:
        raise HTTPException(status_code=400, detail=f"Unknown graph: {graph}")


def _slugify(name: str) -> str:
    slug = name.strip().lower()
    slug = slug.replace(" ", "-")
    slug = re.sub(r"[^a-z0-9-]", "", slug)
    slug = re.sub(r"-+", "-", slug)
    slug = slug.strip("-")
    return slug[:40]


def _unique_id(base_id: str, existing_ids: set[str]) -> str:
    if base_id not in existing_ids:
        return base_id
    i = 1
    while f"{base_id}-{i}" in existing_ids:
        i += 1
    return f"{base_id}-{i}"


class CreateProjectRequest(BaseModel):
    name: str


@router.get("/projects")
def list_projects():
    return _read_projects()


@router.post("/projects", status_code=201)
def create_project(request: CreateProjectRequest):
    name = request.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Project name cannot be empty")

    base_id = _slugify(name)
    if not base_id:
        raise HTTPException(status_code=422, detail="Project name produced an empty slug")

    projects = _read_projects()
    existing_ids = {p["id"] for p in projects}
    project_id = _unique_id(base_id, existing_ids)

    project = {
        "id": project_id,
        "name": name,
        "graphUri": f"http://localhost:8890/{project_id}/",
        "createdAt": datetime.now(timezone.utc).isoformat(),
    }
    projects.append(project)
    _write_projects(projects)
    return project


@router.delete("/projects/{project_id}")
def delete_project(project_id: str):
    projects = _read_projects()
    target = next((p for p in projects if p["id"] == project_id), None)
    if target is None:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")

    graph_uri = target["graphUri"]
    drop_query = f"DROP SILENT GRAPH <{graph_uri}>"
    try:
        requests.post(
            VIRTUOSO_URL,
            data={"update": drop_query},
            headers={"Accept": "application/sparql-results+json"},
            timeout=15,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to drop Virtuoso graph: {e}")

    updated = [p for p in projects if p["id"] != project_id]
    _write_projects(updated)
    return {"status": "success"}
