"""Re-import RDF generation for the STEP *update* flow.

Unlike the initial upload (``RDF_conversion.convert_hierarchy_in_rdf``), the
graph already contains triples for the nodes that persist across the update.
The substitution machinery in ``gltf_update_STEP`` reuses the existing instance
numbers for matching labels, so a node whose name is in ``old_node_names``
already has all its triples (including IFC, which carries randomly-generated
GUIDs that must NOT be regenerated). We therefore emit triples **only for
genuinely new nodes**, while still recursing so that edges from persisting
parents to new children are written.

The File node's provenance was removed by ``delete_remaining_nodes_sparql``, so
it is re-added here.
"""

import ifcopenshell
from pathlib import Path
from rdflib import OWL, Graph, Literal, RDF, URIRef, RDFS

from ....models.models import (
    PREMIS_NAMESPACE,
    GRAPH_NAMESPACE,
    X3D_NAMESPACE,
    XSD_NAMESPACE,
    PROV_NAMESPACE,
    FOAF_NAMESPACE,
    IFC_NAMESPACE,
    EXPRESS_NAMESPACE,
)
from ....services.importing_STEP.RDF_conversion import ExistingProps, GeometryNode


def rdf_update_step(
    hierarchy: list[GeometryNode],
    existing_nodes: list[ExistingProps],
    old_node_names: set[str],
    changed_fundamental_labels: set[str],
    fileName: str,
    fileURL: str,
    ownerFirstName: str,
    ownerLastName: str,
    time: str,
    parent_uri: str | None = None,
) -> str:

    g = Graph()

    g.bind("x3d", X3D_NAMESPACE)
    g.bind("rdfs", RDFS)
    g.bind("ex", GRAPH_NAMESPACE)
    g.bind("ifc", IFC_NAMESPACE)
    g.bind("express", EXPRESS_NAMESPACE)

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
    # New obsolescence markers (declared so the ontology stays consistent).
    g.add((X3D_NAMESPACE.hasRemovedEntities, RDF.type, OWL.DatatypeProperty))
    g.add((X3D_NAMESPACE.hasAddedEntities, RDF.type, OWL.DatatypeProperty))
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

    # Re-add the File node + provenance (removed during the update cleanup).
    file = GRAPH_NAMESPACE[fileName]
    g.add((file, RDF.type, PREMIS_NAMESPACE.File))
    g.add((file, PROV_NAMESPACE.generatedAtTime, Literal(time, datatype=XSD_NAMESPACE.dateTime)))
    storage_location = URIRef(Path(fileURL).as_uri())
    g.add((file, PREMIS_NAMESPACE.storedAt, storage_location))
    owner = GRAPH_NAMESPACE[ownerFirstName + "_" + ownerLastName]
    g.add((owner, RDF.type, PREMIS_NAMESPACE.Person))
    g.add((owner, FOAF_NAMESPACE.firstName, Literal(ownerFirstName, datatype=XSD_NAMESPACE.string)))
    g.add((owner, FOAF_NAMESPACE.lastName, Literal(ownerLastName, datatype=XSD_NAMESPACE.string)))
    g.add((file, PROV_NAMESPACE.wasAttributedTo, owner))

    def get_by_names(items: list[ExistingProps], target: str):
        return next((item for item in items if item["name"] == target), None)

    def add_node(node: GeometryNode, parent_uri=None):
        original_name = node.name
        parts = original_name.split(".")
        label = ".".join(parts[:-1])
        number = int(parts[-1])

        node_uri = GRAPH_NAMESPACE[original_name]

        # Always recurse so that new children of persisting parents are emitted
        # with an edge back to this node. But only emit THIS node's triples when
        # it is genuinely new (its name was not in the file before).
        if original_name not in old_node_names:
            metadata_uri = GRAPH_NAMESPACE[label]
            existing_prop = get_by_names(existing_nodes, label)

            g.add((metadata_uri, RDF.type, X3D_NAMESPACE.MetadataString))
            g.add((node_uri, X3D_NAMESPACE.hasMetadata, metadata_uri))
            g.add((node_uri, X3D_NAMESPACE.name, Literal(number, datatype=XSD_NAMESPACE.integer)))
            g.add((node_uri, X3D_NAMESPACE.hasParentX3D, file))

            # Type assignment + visibility/display/attrib reuse
            if node.dimensions is None:
                g.add((node_uri, RDF.type, X3D_NAMESPACE.CADAssembly))
                if existing_prop:
                    if existing_prop["visible"] is not None:
                        g.add((node_uri, X3D_NAMESPACE.visible, Literal(existing_prop["visible"], datatype=XSD_NAMESPACE.boolean)))
                    else:
                        g.add((node_uri, X3D_NAMESPACE.visible, Literal(False, datatype=XSD_NAMESPACE.boolean)))
                    if existing_prop["display"] is not None:
                        g.add((node_uri, X3D_NAMESPACE.bboxDisplay, Literal(existing_prop["display"], datatype=XSD_NAMESPACE.boolean)))
                    if existing_prop["attrib"]:
                        g.add((node_uri, X3D_NAMESPACE.attrib, Literal(existing_prop["attrib"], datatype=XSD_NAMESPACE.string)))
                else:
                    g.add((node_uri, X3D_NAMESPACE.visible, Literal(False, datatype=XSD_NAMESPACE.boolean)))
            else:
                g.add((node_uri, RDF.type, X3D_NAMESPACE.CADPart))
                bbox_value = f"{node.dimensions['x']} {node.dimensions['y']} {node.dimensions['z']}"
                g.add((node_uri, X3D_NAMESPACE.bboxSize, Literal(bbox_value, datatype=XSD_NAMESPACE.string)))
                if existing_prop:
                    if existing_prop["visible"] is not None:
                        g.add((node_uri, X3D_NAMESPACE.visible, Literal(existing_prop["visible"], datatype=XSD_NAMESPACE.boolean)))
                    if existing_prop["display"] is not None:
                        g.add((node_uri, X3D_NAMESPACE.bboxDisplay, Literal(existing_prop["display"], datatype=XSD_NAMESPACE.boolean)))
                    if existing_prop["attrib"]:
                        g.add((node_uri, X3D_NAMESPACE.attrib, Literal(existing_prop["attrib"], datatype=XSD_NAMESPACE.string)))
                else:
                    if node.dimensions['x'] < 0.05 and node.dimensions['y'] < 0.05 and node.dimensions['z'] < 0.05:
                        g.add((node_uri, X3D_NAMESPACE.visible, Literal(False, datatype=XSD_NAMESPACE.boolean)))

            # Parent-child relation (edge to this new node)
            if parent_uri is not None:
                g.add((parent_uri, X3D_NAMESPACE.children, node_uri))
                g.add((node_uri, X3D_NAMESPACE.hasParentCADPart, parent_uri))

            # IFC metadata reuse — skipped for fundamental nodes whose assembly
            # changed (their old IFC must not be carried over; it is re-entered).
            ifc_suppressed = label in changed_fundamental_labels
            if existing_prop and existing_prop.get("ifc_class") and not ifc_suppressed:
                _emit_ifc(g, node_uri, original_name, label, existing_prop)

        # Recurse
        for child in node.children:
            add_node(child, parent_uri=node_uri)

    for root in hierarchy:
        if parent_uri is not None:
            add_node(root, parent_uri=URIRef(parent_uri))
        else:
            add_node(root)

    return g.serialize(format="nt")


def _emit_ifc(g: Graph, node_uri, original_name: str, label: str, existing_prop: ExistingProps) -> None:
    """Reuse an existing node's IFC metadata for a new instance — mirrors the
    IFC block in ``RDF_conversion.convert_hierarchy_in_rdf``.
    """
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
