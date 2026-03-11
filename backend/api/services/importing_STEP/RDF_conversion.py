from rdflib import OWL, Graph, Namespace, Literal, RDF, URIRef,RDFS
from pydantic import BaseModel
from typing_extensions import TypedDict
from ...models.models import VIRTUOSO_URL,GRAPH_NAMESPACE, X3D_NAMESPACE, XSD_NAMESPACE

class NameAndNumber(TypedDict):
    name: str
    number: int

class Dimensions(TypedDict):
    x: float
    y: float
    z: float

class GeometryNode(BaseModel):
    name: str
    dimensions: Dimensions | None
    children: list['GeometryNode']

def convert_hierarchy_in_rdf(
    hierarchy: list[GeometryNode],
    parent_uri: str|None,
    nameAndNumberList: list[NameAndNumber],
    graphName: str,
    fileName: str,
    fileURL: str
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
    
    urlObjectNode_uri = GRAPH_NAMESPACE[fileName]
    g.add((urlObjectNode_uri, RDF.type, X3D_NAMESPACE.X3DUrlObject))
    g.add((urlObjectNode_uri, URIRef(str(X3D_NAMESPACE) + "url"), Literal(fileURL, datatype=XSD_NAMESPACE.string)))


    def add_node(node: GeometryNode, nameAndNumberList: list[NameAndNumber],parent_uri=None):
        original_name = node.name
        parts = node.name.split(".")
        label= ".".join(parts[:-1]) if len(parts) > 1 else original_name
        number = 1
        def get_by_name(items: list[NameAndNumber], target: str) -> NameAndNumber | None:
            return next((item for item in items if item["name"] == target), None)
        name_and_number = get_by_name(nameAndNumberList, label)
        if name_and_number is not None:
            number = name_and_number["number"] + 1
            name_and_number["number"] = number
        else:
            nameAndNumberList.append({"name": label, "number": number})   

        node_uri = GRAPH_NAMESPACE[label+"."+str(number)]
        metadata_uri = GRAPH_NAMESPACE[label]
        g.add((metadata_uri, RDF.type, X3D_NAMESPACE.MetadataString))
        g.add((node_uri, X3D_NAMESPACE.hasMetadata, metadata_uri))
        g.add((node_uri, X3D_NAMESPACE.name, Literal(str(number), datatype=XSD_NAMESPACE.string)))
        # TODO Da capire perchè cazzo non funziona
        g.add((node_uri, X3D_NAMESPACE.hasParentX3D, urlObjectNode_uri))
        # Da capire se questa dopo serve veramente
        # g.add((metadata_uri, X3D_NAMESPACE.reference, Literal(original_name, datatype=XSD.string)))

        # Type assignment
        if node.dimensions is None:
            g.add((node_uri, RDF.type, X3D_NAMESPACE.CADAssembly))
            g.add((node_uri, X3D_NAMESPACE.visible, Literal(False,datatype=XSD_NAMESPACE.string)))
        else:
            g.add((node_uri, RDF.type, X3D_NAMESPACE.CADPart))

            bbox_value = f"{node.dimensions['x']} {node.dimensions['y']} {node.dimensions['z']}"
            g.add((node_uri, X3D_NAMESPACE.bboxSize, Literal(bbox_value, datatype=XSD_NAMESPACE.string)))
            # TODO Adesso teniamo la soglia per nascondere i nodi per tutti gli oggetti, ma bisogna ricordarsi che quando un nodo si trasforma in un fundamental node bisogna eliminare questa proprietà
            if node.dimensions['x'] <0.05 and node.dimensions['y'] <0.05 and node.dimensions['z'] <0.05:
                g.add((node_uri, X3D_NAMESPACE.visible, Literal(False, datatype=XSD_NAMESPACE.string)))

        # Parent-child relation
        if parent_uri is not None:
            g.add((parent_uri, X3D_NAMESPACE.children, node_uri))
            g.add((node_uri, X3D_NAMESPACE.hasParentCADPart, parent_uri))

        # Recurse
        for child in node.children:
            add_node(child, nameAndNumberList, parent_uri=node_uri)

    for root in hierarchy:
        if parent_uri is not None:
            add_node(root, nameAndNumberList, parent_uri=URIRef(parent_uri))
        else:
            add_node(root, nameAndNumberList)

    return g.serialize(format="nt")
