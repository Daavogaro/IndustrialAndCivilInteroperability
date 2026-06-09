from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool
from SPARQLWrapper import SPARQLWrapper, JSON
import urllib.parse
from ..models.models import VIRTUOSO_URL

router = APIRouter()

GRAPH = "http://localhost:8890/Elettra2/"
METADATA_NS = "https://elettra2.0#"


def _get_val(binding: dict, key: str):
    entry = binding.get(key)
    return entry["value"] if entry else None


def _strip_file_uri(val: str | None) -> str:
    if val:
        return val.replace("file:///", "")
    return ""


def _run_all(decoded_label: str) -> dict:
    metadata_uri = f"{METADATA_NS}{decoded_label}"

    sparql = SPARQLWrapper(VIRTUOSO_URL)
    sparql.setReturnFormat(JSON)
    sparql.setTimeout(30)

    # Query 1 — first instance of the Fundamental Node
    q1 = f"""
PREFIX x3d: <https://www.web3d.org/specifications/X3dOntology4.0#>
PREFIX pre: <http://www.loc.gov/premis/rdf/v3/>
SELECT ?root ?cadType ?metadata ?visible ?display ?dimensions ?fileUrl
FROM <{GRAPH}>
WHERE {{
  ?root x3d:hasMetadata <{metadata_uri}> .
  ?root x3d:hasMetadata ?metadata .
  ?root x3d:attrib ?a .
  FILTER(STR(?a) = "Fundamental_Node")
  ?root a ?cadType .
  ?root x3d:name ?num .
  OPTIONAL {{ ?root x3d:visible ?visible . }}
  OPTIONAL {{ ?root x3d:bboxDisplay ?display . }}
  OPTIONAL {{ ?root x3d:bboxSize ?dimensions . }}
  OPTIONAL {{
    ?root x3d:hasParentX3D ?file .
    ?file a pre:File .
    ?file pre:storedAt ?fileUrl .
  }}
  FILTER(STRSTARTS(STR(?cadType), "https://www.web3d.org/specifications/X3dOntology4.0#"))
}}
ORDER BY ?num
LIMIT 1
"""
    sparql.setQuery(q1)
    r1 = sparql.query().convert()
    bindings_1 = r1.get("results", {}).get("bindings", [])
    if not bindings_1:
        raise ValueError("not_found")

    rb = bindings_1[0]
    root_uri = rb["root"]["value"]

    root_record = {
        "uri": root_uri,
        "cadType": rb["cadType"]["value"],
        "metadata": rb["metadata"]["value"],
        "visible": _get_val(rb, "visible"),
        "display": _get_val(rb, "display"),
        "dimensions": _get_val(rb, "dimensions"),
        "attrib": "Fundamental_Node",
        "fileUrl": _strip_file_uri(_get_val(rb, "fileUrl")),
    }

    # Query 2 — all parent→child edges in the subtree
    q2 = f"""
PREFIX x3d: <https://www.web3d.org/specifications/X3dOntology4.0#>
PREFIX pre: <http://www.loc.gov/premis/rdf/v3/>
SELECT ?parent ?child ?cadType ?metadata ?visible ?display ?dimensions ?attrib ?fileUrl
FROM <{GRAPH}>
WHERE {{
  <{root_uri}> x3d:children* ?parent .
  ?parent x3d:children ?child .
  ?child a ?cadType .
  ?child x3d:hasMetadata ?metadata .
  OPTIONAL {{ ?child x3d:visible ?visible . }}
  OPTIONAL {{ ?child x3d:bboxDisplay ?display . }}
  OPTIONAL {{ ?child x3d:bboxSize ?dimensions . }}
  OPTIONAL {{ ?child x3d:attrib ?attrib . }}
  OPTIONAL {{
    ?child x3d:hasParentX3D ?file .
    ?file a pre:File .
    ?file pre:storedAt ?fileUrl .
  }}
  FILTER(STRSTARTS(STR(?cadType), "https://www.web3d.org/specifications/X3dOntology4.0#"))
}}
"""
    sparql.setQuery(q2)
    r2 = sparql.query().convert()
    bindings_2 = r2.get("results", {}).get("bindings", [])

    edges = [
        {
            "parent": b["parent"]["value"],
            "child": b["child"]["value"],
            "cadType": b["cadType"]["value"],
            "metadata": b["metadata"]["value"],
            "visible": _get_val(b, "visible"),
            "display": _get_val(b, "display"),
            "dimensions": _get_val(b, "dimensions"),
            "attrib": _get_val(b, "attrib"),
            "fileUrl": _strip_file_uri(_get_val(b, "fileUrl")),
        }
        for b in bindings_2
    ]

    # Query 3 — IFC class data for subtree nodes
    q3 = f"""
PREFIX x3d: <https://www.web3d.org/specifications/X3dOntology4.0#>
PREFIX ifc: <https://w3id.org/ifc/IFC4X3_ADD2#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
SELECT ?node ?ifcClass ?predefinedType ?objectType
FROM <{GRAPH}>
WHERE {{
  {{ <{root_uri}> x3d:children* ?node . }} UNION {{ BIND(<{root_uri}> AS ?node) }}
  ?node a ?ifcClass .
  ?node x3d:hasMetadata ?metadata .
  ?node ifc:globalId_IfcRoot ?globalId .
  ?globalId rdf:value ?gidValue .
  OPTIONAL {{
    ?node ?p ?predefinedType .
    FILTER(STRSTARTS(STR(?p), "https://w3id.org/ifc/IFC4X3_ADD2#predefinedType_"))
  }}
  OPTIONAL {{
    ?node ifc:objectType_IfcObject ?lbl .
    ?lbl rdf:value ?objectType .
  }}
  FILTER(STRSTARTS(STR(?ifcClass), "https://w3id.org/ifc/IFC4X3_ADD2#"))
}}
"""
    sparql.setQuery(q3)
    r3 = sparql.query().convert()
    bindings_3 = r3.get("results", {}).get("bindings", [])

    ifc_data = [
        {
            "node": b["node"]["value"],
            "ifcClass": b["ifcClass"]["value"],
            "predefinedType": _get_val(b, "predefinedType"),
            "objectType": _get_val(b, "objectType"),
        }
        for b in bindings_3
    ]

    # Query 4 — IFC property sets for subtree nodes
    q4 = f"""
PREFIX x3d: <https://www.web3d.org/specifications/X3dOntology4.0#>
PREFIX ifc: <https://w3id.org/ifc/IFC4X3_ADD2#>
PREFIX express: <https://w3id.org/express#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
SELECT ?node ?psetName ?propName ?propValue ?datatype
FROM <{GRAPH}>
WHERE {{
  {{ <{root_uri}> x3d:children* ?node . }} UNION {{ BIND(<{root_uri}> AS ?node) }}
  ?s a ifc:IfcRelDefinesByProperties .
  ?s ifc:relatedObjects_IfcRelDefinesByProperties ?node .
  ?s ifc:relatingPropertyDefinition_IfcRelDefinesByProperties ?pset .
  ?pset ifc:name_IfcRoot ?lbl .
  ?lbl express:hasString ?psetName .
  ?pset ifc:hasProperties_IfcPropertySet ?prop .
  ?prop ifc:name_IfcProperty ?identifier .
  ?identifier express:hasString ?propName .
  ?prop ifc:nominalValue_IfcPropertySingleValue ?value .
  ?value ?p ?propValue .
  ?p a owl:DatatypeProperty .
  BIND(DATATYPE(?propValue) AS ?datatype)
}}
"""
    sparql.setQuery(q4)
    r4 = sparql.query().convert()
    bindings_4 = r4.get("results", {}).get("bindings", [])

    ifc_pset_data = [
        {
            "node": b["node"]["value"],
            "psetName": b["psetName"]["value"],
            "propName": b["propName"]["value"],
            "propValue": b["propValue"]["value"],
            "datatype": _get_val(b, "datatype") or "",
        }
        for b in bindings_4
    ]

    return {
        "rootUri": root_uri,
        "roots": [root_record],
        "edges": edges,
        "ifcData": ifc_data,
        "ifcPsetData": ifc_pset_data,
    }


@router.get("/product-hierarchy/{label}")
async def product_hierarchy(label: str):
    decoded = urllib.parse.unquote(label).strip()
    if not decoded:
        raise HTTPException(status_code=404, detail="Product not found")
    try:
        return await run_in_threadpool(_run_all, decoded)
    except ValueError as exc:
        if str(exc) == "not_found":
            raise HTTPException(status_code=404, detail="Product not found")
        raise HTTPException(status_code=500, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error querying hierarchy: {exc}")
