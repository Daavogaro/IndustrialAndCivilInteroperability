from fastapi import APIRouter
from pydantic import BaseModel
import requests
from ..models.models import VIRTUOSO_URL
from .projects import assert_known_graph
from .add_ifc_prop import (
    _delete_existing_element_properties,
    _delete_existing_port,
)

router = APIRouter()


class URIs(BaseModel):
    graph: str
    metadata: str
    remove_ifc: bool = False


async def _remove_ifc_data(graph: str, metadata: str):
    """Resolve the X3D node(s) carrying `metadata` and strip every IFC-namespace
    triple from them (type, GUID, name, predefinedType, objectType, element psets
    and the nested IfcDistributionPort subtree). Reuses the same delete helpers
    that `add-ifc-properties` uses for its delete-then-insert, so the IFC data is
    removed exactly the way it was written. The X3D structural data is untouched."""
    select_query = f"""
    PREFIX x3d: <https://www.web3d.org/specifications/X3dOntology4.0#>
    SELECT ?s
    WHERE {{
    GRAPH <{graph}> {{
        ?s x3d:hasMetadata <{metadata}> .}}
    }}
    """
    response = requests.post(
        VIRTUOSO_URL,
        data={"query": select_query},
        headers={"Accept": "application/sparql-results+json"},
    )
    bindings = response.json()["results"]["bindings"]
    for bind in bindings:
        subject = bind["s"]["value"]
        await _delete_existing_element_properties(graph, subject)
        await _delete_existing_port(graph, subject)


@router.post("/remove-fundamental-node")
async def remove_fundamental_node(request: URIs):
    assert_known_graph(request.graph)
    graph = request.graph
    metadata = request.metadata
    delete_query = f"""
    PREFIX x3d: <https://www.web3d.org/specifications/X3dOntology4.0#>
    PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

    DELETE {{
    GRAPH <{graph}> {{
        ?s x3d:attrib "Fundamental_Node"^^xsd:string .
    }}}}
    WHERE {{

        ?s x3d:hasMetadata <{metadata}> ;
        x3d:attrib "Fundamental_Node"^^xsd:string .}}
    """
    requests.post(
        VIRTUOSO_URL,
        data={"update": delete_query},
        headers={"Accept": "application/sparql-results+json"},
    )

    if request.remove_ifc:
        await _remove_ifc_data(graph, metadata)
        return {
            "status": "success",
            "text": f"Removed fundamental node and IFC data for {metadata.split('#')[-1]}",
        }

    return {
        "status": "success",
        "text": f"Removed fundamental node for {metadata.split('#')[-1]}",
    }
