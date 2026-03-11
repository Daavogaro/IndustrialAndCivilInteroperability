from fastapi import APIRouter
from pydantic import BaseModel
import requests
from ..models.models import VIRTUOSO_URL,GRAPH_NAMESPACE, X3D_NAMESPACE

router = APIRouter()

class URIs(BaseModel):
    graph: str
    metadata: str

@router.post("/add-fundamental-node")
async def add_fundamental_node(request: URIs):
    graph = request.graph
    metadata = request.metadata
    insert_query = f"""
    PREFIX x3d: <https://www.web3d.org/specifications/X3dOntology4.0#>
    PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

    INSERT {{
    GRAPH <{graph}> {{
        ?s x3d:attrib "Fundamental_Node"^^xsd:string .
    }}}}
    WHERE {{
    
        ?s x3d:hasMetadata <{metadata}> .}}
    """
    response = requests.post(
        VIRTUOSO_URL,
        data={"update": insert_query},
        headers={
            "Accept": "application/sparql-results+json"
        }
    )
    
    return {
        "status": "success",
        "text": f"Updated fundamental node for {metadata.split('#')[-1]}",
        
    }
