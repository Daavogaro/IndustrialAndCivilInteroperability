from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel
import os
import subprocess
from ...models.models import BLENDER_EXE

router = APIRouter()


class BlenderRequest(BaseModel):
    scripts: list[str]  # list of script paths
    args: list[list[str]] = None  # optional args for each script

def run_blender_script(script: str, script_args: list[str] | None = None, on_output=None):
    if script_args is None:
        script_args = []

    script_path = os.path.abspath(script)
    cmd = [BLENDER_EXE, "--python", script_path, "--", *script_args]
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    output_lines: list[str] = []

    try:
        if process.stdout is not None:
            for line in process.stdout:
                stripped_line = line.rstrip()
                if not stripped_line:
                    continue

                output_lines.append(stripped_line)
                print(f"[{script} OUTPUT] {stripped_line}")
                if on_output is not None:
                    on_output(stripped_line)
    finally:
        if process.stdout is not None:
            process.stdout.close()

    return_code = process.wait()
    print(f"{script} finished with return code {return_code}")

    if return_code != 0:
        recent_output = "\n".join(output_lines[-10:])
        raise RuntimeError(f"Blender script failed: {script}\n{recent_output}")


def run_blender_scripts(scripts: list[str], args: list[list[str]] = None):
    if args is None:
        args = [[] for _ in scripts]

    for script, script_args in zip(scripts, args):
        run_blender_script(script, script_args)

@router.post("/blender_run_scripts")
def run_scripts(request: BlenderRequest, background_tasks: BackgroundTasks):
    if len(request.scripts) != len(request.args or request.scripts):
        raise HTTPException(status_code=400, detail="scripts and args must have the same length")

    background_tasks.add_task(run_blender_scripts, request.scripts, request.args)
    return {"status": "started"}