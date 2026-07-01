
import subprocess
import os
import shutil
from pathlib import Path


def _find_gltfpack() -> str:
    """Locate the gltfpack executable across environments.

    Order: an explicit GLTFPACK_EXE override, then PATH (the Docker backend
    image installs the standalone binary to /usr/local/bin), then the
    frontend's npm-installed gltfpack (host dev, where `npm install` in
    frontend/ provides node_modules/.bin/gltfpack).
    """
    env_exe = os.getenv("GLTFPACK_EXE")
    if env_exe and Path(env_exe).exists():
        return env_exe

    on_path = shutil.which("gltfpack")
    if on_path:
        return on_path

    project_root = Path(__file__).resolve().parents[4]
    gltfpack_name = "gltfpack.cmd" if os.name == "nt" else "gltfpack"
    candidate = project_root / "frontend" / "node_modules" / ".bin" / gltfpack_name
    if candidate.exists():
        return str(candidate)

    raise FileNotFoundError(
        "gltfpack not found. Set GLTFPACK_EXE, install it on PATH, or run "
        "`npm install` in frontend/."
    )


def compress_gltf(input_path, output_path):
    gltfpack_path = _find_gltfpack()

    output_path = str(output_path).strip()
    if not output_path:
        raise ValueError("output_path is empty")

    output_ext = Path(output_path).suffix.lower()
    if output_ext not in {".gltf", ".glb"}:
        output_path = f"{output_path}.glb"

    cmd = [
        str(gltfpack_path),
        "-i", input_path,
        "-o", output_path,
        "-c", "-tc", "-kn", "-km","-noq"
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    print("STDOUT:", result.stdout)
    print("STDERR:", result.stderr)
    print("Return code:", result.returncode)
