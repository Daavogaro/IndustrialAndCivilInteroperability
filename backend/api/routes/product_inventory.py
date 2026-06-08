from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool
from SPARQLWrapper import SPARQLWrapper, JSON
from ..models.models import VIRTUOSO_URL

router = APIRouter()

GRAPH = "http://localhost:8890/Elettra2/"

# TODO: replace hardcoded provenance with a PROV-based SPARQL query when provenance tracking is implemented
_FAKE_EDITOR = "Sergio Mattarella"
_FAKE_EDIT_DATE = "2026-05-14T10:32:00"

_QUERY = f"""
PREFIX x3d: <https://www.web3d.org/specifications/X3dOntology4.0#>
SELECT ?metadata
       (COUNT(DISTINCT ?node) AS ?count)
       (SAMPLE(?cadType) AS ?cadType)
       (SAMPLE(?ifcClass) AS ?ifcClass)
FROM <{GRAPH}>
WHERE {{
  ?node x3d:hasMetadata ?metadata .
  ?node x3d:attrib ?attrib .
  FILTER(STR(?attrib) = "Fundamental_Node")
  ?node a ?cadType .
  FILTER(STRSTARTS(STR(?cadType), "https://www.web3d.org/specifications/X3dOntology4.0#"))
  OPTIONAL {{
    ?node a ?ifcClass .
    FILTER(STRSTARTS(STR(?ifcClass), "https://w3id.org/ifc/IFC4X3_ADD2#"))
  }}
}}
GROUP BY ?metadata
ORDER BY DESC(?count)
"""


def _run_query():
    sparql = SPARQLWrapper(VIRTUOSO_URL)
    sparql.setQuery(_QUERY)
    sparql.setReturnFormat(JSON)
    sparql.setTimeout(20)
    return sparql.query().convert()


def _transform(bindings: list) -> list:
    records = []
    for b in bindings:
        metadata_uri = b["metadata"]["value"]
        cad_type_uri = b["cadType"]["value"]
        ifc_raw = b.get("ifcClass")

        records.append({
            "label": metadata_uri.split("#")[-1],
            "metadata": metadata_uri,
            "count": int(b["count"]["value"]),
            "cadType": cad_type_uri.split("#")[-1],
            "ifcClass": ifc_raw["value"].split("#")[-1] if ifc_raw else None,
            "lastEditor": _FAKE_EDITOR,
            "lastEditDate": _FAKE_EDIT_DATE,
        })
    return records


@router.get("/product-inventory")
async def product_inventory():
    try:
        result = await run_in_threadpool(_run_query)
        bindings = result.get("results", {}).get("bindings", [])
        return _transform(bindings)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error querying inventory: {e}")
