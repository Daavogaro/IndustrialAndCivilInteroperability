
import subprocess
import os
from pathlib import Path

def compress_gltf(input_path, output_path):
    project_root = Path(__file__).resolve().parents[4]
    frontend_dir = project_root / "frontend"
    gltfpack_name = "gltfpack.cmd" if os.name == "nt" else "gltfpack"
    gltfpack_path = frontend_dir / "node_modules" / ".bin" / gltfpack_name

    if not gltfpack_path.exists():
        raise FileNotFoundError(f"gltfpack not found at: {gltfpack_path}")

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
        "-c", "-tc", "-kn", "-km"
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    print("STDOUT:", result.stdout)
    print("STDERR:", result.stderr)
    print("Return code:", result.returncode)
