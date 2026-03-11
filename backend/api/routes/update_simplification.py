from fastapi import APIRouter
import requests
from ..models.models import VIRTUOSO_URL
# Per ogni chiamata dobbiamo creare un Router.
router = APIRouter()

from pydantic import BaseModel

class UpdateSimplificationRequest(BaseModel):
    metadata: str
    toBeSimplified: bool   

@router.post("/update-simplification")
async def update_simplification(request: UpdateSimplificationRequest):
    metadata = request.metadata
    toBeSimplified = request.toBeSimplified

    deletion_query = f"""
    PREFIX x3d: <https://www.web3d.org/specifications/X3dOntology4.0#> 
    DELETE {{
    GRAPH <http://localhost:8890/Elettra2/> {{
        ?s x3d:bboxDisplay ?o .}}}}
    WHERE {{
    
        ?s x3d:hasMetadata <{metadata}> ;
        x3d:bboxDisplay ?o .
        }}
    """
    boolean_value = "true" if toBeSimplified else "false"
    insert_query = f"""
    PREFIX x3d: <https://www.web3d.org/specifications/X3dOntology4.0#>
    PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

    INSERT {{
    GRAPH <http://localhost:8890/Elettra2/> {{
        ?s x3d:bboxDisplay "{boolean_value}"^^xsd:boolean .
    }}}}
    WHERE {{
    
        ?s x3d:hasMetadata <{metadata}> .}}
    """

    response = requests.post(
        VIRTUOSO_URL,
        data={"update": deletion_query},
        headers={
            "Accept": "application/sparql-results+json"
        }
    )
    response = requests.post(
        VIRTUOSO_URL,
        data={"update": insert_query},
        headers={
            "Accept": "application/sparql-results+json"
        }
    )
    
    return {
        "status": "success",
        "text": f"Updated simplification for {metadata.split('#')[-1]}",
        
    }
