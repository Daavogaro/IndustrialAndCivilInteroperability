from fastapi import APIRouter, UploadFile, File
import os
import shutil
import re

from ..models.models import STEP_FOLDER
# Per ogni chiamata dobbiamo creare un Router.
router = APIRouter()


def sanitize_filename(filename: str) -> str:
    base_name = os.path.basename(filename)
    stem, extension = os.path.splitext(base_name)
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", stem)
    stem = re.sub(r"_+", "_", stem).strip("._-")
    if not stem:
        stem = "uploaded_file"
    return f"{stem}{extension.lower()}"

@router.post("/upload-step")
async def upload_step(file: UploadFile = File(...)):
    original_filename = file.filename or ""
    if not original_filename.lower().endswith(".stp"):
        return {"status": "error", "text": "Only STEP files allowed"}

    safe_filename = sanitize_filename(original_filename)
    file_path = os.path.join(STEP_FOLDER, safe_filename)
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    return {
        "status": "uploaded",
        "text": "File uploaded successfully",
        "filename": safe_filename,
        "path": file_path
    }