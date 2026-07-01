from fastapi import APIRouter, WebSocket
from fastapi.concurrency import run_in_threadpool

from ..services.db_requests.substitution_file_query import substitution_file_query

from ..models.models import GLB_FOLDER, JSON_FOLDER, GLTF_FOLDER, STEP_FOLDER, RDF_FOLDER, get_project_folders
from ..services.importing_STEP.compess_gltf import compress_gltf
from ..services.db_requests.updatingSTEP.gltf_update_STEP import return_gltf_hierarchy
from ..services.db_requests.import_in_DB import import_to_db
from ..services.importing_STEP.RDF_conversion import NameAndNumber, convert_hierarchy_in_rdf
from ..services.importing_STEP.occ_converter import export_gltf
import os
import json
import re
from ..services.importing_STEP.RDF_conversion import GeometryNode
from ..services.db_requests.name_and_number import name_and_number_query
from ..services.db_requests.existing_nodes import existing_nodes
from ..services.db_requests.updatingSTEP.RDF_update_STEP import rdf_update_step

# I servizi Windows hanno bisogno di path reali all'interno del PC, non del container.

router = APIRouter()

# Funzioni utili
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

# Un websocket è una connessione bidirezionale tra client e server che permette di inviare dati in tempo reale. In questo caso, lo usiamo per comunicare con il frontend React durante tutto il processo di conversione e parsing, in modo da poter aggiornare l'utente sullo stato dell'operazione.
@router.websocket("/ws/update")
async def websocket_convert(websocket: WebSocket):
    await websocket.accept() # Accettiamo la connessione websocket. Ora possiamo inviare e ricevere messaggi da questo client.

    try:
        data = await websocket.receive_json() # Aspettiamo di ricevere un messaggio JSON dal client. Ci aspettiamo che questo messaggio contenga il nome del file STEP che l'utente ha caricato e che vogliamo convertire.
        filename = sanitize_filename(data.get("filename", ""))
        graph_name = data.get("graph_name")
        project_id = data.get("project_id")
        tree = data.get("tree")
        ownerFirstName = data.get("ownerFirstName", "Unknown")
        ownerLastName = data.get("ownerLastName", "Unknown")
        time = data.get("time", "Unknown")

        if project_id:
            folders = get_project_folders(project_id)
            step_folder = folders["step"]
            gltf_folder = folders["gltf"]
            glb_folder = folders["glb"]
            json_folder = folders["json"]
            rdf_folder = folders["rdf"]
        else:
            step_folder = STEP_FOLDER
            gltf_folder = GLTF_FOLDER
            glb_folder = GLB_FOLDER
            json_folder = JSON_FOLDER
            rdf_folder = RDF_FOLDER

        input_file = os.path.join(step_folder, filename)
        output_file = os.path.join(gltf_folder, filename.replace(".stp", ".gltf"))
        output_file_compressed = os.path.join(glb_folder, filename.replace(".stp", ".glb"))
        # Ad ogni passaggio vengono mandati dei messaggi al client per aggiornarlo sullo stato dell'operazione

        # STEP to gLTF conversion
        await websocket.send_json({"status": "wip", "text": "Starting conversion"}) # Inviamo un messaggio al client per indicare che la conversione è iniziata. Il client può usare questo messaggio per mostrare un indicatore di caricamento o aggiornare lo stato dell'interfaccia utente.

        # Conversione STEP -> gLTF tramite il convertitore Python (pythonocc-core).
        print(f"Converting STEP file: {input_file}")
        gltf_path = await run_in_threadpool(export_gltf, input_file, output_file)
        await websocket.send_json({"status": "success", "text": "Conversion Done"}) # Se la conversione è andata a buon fine, inviamo un messaggio al client per indicare che la conversione è stata completata con successo.
        # Parsing gerarchia
        await websocket.send_json({"status": "wip", "text": "Parsing hierarchy"})
        try:
            hierarchy = await return_gltf_hierarchy(
                gltf_path,
                graph_name,
                gltf_path,
            )
        except Exception as e:
            await websocket.send_json({"status": "error", "text": f"return_gltf_hierarchy error: {e}"})
            raise
        os.makedirs(json_folder, exist_ok=True)
        hierarchy_file = os.path.join(json_folder, filename.replace(".stp", ".json"))
        await run_in_threadpool(write_json_file, hierarchy_file, hierarchy) # Scriviamo il file JSON della gerarchia in un thread separato per non bloccare il server. La funzione write_json_file è una funzione sincrona che scrive un dizionario su un file JSON. run_in_threadpool è una funzione di FastAPI che permette di eseguire funzioni sincrone in un thread separato, in modo da non bloccare il loop asincrono principale del server.
        await websocket.send_json({
            "status": "success",
            "text": "Hierarchy parsed and saved as JSON"
        })
        # Conversione gerarchia in RDF
        await websocket.send_json({"status": "wip", "text": "Converting hierarchy to RDF"})
        data = await run_in_threadpool(read_json_file, hierarchy_file) # Leggiamo il file JSON della gerarchia in un thread separato. La funzione read_json_file è una funzione sincrona che legge un file JSON e restituisce un dizionario. Anche questa operazione potrebbe richiedere del tempo, quindi la eseguiamo in un thread separato.
        hierarchy_nodes_from_file = await run_in_threadpool(validate_geometry_nodes, data)
        exist_nodes=await existing_nodes()
        # Run the updated hierarchy extraction so node renaming and the
        # remaining substitution-number debug print both execute.


        # Viene lanciata una query SPARQL per ottenere la lista dei nomi e dei numeri già presenti nel database, in modo da poter assegnare un numero univoco a ogni nodo della gerarchia che stiamo importando.
        input_file_url = gltf_folder + "/" + filename.replace(".stp", ".gltf")
        input_filename = filename.replace(".stp", ".gltf")

        rdf_data = await run_in_threadpool(
            rdf_update_step,
            hierarchy_nodes_from_file,
            None,
            exist_nodes,
            tree,
            "https://elettra2.0#",
            input_filename,
            input_file_url,
            ownerFirstName,
            ownerLastName,
            time
        )
        await websocket.send_json({"status": "wip", "text": "Compressing gLTF"}) # Inviamo un messaggio al client per indicare che stiamo iniziando la fase di compressione del file gLTF. Anche questa operazione potrebbe richiedere del tempo, quindi è importante tenere aggiornato l'utente sullo stato dell'operazione.
        await run_in_threadpool(compress_gltf, gltf_path, output_file_compressed)
        await websocket.send_json({"status": "success", "text": "gLTF Compressed"}) # Se la compressione è andata a buon fine, inviamo un messaggio al client per indicare che il file gLTF è stato compresso con successo. A questo punto, abbiamo sia il file gLTF non compresso che quello compresso, e possiamo procedere con le fasi successive di parsing e importazione in DB.
        file_path = os.path.join(rdf_folder, "bulk_import.nt")
        await run_in_threadpool(write_text_file, file_path, rdf_data)
        await websocket.send_json({
            "status": "success",
            "text": "RDF file created"
        })
        # -------------------------
        # Batch import
        # -------------------------
        BATCH_SIZE = 1000
        batches, total_lines = await run_in_threadpool(
            split_batches, rdf_data, BATCH_SIZE
        )
        for batch in batches:
            await import_to_db(websocket, graph_name, batch)
        await websocket.send_json({
            "status": "success",
            "text": f"Imported {total_lines} triples in DB"
        })

    except Exception as e:
        await websocket.send_json({
            "status": "error",
            "text": str(e)
        })