import asyncio
import os
import json
import uuid
from functools import partial
from fastapi import APIRouter, WebSocket
from fastapi.concurrency import run_in_threadpool
from ..models.models import JSON_FOLDER
from ..services.ifc_conversion.blender import run_blender_script

def generate_temp_file(folder: str, node: dict):
        job_id = str(uuid.uuid4())
        tmp_path = os.path.join(folder, f"{job_id}.json")

        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(node, f)
        return tmp_path

IMPORT_GLTF_SCRIPT = r"backend\api\services\ifc_conversion\blender_script\import_gltf.py"
GLTF_PATH = r"tmp\gLTF\PSI_SLS2_Girder_Superbend.gltf"
router = APIRouter()
# Un websocket è una connessione bidirezionale tra client e server che permette di inviare dati in tempo reale. In questo caso, lo usiamo per comunicare con il frontend React durante tutto il processo di conversione e parsing, in modo da poter aggiornare l'utente sullo stato dell'operazione.
@router.websocket("/ws/blender_run_scripts")
async def websocket_ifc_convert(websocket: WebSocket):
    await websocket.accept() # Accettiamo la connessione websocket. Ora possiamo inviare e ricevere messaggi da questo client.

    try:
        data = await websocket.receive_json() # Aspettiamo di ricevere un messaggio JSON dal client. Ci aspettiamo che questo messaggio contenga il nome del file STEP che l'utente ha caricato e che vogliamo convertire.
        node = data.get("node")
        save_blend = bool(data.get("save_blend", False))
                    
        await websocket.send_json({"status": "wip", "text": "Starting conversion"}) # Inviamo un messaggio al client per indicare che la conversione è iniziata. Il client può usare questo messaggio per mostrare un indicatore di caricamento o aggiornare lo stato dell'interfaccia utente.

        tmp_file = await run_in_threadpool(generate_temp_file, JSON_FOLDER, node)
        tmp_path = os.path.join(JSON_FOLDER, os.path.basename(tmp_file))
        progress_queue: asyncio.Queue[str] = asyncio.Queue()
        loop = asyncio.get_running_loop()

        def on_output(line: str):
            if line.startswith("STATUS: "):
                loop.call_soon_threadsafe(progress_queue.put_nowait, line.removeprefix("STATUS: "))

        runner = run_in_threadpool(
            partial(
                run_blender_script,
                IMPORT_GLTF_SCRIPT,
                [GLTF_PATH, tmp_path, str(save_blend).lower()],
                on_output=on_output,
            )
        )
        runner_task = asyncio.create_task(runner)

        while True:
            if runner_task.done() and progress_queue.empty():
                break

            try:
                progress = await asyncio.wait_for(progress_queue.get(), timeout=0.25)
            except asyncio.TimeoutError:
                continue

            await websocket.send_json({"status": "wip", "text": progress})

        await runner_task
        await websocket.send_json({
            "status": "success",
            "text": "IFC conversion completed",
        })
    except Exception as e:
        await websocket.send_json({
            "status": "error",
            "text": str(e)
        })