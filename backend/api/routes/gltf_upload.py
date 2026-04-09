from fastapi import APIRouter
from pydantic import BaseModel
from pathlib import Path
from ..models.models import GLB_FOLDER

router = APIRouter()

class FilesRequest(BaseModel):
    files: list[str]

@router.post("/gltf-upload")
async def gltf_upload(request: FilesRequest):
    glb_folder = Path(GLB_FOLDER)

    filenames = sorted(
        file.name for file in glb_folder.iterdir()
        if file.is_file() and file.name not in request.files
    )

    return {
        "status": "success",
        "text": "Updated gLTF viewer",
        "files": [f"/api/glb/{name}" for name in filenames]
    }