import os

from rdflib import Namespace
from pathlib import Path


MAYO_EXE = r"C:\Program Files\Fougue\Mayo\mayo-conv.exe"
BLENDER_EXE = r"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe"

MAYO_SERVICE_URL = "http://localhost:8000/api/convert"
BLENDER_SERVICE_URL = "http://localhost:8000/api/blender_run_scripts"

BASE_DIR = Path(__file__).resolve().parents[3]

INI_FILE = BASE_DIR / "backend" / "api" / "services" / "importing_STEP" / "mayo-gui.ini"

STEP_FOLDER = str(BASE_DIR / "tmp" / "STEP")
GLTF_FOLDER = str(BASE_DIR / "tmp" / "gLTF")
GLB_FOLDER = str(BASE_DIR / "tmp" / "GLB")
JSON_FOLDER = str(BASE_DIR / "tmp" / "JSON")
RDF_FOLDER = str(BASE_DIR / "tmp" / "RDF")
IFC_FOLDER = str(BASE_DIR / "tmp" / "IFC")


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