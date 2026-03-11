from fastapi import APIRouter, WebSocket
from fastapi.concurrency import run_in_threadpool

from ..models.models import JSON_FOLDER, MAYO_SERVICE_URL,GLTF_FOLDER,STEP_FOLDER,RDF_FOLDER
from ..services.importing_STEP.gltf import return_gltf_hierarchy
from ..services.db_requests.import_in_DB import import_to_db
from ..services.importing_STEP.RDF_conversion import NameAndNumber, convert_hierarchy_in_rdf
import os
import json
import httpx
from ..services.importing_STEP.RDF_conversion import GeometryNode
from ..services.db_requests.name_and_number import name_and_number_query

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


# Un websocket è una connessione bidirezionale tra client e server che permette di inviare dati in tempo reale. In questo caso, lo usiamo per comunicare con il frontend React durante tutto il processo di conversione e parsing, in modo da poter aggiornare l'utente sullo stato dell'operazione.
@router.websocket("/ws/convert")
async def websocket_convert(websocket: WebSocket):
    await websocket.accept() # Accettiamo la connessione websocket. Ora possiamo inviare e ricevere messaggi da questo client.

    try:
        data = await websocket.receive_json() # Aspettiamo di ricevere un messaggio JSON dal client. Ci aspettiamo che questo messaggio contenga il nome del file STEP che l'utente ha caricato e che vogliamo convertire.
        filename = data.get("filename")
        graph_name = data.get("graph_name")
        parent_uri = data.get("parent_uri")

        input_file = os.path.join(STEP_FOLDER, filename)
        output_file = os.path.join(GLTF_FOLDER, filename.replace(".stp", ".gltf"))
        # Ad ogni passaggio vengono mandati dei messaggi al client per aggiornarlo sullo stato dell'operazione

        # STEP to gLTF conversion
        await websocket.send_json({"status": "wip", "text": "Starting conversion"}) # Inviamo un messaggio al client per indicare che la conversione è iniziata. Il client può usare questo messaggio per mostrare un indicatore di caricamento o aggiornare lo stato dell'interfaccia utente.

        async with httpx.AsyncClient() as client: # Dato che la chiamata al servizio Windows potrebbe richiedere del tempo, usiamo httpx.AsyncClient per fare una richiesta HTTP asincrona. In questo modo, il server FastAPI non si bloccherà in attesa della risposta e potrà continuare a gestire altre richieste o websocket.
            # Chiamata a Mayo
            print(f"Calling Mayo service for file: {input_file}")
            res = await client.post(MAYO_SERVICE_URL,json={"input_file": input_file, "output_file": output_file},timeout=None)
            res.raise_for_status() # Se la risposta ha un codice di stato diverso da 200, viene sollevata un'eccezione che verrà catturata dal blocco except.
            await websocket.send_json({"status": "success", "text": "Conversion Done with Mayo"}) # Se la conversione è andata a buon fine, inviamo un messaggio al client per indicare che la conversione è stata completata con successo.
            
            # Parsing gerarchia
            await websocket.send_json({"status": "wip", "text": "Parsing hierarchy"})
            # Restituiamo la gerarchia in un array e salviamo anche un file JSON con la gerarchia stessa
            #  TODO: Non salvare il file JSON della gerarchia, ma inviarlo direttamente al DB 
            hierarchy = await return_gltf_hierarchy(GLTF_FOLDER +"/"+ filename.replace(".stp", ".gltf"))

            os.makedirs(JSON_FOLDER, exist_ok=True)
            hierarchy_file = os.path.join(JSON_FOLDER, filename.replace(".stp", ".json"))
            await run_in_threadpool(write_json_file, hierarchy_file, hierarchy) # Scriviamo il file JSON della gerarchia in un thread separato per non bloccare il server. La funzione write_json_file è una funzione sincrona che scrive un dizionario su un file JSON. run_in_threadpool è una funzione di FastAPI che permette di eseguire funzioni sincrone in un thread separato, in modo da non bloccare il loop asincrono principale del server.
            await websocket.send_json({
                "status": "success",
                "text": "Hierarchy parsed and saved as JSON"
            })

            # Conversione gerarchia in RDF 
            await websocket.send_json({"status": "wip", "text": "Converting hierarchy to RDF"})
            data = await run_in_threadpool(read_json_file, hierarchy_file) # Leggiamo il file JSON della gerarchia in un thread separato. La funzione read_json_file è una funzione sincrona che legge un file JSON e restituisce un dizionario. Anche questa operazione potrebbe richiedere del tempo, quindi la eseguiamo in un thread separato. 
            hierarchy_nodes = await run_in_threadpool(validate_geometry_nodes, data)
            nameAndNumberList = await name_and_number_query()
            # Viene lanciata una query SPARQL per ottenere la lista dei nomi e dei numeri già presenti nel database, in modo da poter assegnare un numero univoco a ogni nodo della gerarchia che stiamo importando.
            input_file_url = GLTF_FOLDER + "/" + filename.replace(".stp", ".gltf")
            input_filename = filename.replace(".stp", ".gltf")
            
            rdf_data = await run_in_threadpool(
                convert_hierarchy_in_rdf,
                hierarchy_nodes,
                parent_uri,
                nameAndNumberList,
                "https://elettra2.0#",
                input_filename,
                input_file_url

            )
    
            file_path = os.path.join(RDF_FOLDER, "bulk_import.nt")
    
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