import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from api.models.models import BASE_DIR, GLB_FOLDER
from api.routes import upload_STEP
from api.routes import mayo_and_gltf
from api.routes import sparql_query
from api.routes import add_child
from api.routes import update_deletion
from api.routes import update_simplification
from api.routes import add_fundamental_node
from api.routes import remove_fundamental_node
from api.routes import add_ifc_prop
from api.routes import gltf_upload
from api.routes import ifc_conversion
from api.services.ifc_conversion import blender
from api.routes import update_STEP
from api.routes import product_inventory
from api.routes import product_hierarchy
from api.routes import projects

# FASTAPi è un framework web per costruire API in Python. In questo file, stiamo creando un'app FastAPI.
app = FastAPI()
# Aggiungere permessi in modo che non ci siano problemi di CORS (Cross-Origin Resource Sharing) quando il frontend React chiama le API del backend.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Un router è un modo per organizzare le rotte in FastAPI. Vuol dire che ogni volta che verrà richiamato il router verrà aggiunto  il prefisso "/api" a tutte le rotte definite in api.router. In questo modo, tutte le rotte definite in api.router saranno accessibili tramite URL che iniziano con "/api".
# Ogni router che usiamo nel backend deve essere incluso in questo file main.py, altrimenti non sarà accessibile. Quindi, se definiamo una nuova rotta in un nuovo file, dobbiamo ricordarci di importare quel file e includere il router qui.
app.include_router(upload_STEP.router, prefix="/api")
app.include_router(mayo_and_gltf.router, prefix="/api")
app.include_router(sparql_query.router, prefix="/api")
app.include_router(add_child.router, prefix="/api")
app.include_router(update_deletion.router, prefix="/api")
app.include_router(update_simplification.router, prefix="/api")
app.include_router(add_fundamental_node.router, prefix="/api")
app.include_router(remove_fundamental_node.router, prefix="/api")
app.include_router(add_ifc_prop.router, prefix="/api")
app.include_router(ifc_conversion.router, prefix="/api")
app.include_router(blender.router, prefix="/api")
app.include_router(gltf_upload.router, prefix="/api")
app.include_router(update_STEP.router, prefix="/api")
app.include_router(product_inventory.router, prefix="/api")
app.include_router(product_hierarchy.router, prefix="/api")
app.include_router(projects.router, prefix="/api")

# Serve generated files (GLB for the 3D viewer, IFC, etc.) straight from tmp/.
# gltf_upload.py hands the frontend URLs like /api/static/projects/<id>/GLB/x.glb
# and /api/glb/x.glb, so both mounts must exist. Absolute paths are used because
# the working dir is /app/backend while tmp/ lives at /app/tmp.
TMP_DIR = str(BASE_DIR / "tmp")
os.makedirs(GLB_FOLDER, exist_ok=True)  # non-project GLB dir may not exist yet
app.mount("/api/glb", StaticFiles(directory=GLB_FOLDER), name="glb")
app.mount("/api/static", StaticFiles(directory=TMP_DIR), name="static")


