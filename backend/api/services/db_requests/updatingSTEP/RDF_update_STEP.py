from platform import node

import ifcopenshell
from rdflib import OWL, Graph, Namespace, Literal, RDF, URIRef,RDFS
from pydantic import BaseModel
from typing_extensions import TypedDict
from pathlib import Path

from ....services.db_requests.substitution_file_query import NodeToSubstitute
from ....models.models import PREMIS_NAMESPACE, VIRTUOSO_URL,GRAPH_NAMESPACE, X3D_NAMESPACE, XSD_NAMESPACE,PROV_NAMESPACE,FOAF_NAMESPACE, IFC_NAMESPACE, EXPRESS_NAMESPACE

class NameAndNumber(TypedDict):
    name: str
    number: int

class ExistingProps(TypedDict):
    name: str
    number:int
    visible: bool | None
    display:bool|None
    attrib: str |None
    ifc_class: str | None
    predefined_type: str | None
    object_type: str | None
    psets: dict | None


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
    time: str,
    parents_with_removals: set[str] | None = None
) -> str:


    g = Graph()

    g.bind("x3d", X3D_NAMESPACE)
    g.bind("rdfs", RDFS)
    g.bind("ex", GRAPH_NAMESPACE)
    g.bind("ifc", IFC_NAMESPACE)
    g.bind("express", EXPRESS_NAMESPACE)
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
    g.add((EXPRESS_NAMESPACE.hasString, RDF.type, OWL.DatatypeProperty))
    g.add((EXPRESS_NAMESPACE.hasInteger, RDF.type, OWL.DatatypeProperty))
    g.add((EXPRESS_NAMESPACE.hasDouble, RDF.type, OWL.DatatypeProperty))
    g.add((EXPRESS_NAMESPACE.hasBoolean, RDF.type, OWL.DatatypeProperty))
    g.add((EXPRESS_NAMESPACE.hasHexBinary, RDF.type, OWL.DatatypeProperty))
    g.add((X3D_NAMESPACE.hasAddedEntities, RDF.type, OWL.DatatypeProperty))
    g.add((X3D_NAMESPACE.hasRemovedEntities, RDF.type, OWL.DatatypeProperty))

    # Labels of Fundamental-Node products that gained new descendant entities in
    # this update; collected during the add_node recursion and emitted as flags.
    parents_with_additions: set[str] = set()

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

    def find_node_by_id(node, target_id: str):
        # old_nodes is the existing hierarchy sent by the frontend; it can be a
        # single root dict or a list of roots. Match on the instance name, which
        # is the part of the node id after the namespace '#'.
        if isinstance(node, list):
            for item in node:
                result = find_node_by_id(item, target_id)
                if result:
                    return result
            return None
        if not isinstance(node, dict):
            return None
        node_id = node.get("id", "")
        if "#" in node_id and node_id.split("#")[1] == target_id:
            return node
        for child in node.get("children", []):
            result = find_node_by_id(child, target_id)
            if result:
                return result
        return None

    def get_by_names(items: list[ExistingProps], target: str):
        return next((item for item in items if item["name"] == target), None)

    def nearest_fundamental_label(candidate_labels: list[str]) -> str | None:
        # candidate_labels are ordered root -> ... -> self (self last). Return the
        # nearest (closest to self) label whose metadata is a Fundamental_Node;
        # fall back to the top-most candidate (the product root of this file).
        for lbl in reversed(candidate_labels):
            prop = get_by_names(existing_nodes, lbl)
            if prop and prop.get("attrib") == "Fundamental_Node":
                return lbl
        return candidate_labels[0] if candidate_labels else None

    def add_node(node: GeometryNode, existing_nodes: list[ExistingProps], parent_uri=None, ancestor_labels=None):
        if ancestor_labels is None:
            ancestor_labels = []
        original_name = node.name
        parts = original_name.split(".")
        label = ".".join(parts[:-1])

        old_node = find_node_by_id(old_nodes, original_name) if old_nodes else None
        node_uri = GRAPH_NAMESPACE[original_name]

        if old_node:
            # Unchanged node: its triples already exist in the graph, so we do not
            # rewrite them. We still recurse so that new entities added beneath an
            # unchanged parent are reached and flagged.
            for child in node.children:
                add_node(child, existing_nodes, parent_uri=node_uri, ancestor_labels=ancestor_labels + [label])
            return

        # New node (no match in the old hierarchy) -> this is an addition. Flag the
        # nearest Fundamental-Node ancestor (self included) as having added entities.
        number = int(parts[-1])
        target_label = nearest_fundamental_label(ancestor_labels + [label])
        if target_label is not None:
            parents_with_additions.add(target_label)

        metadata_uri = GRAPH_NAMESPACE[label]

        g.add((metadata_uri, RDF.type, X3D_NAMESPACE.MetadataString))
        g.add((node_uri, X3D_NAMESPACE.hasMetadata, metadata_uri))
        g.add((node_uri, X3D_NAMESPACE.name, Literal(number, datatype=XSD_NAMESPACE.integer)))
        g.add((node_uri, X3D_NAMESPACE.hasParentX3D, file))

        existing_prop = get_by_names(existing_nodes, label)

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

        # IFC metadata inheritance: a new instance of an already-classified
        # component re-emits the same IFC class, predefined/object types, GUID and
        # property sets so the user does not have to re-enter them.
        if existing_prop and existing_prop.get("ifc_class"):
            ifc_class = existing_prop["ifc_class"]
            predefined_type = existing_prop.get("predefined_type")
            object_type = existing_prop.get("object_type")
            psets = existing_prop.get("psets") or {}

            g.add((node_uri, RDF.type, IFC_NAMESPACE[ifc_class]))

            guid_uri = GRAPH_NAMESPACE["GUID_" + original_name]
            g.add((node_uri, IFC_NAMESPACE["globalId_IfcRoot"], guid_uri))
            g.add((guid_uri, RDF.type, IFC_NAMESPACE["IfcGloballyUniqueId"]))
            g.add((guid_uri, RDF.value, Literal(ifcopenshell.guid.new(), datatype=XSD_NAMESPACE.string)))

            name_label_uri = GRAPH_NAMESPACE["Name_" + original_name]
            g.add((node_uri, IFC_NAMESPACE["name_IfcRoot"], name_label_uri))
            g.add((name_label_uri, RDF.type, IFC_NAMESPACE["IfcLabel"]))
            g.add((name_label_uri, RDF.value, Literal(original_name, datatype=XSD_NAMESPACE.string)))

            if predefined_type:
                g.add((node_uri, IFC_NAMESPACE["predefinedType_" + ifc_class], IFC_NAMESPACE[predefined_type]))

            if object_type:
                object_type_uri = GRAPH_NAMESPACE["ObjectType_" + label]
                g.add((object_type_uri, RDF.type, IFC_NAMESPACE["IfcLabel"]))
                g.add((object_type_uri, EXPRESS_NAMESPACE.hasString, Literal(object_type, datatype=XSD_NAMESPACE.string)))
                g.add((node_uri, IFC_NAMESPACE["objectType_IfcObject"], object_type_uri))

            rel_psets_uris = []
            for pset_name, properties in psets.items():
                rel_defines_uri = GRAPH_NAMESPACE[f"IfcRelDefinesByProperties_{label}_{pset_name}"]
                g.add((rel_defines_uri, RDF.type, IFC_NAMESPACE["IfcRelDefinesByProperties"]))
                rel_psets_uris.append(rel_defines_uri)

                rel_defines_guid_uri = GRAPH_NAMESPACE[f"IfcGloballyUniqueId_IRDBP_{label}_{pset_name}"]
                g.add((rel_defines_guid_uri, RDF.type, IFC_NAMESPACE["IfcGloballyUniqueId"]))
                g.add((rel_defines_guid_uri, EXPRESS_NAMESPACE.hasString, Literal(ifcopenshell.guid.new(), datatype=XSD_NAMESPACE.string)))
                g.add((rel_defines_uri, IFC_NAMESPACE["globalId_IfcRoot"], rel_defines_guid_uri))

                pset_uri = GRAPH_NAMESPACE[f"IfcPropertySet_{label}_{pset_name}"]
                g.add((pset_uri, RDF.type, IFC_NAMESPACE["IfcPropertySet"]))
                g.add((rel_defines_uri, IFC_NAMESPACE["relatingPropertyDefinition_IfcRelDefinesByProperties"], pset_uri))
                g.add((pset_uri, IFC_NAMESPACE["definesOccurrence_IfcPropertySetDefinition"], rel_defines_uri))

                pset_guid_uri = GRAPH_NAMESPACE[f"IfcGloballyUniqueId_PSet_{label}_{pset_name}"]
                g.add((pset_guid_uri, RDF.type, IFC_NAMESPACE["IfcGloballyUniqueId"]))
                g.add((pset_guid_uri, EXPRESS_NAMESPACE.hasString, Literal(ifcopenshell.guid.new(), datatype=XSD_NAMESPACE.string)))
                g.add((pset_uri, IFC_NAMESPACE["globalId_IfcRoot"], pset_guid_uri))

                pset_label_uri = GRAPH_NAMESPACE[f"IfcLabel_{pset_name}"]
                g.add((pset_label_uri, RDF.type, IFC_NAMESPACE["IfcLabel"]))
                g.add((pset_label_uri, EXPRESS_NAMESPACE.hasString, Literal(pset_name, datatype=XSD_NAMESPACE.string)))
                g.add((pset_uri, IFC_NAMESPACE["name_IfcRoot"], pset_label_uri))

                for prop_name, prop_data in properties.items():
                    if not isinstance(prop_data, dict):
                        continue
                    prop_value = prop_data.get("value")
                    ifc_value = prop_data.get("ifc_value")
                    data_type = prop_data.get("data_type")
                    if not ifc_value or not data_type or prop_value is None or prop_value == "":
                        continue

                    prop_uri = GRAPH_NAMESPACE[f"IfcPropertySingleValue_{label}_{pset_name}_{prop_name}"]
                    g.add((prop_uri, RDF.type, IFC_NAMESPACE["IfcPropertySingleValue"]))
                    g.add((pset_uri, IFC_NAMESPACE["hasProperties_IfcPropertySet"], prop_uri))
                    g.add((prop_uri, IFC_NAMESPACE["partOfPset_IfcPropertySingleValue"], pset_uri))

                    prop_name_id_uri = GRAPH_NAMESPACE[f"IfcIdentifier_{prop_name}"]
                    g.add((prop_name_id_uri, RDF.type, IFC_NAMESPACE["IfcIdentifier"]))
                    g.add((prop_name_id_uri, EXPRESS_NAMESPACE.hasString, Literal(prop_name, datatype=XSD_NAMESPACE.string)))
                    g.add((prop_uri, IFC_NAMESPACE["name_IfcProperty"], prop_name_id_uri))

                    ifc_value_uri = GRAPH_NAMESPACE[f"{ifc_value}_{label}_{pset_name}_{prop_name}"]
                    g.add((ifc_value_uri, RDF.type, IFC_NAMESPACE[ifc_value]))
                    g.add((prop_uri, IFC_NAMESPACE["nominalValue_IfcPropertySingleValue"], ifc_value_uri))

                    if data_type == "STRING":
                        g.add((ifc_value_uri, EXPRESS_NAMESPACE.hasString, Literal(str(prop_value), datatype=XSD_NAMESPACE.string)))
                    elif data_type == "INTEGER":
                        g.add((ifc_value_uri, EXPRESS_NAMESPACE.hasInteger, Literal(int(prop_value), datatype=XSD_NAMESPACE.integer)))
                    elif data_type in ("DOUBLE", "REAL"):
                        g.add((ifc_value_uri, EXPRESS_NAMESPACE.hasDouble, Literal(float(prop_value), datatype=XSD_NAMESPACE.double)))
                    elif data_type == "BOOLEAN":
                        bool_val = prop_value if isinstance(prop_value, bool) else str(prop_value).lower() == "true"
                        g.add((ifc_value_uri, EXPRESS_NAMESPACE.hasBoolean, Literal(bool_val, datatype=XSD_NAMESPACE.boolean)))
                    elif data_type == "HEX_BINARY":
                        g.add((ifc_value_uri, EXPRESS_NAMESPACE.hasHexBinary, Literal(str(prop_value), datatype=XSD_NAMESPACE.hexBinary)))

            for rel in rel_psets_uris:
                g.add((rel, IFC_NAMESPACE["relatedObjects_IfcRelDefinesByProperties"], node_uri))
                g.add((node_uri, IFC_NAMESPACE["isDefinedBy_IfcObject"], rel))

        # Recurse
        for child in node.children:
            add_node(child, existing_nodes, parent_uri=node_uri, ancestor_labels=ancestor_labels + [label])

    for root in hierarchy:
        if parent_uri is not None:
            add_node(root, existing_nodes, parent_uri=URIRef(parent_uri))
        else:
            add_node(root, existing_nodes)

    # Emit the change-review flags on the affected products' metadata URIs.
    # Presence-only semantics: a flag triple exists only when that change occurred.
    for label in parents_with_additions:
        g.add((GRAPH_NAMESPACE[label], X3D_NAMESPACE.hasAddedEntities, Literal(True, datatype=XSD_NAMESPACE.boolean)))
    for label in (parents_with_removals or set()):
        g.add((GRAPH_NAMESPACE[label], X3D_NAMESPACE.hasRemovedEntities, Literal(True, datatype=XSD_NAMESPACE.boolean)))

    return g.serialize(format="nt")
