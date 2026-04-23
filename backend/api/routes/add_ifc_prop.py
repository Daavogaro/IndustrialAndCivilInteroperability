from fastapi import APIRouter
from pydantic import BaseModel
import requests
from rdflib import  Graph, Namespace, Literal, RDF, URIRef,OWL
import ifcopenshell
from typing import Dict, Any
from ..services.db_requests.import_in_DB import import_to_db
from ..models.models import VIRTUOSO_URL,GRAPH_NAMESPACE, IFC_NAMESPACE, XSD_NAMESPACE,EXPRESS_NAMESPACE
from datetime import datetime
router = APIRouter()

class IFCProps(BaseModel):
    graph: str
    metadata: str
    ifc_class: str
    predefined_type: str
    userdefined_type: str|None
    property_sets: Dict[str, Dict[str, Any]] | None = None


@router.post("/add-ifc-properties")
async def add_ifc_properties(request: IFCProps):
    graph = request.graph
    metadata = request.metadata
    ifc_class = request.ifc_class
    predefined_type = request.predefined_type
    userdefined_type = request.userdefined_type
    property_sets = request.property_sets or {}

    


    metadata_select_query = f"""
    PREFIX x3d: <https://www.web3d.org/specifications/X3dOntology4.0#>
    PREFIX XSD_NAMESPACE: <http://www.w3.org/2001/XMLSchema#>
    PREFIX EXPRESS_NAMESPACE: <https://w3id.org/express#>

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
    g.add((EXPRESS_NAMESPACE.hasString, RDF.type, OWL.DatatypeProperty))
    g.add((EXPRESS_NAMESPACE.hasInteger, RDF.type, OWL.DatatypeProperty))
    g.add((EXPRESS_NAMESPACE.hasDouble, RDF.type, OWL.DatatypeProperty))
    g.add((EXPRESS_NAMESPACE.hasBoolean, RDF.type, OWL.DatatypeProperty))
    g.add((EXPRESS_NAMESPACE.hasHexBinary, RDF.type, OWL.DatatypeProperty))
    object_type_label_uri = None
    if userdefined_type:
        object_type_label_uri = GRAPH_NAMESPACE["ObjectType_" + metadata.split("#")[-1]]
        g.add((object_type_label_uri, RDF.type, IFC_NAMESPACE["IfcLabel"]))
        g.add((object_type_label_uri, EXPRESS_NAMESPACE.hasString, Literal(userdefined_type, datatype=XSD_NAMESPACE.string)))

    rel_psets_uri=[]
    for pset_name, properties in property_sets.items():
        rel_defines_uri = GRAPH_NAMESPACE[f"IfcRelDefinesByProperties_{metadata.split('#')[-1]}_{pset_name}"]
        g.add((rel_defines_uri, RDF.type, IFC_NAMESPACE["IfcRelDefinesByProperties"]))
        rel_psets_uri.append(rel_defines_uri)
        rel_defines_GUID = GRAPH_NAMESPACE[f"IfcGloballyUniqueId_IRDBP_{metadata.split('#')[-1]}_{pset_name}"]
        g.add((rel_defines_GUID, RDF.type, IFC_NAMESPACE["IfcGloballyUniqueId"]))
        g.add((rel_defines_GUID, EXPRESS_NAMESPACE.hasString, Literal(ifcopenshell.guid.new(), datatype=XSD_NAMESPACE.string)))
        g.add((rel_defines_uri, IFC_NAMESPACE["globalId_IfcRoot"], rel_defines_GUID))

        pset_uri = GRAPH_NAMESPACE[f"IfcPropertySet_{metadata.split('#')[-1]}_{pset_name}"]
        g.add((pset_uri, RDF.type, IFC_NAMESPACE["IfcPropertySet"]))
        g.add((rel_defines_uri, IFC_NAMESPACE["relatingPropertyDefinition_IfcRelDefinesByProperties"], pset_uri))
        g.add((pset_uri, IFC_NAMESPACE["definesOccurrence_IfcPropertySetDefinition"], rel_defines_uri))
        pset_GUID = GRAPH_NAMESPACE[f"IfcGloballyUniqueId_PSet_{metadata.split('#')[-1]}_{pset_name}"]
        g.add((pset_GUID, RDF.type, IFC_NAMESPACE["IfcGloballyUniqueId"]))
        g.add((pset_GUID, EXPRESS_NAMESPACE.hasString, Literal(ifcopenshell.guid.new(), datatype=XSD_NAMESPACE.string)))
        g.add((pset_uri, IFC_NAMESPACE["globalId_IfcRoot"], pset_GUID))

        pset_label_name = GRAPH_NAMESPACE[f"IfcLabel_{pset_name}"]
        g.add((pset_label_name, RDF.type, IFC_NAMESPACE["IfcLabel"]))
        g.add((pset_label_name, EXPRESS_NAMESPACE.hasString, Literal(pset_name, datatype=XSD_NAMESPACE.string)))
        g.add((pset_uri, IFC_NAMESPACE["name_IfcRoot"], pset_label_name))

        for prop_name, prop_data in properties.items():
            if not isinstance(prop_data, dict):
                continue

            prop_value = prop_data.get("value")
            ifc_value = prop_data.get("ifc_value")
            data_type = prop_data.get("data_type")

            if not ifc_value or not data_type:
                continue

            if prop_value is not None and prop_value != "":
                prop_uri = GRAPH_NAMESPACE[f"IfcPropertySingleValue_{metadata.split('#')[-1]}_{pset_name}_{prop_name}"]
                g.add((prop_uri, RDF.type, IFC_NAMESPACE["IfcPropertySingleValue"]))
                g.add((pset_uri, IFC_NAMESPACE["hasProperties_IfcPropertySet"], prop_uri))
                g.add((prop_uri, IFC_NAMESPACE["partOfPset_IfcPropertySingleValue"], pset_uri))

                prop_name_identifier = GRAPH_NAMESPACE[f"IfcIdentifier_{prop_name}"]
                g.add((prop_name_identifier, RDF.type, IFC_NAMESPACE["IfcIdentifier"]))
                g.add((prop_name_identifier, EXPRESS_NAMESPACE.hasString, Literal(prop_name, datatype=XSD_NAMESPACE.string)))
                g.add((prop_uri, IFC_NAMESPACE["name_IfcProperty"], prop_name_identifier))

                ifc_value_uri = GRAPH_NAMESPACE[f"{ifc_value}_{metadata.split('#')[-1]}_{pset_name}_{prop_name}"]
                g.add((ifc_value_uri, RDF.type, IFC_NAMESPACE[ifc_value]))
                g.add((prop_uri, IFC_NAMESPACE["nominalValue_IfcPropertySingleValue"], ifc_value_uri))
                if data_type == "STRING":
                    g.add((ifc_value_uri, EXPRESS_NAMESPACE.hasString, Literal(str(prop_value), datatype=XSD_NAMESPACE.string)))
                if data_type == "DATE":
                    dt = datetime.strptime(prop_value, "%Y-%m-%d")
                    iso_format= dt.date().isoformat()
                    g.add((ifc_value_uri, EXPRESS_NAMESPACE.hasString, Literal(iso_format, datatype=XSD_NAMESPACE.string)))
                elif data_type == "INTEGER":
                    g.add((ifc_value_uri, EXPRESS_NAMESPACE.hasInteger, Literal(int(prop_value), datatype=XSD_NAMESPACE.integer)))
                elif data_type == "DOUBLE" or data_type == "REAL":
                    g.add((ifc_value_uri, EXPRESS_NAMESPACE.hasDouble, Literal(float(prop_value), datatype=XSD_NAMESPACE.double)))
                elif data_type == "BOOLEAN":
                    bool_value = prop_value if isinstance(prop_value, bool) else str(prop_value).lower() == "true"
                    g.add((ifc_value_uri, EXPRESS_NAMESPACE.hasBoolean, Literal(bool_value, datatype=XSD_NAMESPACE.boolean)))
                elif data_type == "HEX_BINARY":
                    g.add((ifc_value_uri, EXPRESS_NAMESPACE.hasHexBinary, Literal(str(prop_value), datatype=XSD_NAMESPACE.hexBinary)))
            

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
        for rel in rel_psets_uri:
            g.add((rel, IFC_NAMESPACE["relatedObjects_IfcRelDefinesByProperties"], subject))
            g.add((subject, IFC_NAMESPACE["isDefinedBy_IfcObject"], rel))

        
    serialized_graph=g.serialize(format="nt")    
    await import_to_db(None, graph,serialized_graph)
            

    
    return {
        "status": "success",
        "text": f"Added IFC properties for {metadata}"
    }
