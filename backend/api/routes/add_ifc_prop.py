from fastapi import APIRouter
from pydantic import BaseModel
import requests
from rdflib import  Graph, Namespace, Literal, RDF, URIRef,OWL
import ifcopenshell
from typing import Dict, Any
from ..services.db_requests.import_in_DB import import_to_db, delete_from_db
from ..models.models import VIRTUOSO_URL,GRAPH_NAMESPACE, IFC_NAMESPACE, XSD_NAMESPACE,EXPRESS_NAMESPACE
from datetime import datetime
router = APIRouter()


class DistributionPort(BaseModel):
    system_type: str | None = None
    predefined_type: str | None = None
    flow_direction: str | None = None
    property_sets: Dict[str, Dict[str, Any]] | None = None


class IFCProps(BaseModel):
    graph: str
    metadata: str
    ifc_class: str
    predefined_type: str
    userdefined_type: str|None
    property_sets: Dict[str, Dict[str, Any]] | None = None
    distribution_port: DistributionPort | None = None


def _add_nominal_value(g, ifc_value_uri, data_type, prop_value):
    """Attach a typed literal to a nominal-value individual (same coercion the
    element pset writer uses)."""
    if data_type == "STRING":
        g.add((ifc_value_uri, EXPRESS_NAMESPACE.hasString, Literal(str(prop_value), datatype=XSD_NAMESPACE.string)))
    elif data_type == "DATE":
        dt = datetime.strptime(prop_value, "%Y-%m-%d")
        g.add((ifc_value_uri, EXPRESS_NAMESPACE.hasString, Literal(dt.date().isoformat(), datatype=XSD_NAMESPACE.string)))
    elif data_type == "INTEGER":
        g.add((ifc_value_uri, EXPRESS_NAMESPACE.hasInteger, Literal(int(prop_value), datatype=XSD_NAMESPACE.integer)))
    elif data_type == "DOUBLE" or data_type == "REAL":
        g.add((ifc_value_uri, EXPRESS_NAMESPACE.hasDouble, Literal(float(prop_value), datatype=XSD_NAMESPACE.double)))
    elif data_type == "BOOLEAN":
        bool_value = prop_value if isinstance(prop_value, bool) else str(prop_value).lower() == "true"
        g.add((ifc_value_uri, EXPRESS_NAMESPACE.hasBoolean, Literal(bool_value, datatype=XSD_NAMESPACE.boolean)))
    elif data_type == "HEX_BINARY":
        g.add((ifc_value_uri, EXPRESS_NAMESPACE.hasHexBinary, Literal(str(prop_value), datatype=XSD_NAMESPACE.hexBinary)))


def _port_has_content(dp: DistributionPort) -> bool:
    if dp.system_type or dp.predefined_type or dp.flow_direction:
        return True
    return bool(dp.property_sets)


def _write_port_triples(g, subject, node_name, dp: DistributionPort):
    """Create the IfcDistributionPort + IfcRelNests subtree nested under `subject`
    (an IfcDistributionElement / IfcDistributionControlElement occurrence).

    The port is named "Port_<node_name>" and all pset-related URIs are scoped with
    "Port_<node_name>" so they never collide with the element's own pset URIs."""
    port_uri = GRAPH_NAMESPACE["Port_" + node_name]
    g.add((port_uri, RDF.type, IFC_NAMESPACE["IfcDistributionPort"]))

    # Name -> IfcLabel("Port_<node_name>"), read back with rdf:value (mirrors the
    # element subject's name label).
    port_name = "Port_" + node_name
    port_name_label = GRAPH_NAMESPACE["Name_Port_" + node_name]
    g.add((port_name_label, RDF.type, IFC_NAMESPACE["IfcLabel"]))
    g.add((port_name_label, RDF.value, Literal(port_name, datatype=XSD_NAMESPACE.string)))
    g.add((port_uri, IFC_NAMESPACE["name_IfcRoot"], port_name_label))

    # GlobalId.
    port_guid = GRAPH_NAMESPACE["GUID_Port_" + node_name]
    g.add((port_guid, RDF.type, IFC_NAMESPACE["IfcGloballyUniqueId"]))
    g.add((port_guid, RDF.value, Literal(ifcopenshell.guid.new(), datatype=XSD_NAMESPACE.string)))
    g.add((port_uri, IFC_NAMESPACE["globalId_IfcRoot"], port_guid))

    # Optional attributes (emit a triple only for a non-empty value).
    if dp.system_type:
        g.add((port_uri, IFC_NAMESPACE["systemType_IfcDistributionPort"], IFC_NAMESPACE[dp.system_type]))
    if dp.predefined_type:
        g.add((port_uri, IFC_NAMESPACE["predefinedType_IfcDistributionPort"], IFC_NAMESPACE[dp.predefined_type]))
    if dp.flow_direction:
        g.add((port_uri, IFC_NAMESPACE["flowDirection_IfcDistributionPort"], IFC_NAMESPACE[dp.flow_direction]))

    # IfcRelNests: element (relatingObject) nests the port (relatedObjects).
    rel_uri = GRAPH_NAMESPACE["IfcRelNests_" + node_name]
    g.add((rel_uri, RDF.type, IFC_NAMESPACE["IfcRelNests"]))
    rel_guid = GRAPH_NAMESPACE["GUID_RelNests_" + node_name]
    g.add((rel_guid, RDF.type, IFC_NAMESPACE["IfcGloballyUniqueId"]))
    g.add((rel_guid, RDF.value, Literal(ifcopenshell.guid.new(), datatype=XSD_NAMESPACE.string)))
    g.add((rel_uri, IFC_NAMESPACE["globalId_IfcRoot"], rel_guid))
    g.add((rel_uri, IFC_NAMESPACE["relatingObject_IfcRelNests"], subject))
    g.add((rel_uri, IFC_NAMESPACE["relatedObjects_IfcRelNests"], port_uri))

    # Back-references.
    g.add((subject, IFC_NAMESPACE["isNestedBy_IfcObjectDefinition"], rel_uri))
    g.add((port_uri, IFC_NAMESPACE["nests_IfcObjectDefinition"], rel_uri))

    # Property sets (same triple shape as the element psets, but related to the
    # port and scoped with "Port_<node_name>").
    port_property_sets = dp.property_sets or {}
    for pset_name, properties in port_property_sets.items():
        scope = f"Port_{node_name}_{pset_name}"
        rel_defines_uri = GRAPH_NAMESPACE[f"IfcRelDefinesByProperties_{scope}"]
        g.add((rel_defines_uri, RDF.type, IFC_NAMESPACE["IfcRelDefinesByProperties"]))
        rel_defines_GUID = GRAPH_NAMESPACE[f"IfcGloballyUniqueId_IRDBP_{scope}"]
        g.add((rel_defines_GUID, RDF.type, IFC_NAMESPACE["IfcGloballyUniqueId"]))
        g.add((rel_defines_GUID, EXPRESS_NAMESPACE.hasString, Literal(ifcopenshell.guid.new(), datatype=XSD_NAMESPACE.string)))
        g.add((rel_defines_uri, IFC_NAMESPACE["globalId_IfcRoot"], rel_defines_GUID))

        pset_uri = GRAPH_NAMESPACE[f"IfcPropertySet_{scope}"]
        g.add((pset_uri, RDF.type, IFC_NAMESPACE["IfcPropertySet"]))
        g.add((rel_defines_uri, IFC_NAMESPACE["relatingPropertyDefinition_IfcRelDefinesByProperties"], pset_uri))
        g.add((pset_uri, IFC_NAMESPACE["definesOccurrence_IfcPropertySetDefinition"], rel_defines_uri))
        pset_GUID = GRAPH_NAMESPACE[f"IfcGloballyUniqueId_PSet_{scope}"]
        g.add((pset_GUID, RDF.type, IFC_NAMESPACE["IfcGloballyUniqueId"]))
        g.add((pset_GUID, EXPRESS_NAMESPACE.hasString, Literal(ifcopenshell.guid.new(), datatype=XSD_NAMESPACE.string)))
        g.add((pset_uri, IFC_NAMESPACE["globalId_IfcRoot"], pset_GUID))

        pset_label_name = GRAPH_NAMESPACE[f"IfcLabel_{scope}"]
        g.add((pset_label_name, RDF.type, IFC_NAMESPACE["IfcLabel"]))
        g.add((pset_label_name, EXPRESS_NAMESPACE.hasString, Literal(pset_name, datatype=XSD_NAMESPACE.string)))
        g.add((pset_uri, IFC_NAMESPACE["name_IfcRoot"], pset_label_name))

        # Relate the pset definition to the port.
        g.add((rel_defines_uri, IFC_NAMESPACE["relatedObjects_IfcRelDefinesByProperties"], port_uri))
        g.add((port_uri, IFC_NAMESPACE["isDefinedBy_IfcObject"], rel_defines_uri))

        for prop_name, prop_data in properties.items():
            if not isinstance(prop_data, dict):
                continue

            prop_value = prop_data.get("value")
            ifc_value = prop_data.get("ifc_value")
            data_type = prop_data.get("data_type")

            if not ifc_value or not data_type:
                continue

            if prop_value is None or prop_value == "":
                continue

            prop_uri = GRAPH_NAMESPACE[f"IfcPropertySingleValue_{scope}_{prop_name}"]
            g.add((prop_uri, RDF.type, IFC_NAMESPACE["IfcPropertySingleValue"]))
            g.add((pset_uri, IFC_NAMESPACE["hasProperties_IfcPropertySet"], prop_uri))
            g.add((prop_uri, IFC_NAMESPACE["partOfPset_IfcPropertySingleValue"], pset_uri))

            prop_name_identifier = GRAPH_NAMESPACE[f"IfcIdentifier_Port_{node_name}_{prop_name}"]
            g.add((prop_name_identifier, RDF.type, IFC_NAMESPACE["IfcIdentifier"]))
            g.add((prop_name_identifier, EXPRESS_NAMESPACE.hasString, Literal(prop_name, datatype=XSD_NAMESPACE.string)))
            g.add((prop_uri, IFC_NAMESPACE["name_IfcProperty"], prop_name_identifier))

            ifc_value_uri = GRAPH_NAMESPACE[f"{ifc_value}_{scope}_{prop_name}"]
            g.add((ifc_value_uri, RDF.type, IFC_NAMESPACE[ifc_value]))
            g.add((prop_uri, IFC_NAMESPACE["nominalValue_IfcPropertySingleValue"], ifc_value_uri))
            _add_nominal_value(g, ifc_value_uri, data_type, prop_value)


async def _delete_existing_port(graph: str, subject):
    """Remove any port/nest/port-pset subtree previously nested under `subject`
    so a re-submission stays clean (delete-then-insert).

    Done in two cheap steps to avoid a cartesian-product DELETE (which can hang
    Virtuoso): first collect every resource in the subtree by traversing the
    1:1/1:few structural predicates, then delete all triples that touch those
    resources as subject or object."""
    subject_iri = f"<{subject}>"
    ifc = str(IFC_NAMESPACE)
    collect_query = f"""
    SELECT DISTINCT ?rel ?relGuid ?port ?portName ?portGuid
                    ?relpset ?rpGuid ?pset ?psGuid ?psLabel ?prop ?ident ?nomval
    WHERE {{
      GRAPH <{graph}> {{
        {subject_iri} <{ifc}isNestedBy_IfcObjectDefinition> ?rel .
        OPTIONAL {{ ?rel <{ifc}globalId_IfcRoot> ?relGuid . }}
        OPTIONAL {{
          ?rel <{ifc}relatedObjects_IfcRelNests> ?port .
          OPTIONAL {{ ?port <{ifc}name_IfcRoot> ?portName . }}
          OPTIONAL {{ ?port <{ifc}globalId_IfcRoot> ?portGuid . }}
          OPTIONAL {{
            ?relpset <{ifc}relatedObjects_IfcRelDefinesByProperties> ?port .
            OPTIONAL {{ ?relpset <{ifc}globalId_IfcRoot> ?rpGuid . }}
            OPTIONAL {{
              ?relpset <{ifc}relatingPropertyDefinition_IfcRelDefinesByProperties> ?pset .
              OPTIONAL {{ ?pset <{ifc}globalId_IfcRoot> ?psGuid . }}
              OPTIONAL {{ ?pset <{ifc}name_IfcRoot> ?psLabel . }}
              OPTIONAL {{
                ?pset <{ifc}hasProperties_IfcPropertySet> ?prop .
                OPTIONAL {{ ?prop <{ifc}name_IfcProperty> ?ident . }}
                OPTIONAL {{ ?prop <{ifc}nominalValue_IfcPropertySingleValue> ?nomval . }}
              }}
            }}
          }}
        }}
      }}
    }}
    """
    response = requests.post(
        VIRTUOSO_URL,
        data={"query": collect_query},
        headers={"Accept": "application/sparql-results+json"},
    )
    bindings = response.json()["results"]["bindings"]

    resources = set()
    for row in bindings:
        for value in row.values():
            if value.get("type") in ("uri", "bnode"):
                resources.add(value["value"])

    if not resources:
        return

    values_list = " ".join(f"<{uri}>" for uri in resources)
    delete_template = "?s ?p ?o ."
    # Bind via the subject and object indexes (VALUES) instead of scanning the
    # whole graph: deletes every outgoing triple of each resource plus the
    # element's back-reference to the removed IfcRelNests.
    where_body = f"""
      {{ VALUES ?s {{ {values_list} }} ?s ?p ?o . }}
      UNION
      {{ VALUES ?o {{ {values_list} }} ?s ?p ?o . }}
    """
    await delete_from_db(graph, delete_template, where_body)


async def _delete_existing_element_properties(graph: str, subject):
    """Remove the IFC annotations previously written onto `subject` (its IFC type,
    GUID, name label, predefinedType link, objectType label and every element
    property-set subtree) so a re-submission stays clean (delete-then-insert).

    `subject` is a shared X3D node, so this deletes ONLY the IFC-namespace triples
    and leaves the X3D structural data (hasMetadata, hasParentCADPart, …) intact.
    The port subtree is owned by `_delete_existing_port`; its `isNestedBy` link is
    explicitly excluded here so the two deletes stay independent of each other.

    Done in two cheap steps to avoid a cartesian-product DELETE (which can hang
    Virtuoso): first collect the dependent resources by traversing the 1:1/1:few
    structural predicates, then delete by subject/object index lookups."""
    subject_iri = f"<{subject}>"
    ifc = str(IFC_NAMESPACE)
    rdf_type = "<http://www.w3.org/1999/02/22-rdf-syntax-ns#type>"
    nested_by = f"<{ifc}isNestedBy_IfcObjectDefinition>"
    collect_query = f"""
    SELECT DISTINCT ?guid ?nameLabel ?objType ?rel ?relGuid ?pset ?psGuid ?psLabel ?prop ?ident ?nomval
    WHERE {{
      GRAPH <{graph}> {{
        {{ {subject_iri} <{ifc}globalId_IfcRoot> ?guid . }}
        UNION
        {{ {subject_iri} <{ifc}name_IfcRoot> ?nameLabel . }}
        UNION
        {{ {subject_iri} <{ifc}objectType_IfcObject> ?objType . }}
        UNION
        {{
          {subject_iri} <{ifc}isDefinedBy_IfcObject> ?rel .
          OPTIONAL {{ ?rel <{ifc}globalId_IfcRoot> ?relGuid . }}
          OPTIONAL {{
            ?rel <{ifc}relatingPropertyDefinition_IfcRelDefinesByProperties> ?pset .
            OPTIONAL {{ ?pset <{ifc}globalId_IfcRoot> ?psGuid . }}
            OPTIONAL {{ ?pset <{ifc}name_IfcRoot> ?psLabel . }}
            OPTIONAL {{
              ?pset <{ifc}hasProperties_IfcPropertySet> ?prop .
              OPTIONAL {{ ?prop <{ifc}name_IfcProperty> ?ident . }}
              OPTIONAL {{ ?prop <{ifc}nominalValue_IfcPropertySingleValue> ?nomval . }}
            }}
          }}
        }}
      }}
    }}
    """
    response = requests.post(
        VIRTUOSO_URL,
        data={"query": collect_query},
        headers={"Accept": "application/sparql-results+json"},
    )
    bindings = response.json()["results"]["bindings"]

    resources = set()
    for row in bindings:
        for value in row.values():
            if value.get("type") in ("uri", "bnode"):
                resources.add(value["value"])

    delete_template = "?s ?p ?o ."
    where_parts = []
    if resources:
        values_list = " ".join(f"<{uri}>" for uri in resources)
        # Delete every triple touching a dependent resource (as subject or object):
        # this clears the GUID/name/objectType/pset subtrees and the element's
        # back-references to them (isDefinedBy / relatedObjects).
        where_parts.append(f"{{ VALUES ?s {{ {values_list} }} ?s ?p ?o . }}")
        where_parts.append(f"{{ VALUES ?o {{ {values_list} }} ?s ?p ?o . }}")
    # Delete the element's own outgoing IFC links (globalId/name/objectType/
    # predefinedType_*/isDefinedBy) — index lookup on the subject, no scan. Exclude
    # the port nest link, which `_delete_existing_port` owns.
    where_parts.append(
        f"{{ VALUES ?s {{ {subject_iri} }} ?s ?p ?o ."
        f" FILTER(STRSTARTS(STR(?p), \"{ifc}\") && ?p != {nested_by}) }}"
    )
    # Delete the element's IFC rdf:type (keeping its X3D types).
    where_parts.append(
        f"{{ VALUES ?s {{ {subject_iri} }} VALUES ?p {{ {rdf_type} }} ?s ?p ?o ."
        f" FILTER(STRSTARTS(STR(?o), \"{ifc}\")) }}"
    )
    where_body = "\n      UNION\n      ".join(where_parts)
    await delete_from_db(graph, delete_template, where_body)


@router.post("/add-ifc-properties")
async def add_ifc_properties(request: IFCProps):
    graph = request.graph
    metadata = request.metadata
    ifc_class = request.ifc_class
    predefined_type = request.predefined_type
    userdefined_type = request.userdefined_type
    property_sets = request.property_sets or {}
    distribution_port = request.distribution_port

    


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

        # Clear any IFC properties previously written onto this element so a
        # re-submission stays clean (delete-then-insert) — same logic as the port.
        await _delete_existing_element_properties(graph, subject)

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

        # IfcDistributionPort connector (delete-then-insert per occurrence).
        if distribution_port is not None:
            # Always clear any previously written port subtree so re-submitting a
            # node stays clean (and clearing the section removes the port).
            await _delete_existing_port(graph, subject)
            # Re-create the port only when the user actually filled the section.
            if _port_has_content(distribution_port):
                _write_port_triples(g, subject, subject.split("#")[-1], distribution_port)


    serialized_graph=g.serialize(format="nt")
    await import_to_db(None, graph,serialized_graph)
            

    
    return {
        "status": "success",
        "text": f"Added IFC properties for {metadata}"
    }
