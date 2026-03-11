from fastapi import FastAPI,APIRouter
from pydantic import BaseModel
import subprocess
import threading
import queue
import time
from ...models.models import MAYO_EXE,INI_FILE

router = APIRouter()

# Questa classe serve per definire la struttura del JSON che riceveremo nella richiesta POST a /convert. 
class MayoRequest(BaseModel):
    input_file: str
    output_file: str

def convert_with_mayo(input_file: str, output_file: str):

    import os
    if not os.path.exists(input_file):
        raise Exception(f"Input file does not exist: {input_file}")
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    cmd = [MAYO_EXE, '--use-settings', INI_FILE, input_file, '--export', output_file]
    print("CMD:", cmd)
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    print("RETURN CODE:", result.returncode)
    print("STDOUT:", result.stdout)
    print("STDERR:", result.stderr)
    
    if result.returncode != 0:
        # Do not raise generic Exception; include output in the response
        return {
            "status": "error",
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr
        }
    
    return {
        "status": "success",
        "stdout": result.stdout,
        "stderr": result.stderr
    }
# Quando arriva la richiesta POST a /convert, questa funzione viene eseguita. Riceve un JSON 
@router.post("/convert")

def convert(req: MayoRequest):
    return convert_with_mayo(req.input_file, req.output_file)
