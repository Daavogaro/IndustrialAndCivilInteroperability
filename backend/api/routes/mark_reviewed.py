from fastapi import APIRouter
import requests
from pydantic import BaseModel

from ..models.models import VIRTUOSO_URL
from .projects import assert_known_graph

router = APIRouter()


class MarkReviewedRequest(BaseModel):
    graph: str
    metadata: str  # full metadata URI, e.g. https://elettra2.0#Motor


@router.post("/mark-reviewed")
async def mark_reviewed(request: MarkReviewedRequest):
    assert_known_graph(request.graph)
    graph = request.graph
    metadata = request.metadata

    # Clear the obsolescence markers for every instance of this product in the
    # active project graph ("all at once"). Other projects keep their markers
    # until reviewed in their own inventory.
    removed_query = f"""
    PREFIX x3d: <https://www.web3d.org/specifications/X3dOntology4.0#>
    DELETE {{
    GRAPH <{graph}> {{
        ?s x3d:hasRemovedEntities ?r .}}}}
    WHERE {{
        ?s x3d:hasMetadata <{metadata}> ;
        x3d:hasRemovedEntities ?r .
        }}
    """
    added_query = f"""
    PREFIX x3d: <https://www.web3d.org/specifications/X3dOntology4.0#>
    DELETE {{
    GRAPH <{graph}> {{
        ?s x3d:hasAddedEntities ?a .}}}}
    WHERE {{
        ?s x3d:hasMetadata <{metadata}> ;
        x3d:hasAddedEntities ?a .
        }}
    """

    requests.post(
        VIRTUOSO_URL,
        data={"update": removed_query},
        headers={"Accept": "application/sparql-results+json"},
    )
    requests.post(
        VIRTUOSO_URL,
        data={"update": added_query},
        headers={"Accept": "application/sparql-results+json"},
    )

    return {
        "status": "success",
        "text": f"Marked {metadata.split('#')[-1]} as reviewed",
    }
