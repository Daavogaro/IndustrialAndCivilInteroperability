import os

from fastapi import APIRouter
from pydantic import BaseModel
import requests
from rdflib import Graph, Namespace, Literal, RDF, URIRef

from ..models.models import VIRTUOSO_URL,GRAPH_NAMESPACE, X3D_NAMESPACE

from ..services.db_requests.name_and_number import name_and_number_query
from ..services.importing_STEP.RDF_conversion import NameAndNumber

router = APIRouter()

class URIs(BaseModel):
    graph: str
    child: str
    parent: str|None

@router.post("/add-child")
async def add_child(request: URIs):
    g = Graph()
    g.bind("ex", GRAPH_NAMESPACE)
    nameAndNumberList = await name_and_number_query()
    number = 1
    
    def get_by_name(items: list[NameAndNumber], target: str) -> NameAndNumber | None:
        return next((item for item in items if item["name"] == target), None)
    name_and_number = get_by_name(nameAndNumberList, request.child)
    if name_and_number is not None:
        number = name_and_number["number"] + 1
        name_and_number["number"] = number
    else:
        nameAndNumberList.append({"name": request.child, "number": 1})
    child_uri = GRAPH_NAMESPACE[request.child+"."+str(number)]
    metadata_uri = GRAPH_NAMESPACE[request.child]
    g.add((child_uri, RDF.type, X3D_NAMESPACE.CADAssembly))
    g.add((child_uri, X3D_NAMESPACE.visible, Literal(False,datatype=X3D_NAMESPACE.boolean)))
    g.add((child_uri, X3D_NAMESPACE.name, Literal(str(number))))
    g.add((metadata_uri, RDF.type, X3D_NAMESPACE.MetadataString))
    g.add((child_uri, X3D_NAMESPACE.hasMetadata, metadata_uri))
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
