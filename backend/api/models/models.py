import os

from rdflib import Namespace


MAYO_EXE = r"C:\Program Files\Fougue\Mayo\mayo-conv.exe"
BLENDER_EXE = r"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe"
INI_FILE = r"C:\Users\Utente\Desktop\IndustrialAndCivilInteroperability\backend\api\services\importing_STEP\mayo-gui.ini"
MAYO_SERVICE_URL = "http://localhost:8000/api/convert"
BLENDER_SERVICE_URL = "http://localhost:8000/api/blender_run_scripts"


STEP_FOLDER = r"C:\Users\Utente\Desktop\IndustrialAndCivilInteroperability\tmp\STEP"
GLTF_FOLDER = r"C:\Users\Utente\Desktop\IndustrialAndCivilInteroperability\tmp\gLTF"
JSON_FOLDER = r"C:\Users\Utente\Desktop\IndustrialAndCivilInteroperability\tmp\JSON"
RDF_FOLDER = r"C:\Users\Utente\Desktop\IndustrialAndCivilInteroperability\tmp\RDF"


VIRTUOSO_HOST = os.getenv("DB_HOST", "localhost")    
VIRTUOSO_URL = f"http://{VIRTUOSO_HOST}:8890/sparql"

GRAPH_NAMESPACE = Namespace("https://elettra2.0#")
X3D_NAMESPACE = Namespace("https://www.web3d.org/specifications/X3dOntology4.0#")
XSD_NAMESPACE = Namespace("http://www.w3.org/2001/XMLSchema#")
IFC_NAMESPACE = Namespace("https://standards.buildingsmart.org/IFC/DEV/IFC4/ADD2_TC1/OWL#")