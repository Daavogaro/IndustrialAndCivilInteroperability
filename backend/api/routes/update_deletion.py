from fastapi import APIRouter
import requests
from ..models.models import VIRTUOSO_URL
from .projects import assert_known_graph

router = APIRouter()

from pydantic import BaseModel

class UpdateDeletionRequest(BaseModel):
    metadata: str
    toBeDeleted: bool
    graph: str


@router.post("/update-deletion")
async def update_deletion(request: UpdateDeletionRequest):
    assert_known_graph(request.graph)
    metadata = request.metadata
    toBeDeleted = request.toBeDeleted
    graph = request.graph

    deletion_query = f"""
    PREFIX x3d: <https://www.web3d.org/specifications/X3dOntology4.0#>
    DELETE {{
    GRAPH <{graph}> {{
        ?s x3d:visible ?o .}}}}
    WHERE {{

        ?s x3d:hasMetadata <{metadata}> ;
        x3d:visible ?o .
        }}
    """
    boolean_value = "false" if toBeDeleted else "true"
    insert_query = f"""
    PREFIX x3d: <https://www.web3d.org/specifications/X3dOntology4.0#>
    PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

    INSERT {{
    GRAPH <{graph}> {{
        ?s x3d:visible "{boolean_value}"^^xsd:boolean .
    }}}}
    WHERE {{

        ?s x3d:hasMetadata <{metadata}> .}}
    """

    requests.post(
        VIRTUOSO_URL,
        data={"update": deletion_query},
        headers={"Accept": "application/sparql-results+json"},
    )
    requests.post(
        VIRTUOSO_URL,
        data={"update": insert_query},
        headers={"Accept": "application/sparql-results+json"},
    )

    return {
        "status": "success",
        "text": f"Updated deletion for {metadata.split('#')[-1]}",
    }
