import os

from rdflib import Namespace
from pathlib import Path
from typing import Dict


# Blender executable: resolved on PATH inside the container (default "blender").
# On a Windows host, set the BLENDER_EXE env var to the full blender.exe path.
BLENDER_EXE = os.getenv("BLENDER_EXE", "blender")

BLENDER_SERVICE_URL = "http://localhost:8000/api/blender_run_scripts"

BASE_DIR = Path(__file__).resolve().parents[3]

# Absolute, OS-independent paths to the Blender Python scripts. Built from
# BASE_DIR so they do not depend on the process working directory.
BLENDER_SCRIPT_DIR = BASE_DIR / "backend" / "api" / "services" / "ifc_conversion" / "blender_script"
IMPORT_GLTF_SCRIPT = str(BLENDER_SCRIPT_DIR / "import_gltf.py")

STEP_FOLDER = str(BASE_DIR / "tmp" / "STEP")
GLTF_FOLDER = str(BASE_DIR / "tmp" / "gLTF")
GLB_FOLDER = str(BASE_DIR / "tmp" / "GLB")
JSON_FOLDER = str(BASE_DIR / "tmp" / "JSON")
RDF_FOLDER = str(BASE_DIR / "tmp" / "RDF")
IFC_FOLDER = str(BASE_DIR / "tmp" / "IFC")


def get_project_folders(project_id: str) -> Dict[str, str]:
    base = BASE_DIR / "tmp" / "projects" / project_id
    folders = {
        "step": str(base / "STEP"),
        "gltf": str(base / "gLTF"),
        "glb": str(base / "GLB"),
        "json": str(base / "JSON"),
        "rdf": str(base / "RDF"),
        "ifc": str(base / "IFC"),
    }
    for path in folders.values():
        os.makedirs(path, exist_ok=True)
    return folders


VIRTUOSO_HOST = os.getenv("DB_HOST", "localhost")    
VIRTUOSO_URL = f"http://{VIRTUOSO_HOST}:8890/sparql"

GRAPH_NAMESPACE = Namespace("https://elettra2.0#")
X3D_NAMESPACE = Namespace("https://www.web3d.org/specifications/X3dOntology4.0#")
XSD_NAMESPACE = Namespace("http://www.w3.org/2001/XMLSchema#")
IFC_NAMESPACE = Namespace("https://w3id.org/ifc/IFC4X3_ADD2#")
EXPRESS_NAMESPACE = Namespace("https://w3id.org/express#")
PREMIS_NAMESPACE = Namespace("http://www.loc.gov/premis/rdf/v3/")
PROV_NAMESPACE = Namespace("http://www.w3.org/ns/prov#")
FOAF_NAMESPACE = Namespace("http://xmlns.com/foaf/0.1/")