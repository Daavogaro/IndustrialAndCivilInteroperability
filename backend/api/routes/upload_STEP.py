from fastapi import APIRouter, UploadFile, File
import os
import shutil

from ..models.models import STEP_FOLDER
# Per ogni chiamata dobbiamo creare un Router.
router = APIRouter()


MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB

@router.post("/upload-step")
async def upload_step(file: UploadFile = File(...)):
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        return {"status": "error", "text": "File too large. Max 50MB allowed."}

    if not file.filename.lower().endswith(".stp"):
        return {"status": "error", "text": "Only STEP files allowed"}

    file_path = os.path.join(STEP_FOLDER, file.filename)
    with open(file_path, "wb") as f:
        f.write(contents)

    return {
        "status": "uploaded",
        "text": "File uploaded successfully",
        "filename": file.filename,
        "path": file_path
    }