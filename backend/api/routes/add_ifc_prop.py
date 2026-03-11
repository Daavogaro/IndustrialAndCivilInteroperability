from fastapi import APIRouter
from pydantic import BaseModel
import requests
from rdflib import  Graph, Namespace, Literal, RDF, URIRef
import ifcopenshell
from ..services.db_requests.import_in_DB import import_to_db
from ..models.models import VIRTUOSO_URL,GRAPH_NAMESPACE, IFC_NAMESPACE, XSD_NAMESPACE

router = APIRouter()

class IFCProps(BaseModel):
    graph: str
    metadata: str
    ifc_class: str
    predefined_type: str
    userdefined_type: str|None


@router.post("/add-ifc-properties")
async def add_ifc_properties(request: IFCProps):
    graph = request.graph
    metadata = request.metadata
    ifc_class = request.ifc_class
    predefined_type = request.predefined_type
    userdefined_type = request.userdefined_type

    metadata_select_query = f"""
    PREFIX x3d: <https://www.web3d.org/specifications/X3dOntology4.0#>
    PREFIX XSD_NAMESPACE: <http://www.w3.org/2001/XMLSchema#>

    SELECT ?s
    WHERE {{
    GRAPH <{graph}>{{
        ?s x3d:hasMetadata <{metadata}> .}}
    }}
    """
    response = requests.post(
        VIRTUOSO_URL,
        data={"query": metadata_select_query},
        headers={
            "Accept": "application/sparql-results+json"
        }
    )

    response_data = response.json()
    binding = response_data["results"]["bindings"]
    g = Graph()
    object_type_label_uri = None
    if userdefined_type:
        object_type_label_uri = GRAPH_NAMESPACE["ObjectType_" + metadata.split("#")[-1]]
        g.add((object_type_label_uri, RDF.type, IFC_NAMESPACE["IfcLabel"]))
        g.add((object_type_label_uri, RDF.value, Literal(userdefined_type, datatype=XSD_NAMESPACE.string)))
    for bind in binding:
        guid = ifcopenshell.guid.new()
        subject = URIRef(bind["s"]["value"])
        g.add((subject, RDF.type, IFC_NAMESPACE[ifc_class]))
        guid_uri = GRAPH_NAMESPACE["GUID_" + subject.split("#")[-1]]
        g.add((subject, IFC_NAMESPACE["globalId_IfcRoot"], guid_uri))
        g.add((guid_uri, RDF.type, IFC_NAMESPACE["IfcGloballyUniqueId"]))
        g.add((guid_uri, RDF.value, Literal(guid,datatype=XSD_NAMESPACE.string)))
        name_label_uri = GRAPH_NAMESPACE["Name_" + subject.split("#")[-1]]
        g.add((subject, IFC_NAMESPACE["name_IfcRoot"], name_label_uri))
        g.add((name_label_uri, RDF.type, IFC_NAMESPACE["IfcLabel"]))
        g.add((name_label_uri, RDF.value, Literal(subject.split("#")[-1],datatype=XSD_NAMESPACE.string)))
        predefined_type_uri = IFC_NAMESPACE[predefined_type]
        g.add((subject, IFC_NAMESPACE["predefinedType_" + ifc_class], predefined_type_uri))
        if object_type_label_uri:
            g.add((subject, IFC_NAMESPACE["objectType_IfcObject"], object_type_label_uri))
    serialized_graph=g.serialize(format="nt")    
    await import_to_db(None, graph,serialized_graph)
            

    
    return {
        "status": "success",
        "text": f"Added IFC properties for {metadata}"
    }
