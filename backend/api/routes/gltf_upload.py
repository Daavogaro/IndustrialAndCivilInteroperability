from fastapi import APIRouter
from pydantic import BaseModel
from pathlib import Path
from typing import Optional
from ..models.models import GLB_FOLDER, get_project_folders

router = APIRouter()

class FilesRequest(BaseModel):
    files: list[str]
    projectId: Optional[str] = None

@router.post("/gltf-upload")
async def gltf_upload(request: FilesRequest):
    if request.projectId:
        folders = get_project_folders(request.projectId)
        glb_folder = Path(folders["glb"])
        url_prefix = f"/api/static/projects/{request.projectId}/GLB"
    else:
        glb_folder = Path(GLB_FOLDER)
        url_prefix = "/api/glb"

    if not glb_folder.exists():
        return {"status": "success", "text": "No files found", "files": []}

    filenames = sorted(
        file.name for file in glb_folder.iterdir()
        if file.is_file() and file.name not in request.files
    )

    return {
        "status": "success",
        "text": "Updated gLTF viewer",
        "files": [f"{url_prefix}/{name}" for name in filenames],
    }