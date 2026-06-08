from platform import node

from rdflib import OWL, Graph, Namespace, Literal, RDF, URIRef,RDFS
from pydantic import BaseModel
from typing_extensions import TypedDict
from pathlib import Path

from ....services.db_requests.substitution_file_query import NodeToSubstitute
from ....models.models import PREMIS_NAMESPACE, VIRTUOSO_URL,GRAPH_NAMESPACE, X3D_NAMESPACE, XSD_NAMESPACE,PROV_NAMESPACE,FOAF_NAMESPACE

class NameAndNumber(TypedDict):
    name: str
    number: int

class ExistingProps(TypedDict):
    name: str
    number:int
    visible: bool | None
    display:bool|None
    attrib: str |None


class Dimensions(TypedDict):
    x: float
    y: float
    z: float

class GeometryNode(BaseModel):
    name: str
    dimensions: Dimensions | None
    children: list['GeometryNode']

def rdf_update_step(
    hierarchy: list[GeometryNode],
    parent_uri: str|None,
    existing_nodes: list[ExistingProps],
    old_nodes: dict,
    fileName: str,
    fileURL: str,
    ownerFirstName: str,
    ownerLastName: str,
    time: str
) -> str:
    

    g = Graph()

    g.bind("x3d", X3D_NAMESPACE)
    g.bind("rdfs", RDFS)
    g.bind("ex", GRAPH_NAMESPACE)
    # Forse queste sarà da toglierle, perchè in teoria dovrebbe bastare importare le ontologie
    g.add((X3D_NAMESPACE.bboxSize, RDF.type, OWL.DatatypeProperty))
    g.add((X3D_NAMESPACE.name, RDF.type, OWL.DatatypeProperty))
    g.add((X3D_NAMESPACE.visible, RDF.type, OWL.DatatypeProperty))
    g.add((X3D_NAMESPACE.bboxDisplay, RDF.type, OWL.DatatypeProperty))
    g.add((URIRef(str(X3D_NAMESPACE) + "url"), RDF.type, OWL.DatatypeProperty))
    g.add((X3D_NAMESPACE.children, RDF.type, OWL.ObjectProperty))
    g.add((X3D_NAMESPACE.hasParentCADPart, RDF.type, OWL.ObjectProperty))
    g.add((X3D_NAMESPACE.hasMetadata, RDF.type, OWL.ObjectProperty))
    g.add((X3D_NAMESPACE.hasParentX3D, RDF.type, OWL.ObjectProperty))
    g.add((X3D_NAMESPACE.attrib, RDF.type, OWL.DatatypeProperty))
    g.add((PREMIS_NAMESPACE.storedAt, RDF.type, OWL.ObjectProperty))
    g.add((PROV_NAMESPACE.generatedAtTime, RDF.type, OWL.DatatypeProperty))
    g.add((FOAF_NAMESPACE.firstName, RDF.type, OWL.DatatypeProperty))
    g.add((FOAF_NAMESPACE.lastName, RDF.type, OWL.DatatypeProperty))
    g.add((PROV_NAMESPACE.wasAttributedTo, RDF.type, OWL.ObjectProperty))
    
    file = GRAPH_NAMESPACE[fileName]
    g.add((file, RDF.type, PREMIS_NAMESPACE.File))
    g.add((file,PROV_NAMESPACE.generatedAtTime, Literal(time, datatype=XSD_NAMESPACE.dateTime)))
    storage_location = URIRef(Path(fileURL).as_uri())
    g.add((file, PREMIS_NAMESPACE.storedAt, storage_location))
    owner = GRAPH_NAMESPACE[ownerFirstName+"_"+ownerLastName]
    g.add((owner, RDF.type, PREMIS_NAMESPACE.Person))
    g.add((owner, FOAF_NAMESPACE.firstName, Literal(ownerFirstName, datatype=XSD_NAMESPACE.string)))
    g.add((owner, FOAF_NAMESPACE.lastName, Literal(ownerLastName, datatype=XSD_NAMESPACE.string)))
    g.add((file,PROV_NAMESPACE.wasAttributedTo, owner))

    def find_node_by_id(node: dict, target_id: str):
        if node["id"].split("#")[1] == target_id:
            return node
        for child in node.get("children", []):
            result = find_node_by_id(child, target_id)
            if result:
                return result
        return None
    
    def add_node(node: GeometryNode, existing_nodes: list[ExistingProps], parent_uri=None):
        original_name = node.name
        
        old_node = find_node_by_id(old_nodes, original_name) if old_nodes else None
        if old_node:
            return
        else:
            parts = original_name.split(".")
            label= ".".join(parts[:-1])
            number = int(parts[-1])
    
            node_uri = GRAPH_NAMESPACE[original_name]
            metadata_uri = GRAPH_NAMESPACE[label]

            g.add((metadata_uri, RDF.type, X3D_NAMESPACE.MetadataString))
            g.add((node_uri, X3D_NAMESPACE.hasMetadata, metadata_uri))
            g.add((node_uri, X3D_NAMESPACE.name, Literal(number, datatype=XSD_NAMESPACE.integer)))
            g.add((node_uri, X3D_NAMESPACE.hasParentX3D, file))

            def get_by_names(items:list[ExistingProps], target: str):
                return next((item for item in items if item["name"] == target), None)
            existing_prop=get_by_names(existing_nodes,label)

            # Type assignment
            if node.dimensions is None:
                g.add((node_uri, RDF.type, X3D_NAMESPACE.CADAssembly))
                if existing_prop:
                    if existing_prop["visible"] is not None:
                        g.add((node_uri, X3D_NAMESPACE.visible, Literal(existing_prop["visible"],datatype=XSD_NAMESPACE.boolean)))
                    else:
                        g.add((node_uri, X3D_NAMESPACE.visible, Literal(False,datatype=XSD_NAMESPACE.boolean)))
                    if existing_prop["display"] is not None:
                        g.add((node_uri, X3D_NAMESPACE.bboxDisplay, Literal(existing_prop["display"],datatype=XSD_NAMESPACE.boolean)))
                    if existing_prop["attrib"]:
                        g.add((node_uri, X3D_NAMESPACE.attrib, Literal(existing_prop["attrib"],datatype=XSD_NAMESPACE.string)))
                else:
                    g.add((node_uri, X3D_NAMESPACE.visible, Literal(False,datatype=XSD_NAMESPACE.boolean)))

            else:
                g.add((node_uri, RDF.type, X3D_NAMESPACE.CADPart))
                bbox_value = f"{node.dimensions['x']} {node.dimensions['y']} {node.dimensions['z']}"
                g.add((node_uri, X3D_NAMESPACE.bboxSize, Literal(bbox_value, datatype=XSD_NAMESPACE.string)))
                # TODO Adesso teniamo la soglia per nascondere i nodi per tutti gli oggetti, ma bisogna ricordarsi che quando un nodo si trasforma in un fundamental node bisogna eliminare questa proprietà
                if existing_prop:
                    if existing_prop["visible"] is not None:
                        g.add((node_uri, X3D_NAMESPACE.visible, Literal(existing_prop["visible"],datatype=XSD_NAMESPACE.boolean)))
                    if existing_prop["display"] is not None:
                        g.add((node_uri, X3D_NAMESPACE.bboxDisplay, Literal(existing_prop["display"],datatype=XSD_NAMESPACE.boolean)))
                    if existing_prop["attrib"]:
                        g.add((node_uri, X3D_NAMESPACE.attrib, Literal(existing_prop["attrib"],datatype=XSD_NAMESPACE.string)))
                else:
                    if node.dimensions['x'] <0.05 and node.dimensions['y'] <0.05 and node.dimensions['z'] <0.05:
                        g.add((node_uri, X3D_NAMESPACE.visible, Literal(False, datatype=XSD_NAMESPACE.boolean)))

            # Parent-child relation
            if parent_uri is not None:
                g.add((parent_uri, X3D_NAMESPACE.children, node_uri))
                g.add((node_uri, X3D_NAMESPACE.hasParentCADPart, parent_uri))

            # Recurse
            for child in node.children:
                add_node(child, existing_nodes, parent_uri=node_uri)

    for root in hierarchy:
        if parent_uri is not None:
            add_node(root, existing_nodes, parent_uri=URIRef(parent_uri))
        else:
            add_node(root, existing_nodes)

    return g.serialize(format="nt")
