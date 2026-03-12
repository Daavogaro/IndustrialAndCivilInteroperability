import os

from fastapi import APIRouter
from pydantic import BaseModel
import requests
from rdflib import Graph, Namespace, Literal, RDF, URIRef

from ..models.models import VIRTUOSO_URL,GRAPH_NAMESPACE, X3D_NAMESPACE, XSD_NAMESPACE

from ..services.db_requests.name_and_number import name_and_number_query
from ..services.importing_STEP.RDF_conversion import ExistingProps, NameAndNumber
from ..services.db_requests.existing_nodes import existing_nodes

router = APIRouter()

class URIs(BaseModel):
    graph: str
    child: str
    parent: str|None

@router.post("/add-child")
async def add_child(request: URIs):
    g = Graph()
    g.bind("ex", GRAPH_NAMESPACE)
    exist_nodes=await existing_nodes()
    number = 1
    
    def get_by_name(items: list[ExistingProps], target: str) -> ExistingProps | None:
        return next((item for item in items if item["name"] == target), None)
    existing_props = get_by_name(exist_nodes, request.child)
    if existing_props is not None:
        number = existing_props["number"] + 1
        existing_props["number"] = number
    else:
        exist_nodes.append({"name": request.child, "number": 1})
    child_uri = GRAPH_NAMESPACE[request.child+"."+str(number)]
    metadata_uri = GRAPH_NAMESPACE[request.child]
    g.add((child_uri, RDF.type, X3D_NAMESPACE.CADAssembly))
    g.add((child_uri, X3D_NAMESPACE.name, Literal(str(number))))
    g.add((metadata_uri, RDF.type, X3D_NAMESPACE.MetadataString))
    g.add((child_uri, X3D_NAMESPACE.hasMetadata, metadata_uri))
    if existing_props:
        if existing_props["visible"] is not None:
            g.add((child_uri, X3D_NAMESPACE.visible, Literal(existing_props["visible"],datatype=XSD_NAMESPACE.boolean)))
        else:
            g.add((child_uri, X3D_NAMESPACE.visible, Literal(False,datatype=XSD_NAMESPACE.boolean)))
        if existing_props["display"] is not None:
            g.add((child_uri, X3D_NAMESPACE.bboxDisplay, Literal(existing_props["display"],datatype=XSD_NAMESPACE.boolean)))
        if existing_props["attrib"]:
            g.add((child_uri, X3D_NAMESPACE.attrib, Literal(existing_props["attrib"],datatype=XSD_NAMESPACE.string)))
    else:
        g.add((child_uri, X3D_NAMESPACE.visible, Literal(False,datatype=XSD_NAMESPACE.boolean)))
    
    if request.parent:
        parent_uri = URIRef(request.parent)
        g.add((parent_uri, X3D_NAMESPACE.children, child_uri))
        g.add((child_uri, X3D_NAMESPACE.hasParentCADPart, parent_uri)) 
    triples = g.serialize(format="nt")

    sparql_update = """
  INSERT DATA {
    GRAPH <""" + request.graph + """> {
      """ + triples + """
    }
  }
  """

    try:
        response = requests.post(
            VIRTUOSO_URL,
            data={"update": sparql_update},
        )
        response.raise_for_status()
        return {"status": response.status_code}
    except Exception as e:
        print(f"Error from Virtuoso! Status: {getattr(response, 'status_code', 'N/A')}")
        print(f"Response text: {getattr(response, 'text', str(e))}")
        print(f"Query was: {sparql_update}")
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=f"Virtuoso error: {getattr(response, 'text', str(e))}")
