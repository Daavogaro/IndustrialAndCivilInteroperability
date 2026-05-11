from fastapi import APIRouter, UploadFile, File, Form
import os
import shutil
import re
from typing import Optional

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
async def upload_step(file: UploadFile = File(...), fileName: Optional[str] = Form(None)):
    # Prefer the provided form `fileName` when present, otherwise use the uploaded file's name
    original_filename = fileName if fileName else file.filename

    # If no extension provided in fileName, try to copy it from the uploaded file or default to .stp
    name, ext = os.path.splitext(original_filename)
    if not ext:
        _, uploaded_ext = os.path.splitext(file.filename or "")
        ext = uploaded_ext if uploaded_ext else ".stp"
        original_filename = f"{name}{ext}"

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