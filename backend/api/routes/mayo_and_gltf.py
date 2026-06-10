from fastapi import APIRouter, WebSocket
from fastapi.concurrency import run_in_threadpool

from ..models.models import GLB_FOLDER, JSON_FOLDER, GLTF_FOLDER, STEP_FOLDER, RDF_FOLDER
from ..services.importing_STEP.compess_gltf import compress_gltf
from ..services.importing_STEP.gltf import return_gltf_hierarchy
from ..services.db_requests.import_in_DB import import_to_db
from ..services.importing_STEP.RDF_conversion import NameAndNumber, convert_hierarchy_in_rdf
from ..services.importing_STEP.occ_converter import export_gltf
import os
import json
import re
from ..services.importing_STEP.RDF_conversion import GeometryNode
from ..services.db_requests.name_and_number import name_and_number_query
from ..services.db_requests.existing_nodes import existing_nodes

router = APIRouter()

def write_json_file(path: str, data: dict):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

def read_json_file(path: str):
    with open(path, "r") as f:
        return json.load(f)

def write_text_file(path: str, content: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

def split_batches(text: str, batch_size: int):
    lines = text.split("\n")
    return [
        "".join(lines[i:i + batch_size])
        for i in range(0, len(lines), batch_size)
    ], len(lines)

def validate_geometry_nodes(data):
    GeometryNode.model_rebuild()
    return [GeometryNode.model_validate(obj) for obj in data[0]["nodes"]]

def sanitize_filename(filename: str) -> str:
    base_name = os.path.basename(filename or "")
    stem, extension = os.path.splitext(base_name)
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", stem)
    stem = re.sub(r"_+", "_", stem).strip("._-")
    if not stem:
        stem = "uploaded_file"
    return f"{stem}{extension.lower()}"

@router.websocket("/ws/convert")
async def websocket_convert(websocket: WebSocket):
    await websocket.accept()

    try:
        data = await websocket.receive_json()
        filename = sanitize_filename(data.get("filename", ""))
        graph_name = data.get("graph_name")
        parent_uri = data.get("parent_uri")
        ownerFirstName = data.get("ownerFirstName", "Unknown")
        ownerLastName = data.get("ownerLastName", "Unknown")
        time = data.get("time", "Unknown")

        stem, _ = os.path.splitext(filename)

        input_file = os.path.join(STEP_FOLDER, filename)
        output_file = os.path.join(GLTF_FOLDER, stem + ".gltf")
        output_file_compressed = os.path.join(GLB_FOLDER, stem + ".glb")

        await websocket.send_json({"status": "wip", "text": "Starting conversion"})

        gltf_path = await run_in_threadpool(export_gltf, input_file, output_file)
        await websocket.send_json({"status": "success", "text": "Conversion Done"})

        await websocket.send_json({"status": "wip", "text": "Parsing hierarchy"})
        hierarchy = await return_gltf_hierarchy(gltf_path)

        os.makedirs(JSON_FOLDER, exist_ok=True)
        hierarchy_file = os.path.join(JSON_FOLDER, stem + ".json")
        await run_in_threadpool(write_json_file, hierarchy_file, hierarchy)
        await websocket.send_json({"status": "success", "text": "Hierarchy parsed and saved as JSON"})

        await websocket.send_json({"status": "wip", "text": "Converting hierarchy to RDF"})
        data = await run_in_threadpool(read_json_file, hierarchy_file)
        hierarchy_nodes = await run_in_threadpool(validate_geometry_nodes, data)
        exist_nodes = await existing_nodes()

        input_file_url = gltf_path.replace("\\", "/")
        input_filename = stem + ".gltf"

        rdf_data = await run_in_threadpool(
            convert_hierarchy_in_rdf,
            hierarchy_nodes,
            parent_uri,
            exist_nodes,
            "https://elettra2.0#",
            input_filename,
            input_file_url,
            ownerFirstName,
            ownerLastName,
            time
        )

        await websocket.send_json({"status": "wip", "text": "Compressing gLTF"})
        await run_in_threadpool(compress_gltf, gltf_path, output_file_compressed)
        await websocket.send_json({"status": "success", "text": "gLTF Compressed"})

        file_path = os.path.join(RDF_FOLDER, "bulk_import.nt")
        await run_in_threadpool(write_text_file, file_path, rdf_data)
        await websocket.send_json({"status": "success", "text": "RDF file created"})

        BATCH_SIZE = 1000
        batches, total_lines = await run_in_threadpool(split_batches, rdf_data, BATCH_SIZE)

        for batch in batches:
            await import_to_db(websocket, graph_name, batch)

        await websocket.send_json({"status": "success", "text": f"Imported {total_lines} triples in DB"})

    except Exception as e:
        await websocket.send_json({"status": "error", "text": str(e)})
