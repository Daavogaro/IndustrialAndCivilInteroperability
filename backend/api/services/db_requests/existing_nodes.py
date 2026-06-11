from pydantic import BaseModel

from ...routes.sparql_query import sparql_query
from ..importing_STEP.RDF_conversion import ExistingProps

class SparqlRequest(BaseModel):
    query: str


def _parse_int(value: str | None) -> int:
    if value is None:
        return 0
    return int(value)


def _parse_bool(value: str | None) -> bool | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized in {"true", "1"}:
        return True
    if normalized in {"false", "0"}:
        return False
    return None


def _build_psets_from_results(psets_results: dict) -> dict[str, dict]:
    psets_by_node: dict[str, dict] = {}

    for binding in psets_results["results"]["bindings"]:
        raw_name = binding["name"]["value"]
        parts = raw_name.split("#")
        name = "#".join(parts[1:]) if len(parts) > 1 else raw_name

        pset_name = binding.get("psetName", {}).get("value")
        if not pset_name:
            continue

        if name not in psets_by_node:
            psets_by_node[name] = {}
        if pset_name not in psets_by_node[name]:
            psets_by_node[name][pset_name] = {}

        prop_name = binding.get("propName", {}).get("value")
        if not prop_name:
            continue

        prop_value = binding.get("propValue", {}).get("value")
        ifc_value_type = binding.get("ifcValueType", {}).get("value")
        data_type = binding.get("dataType", {}).get("value")

        if prop_value and ifc_value_type and data_type:
            psets_by_node[name][pset_name][prop_name] = {
                "value": prop_value,
                "ifc_value": ifc_value_type,
                "data_type": data_type,
            }

    return psets_by_node


def convert_sparql_results(results_json: dict, psets_by_node: dict[str, dict]) -> list[ExistingProps]:
    output: list[ExistingProps] = []

    for binding in results_json["results"]["bindings"]:
        raw_name = binding["name"]["value"]
        parts = raw_name.split("#")
        name = "#".join(parts[1:]) if len(parts) > 1 else raw_name

        number = int(binding["maxNumber"]["value"])

        visible_any_true = binding.get("visibleAnyTrue", {}).get("value")
        visible_bound_count = binding.get("visibleBoundCount", {}).get("value")
        display_any_true = binding.get("displayAnyTrue", {}).get("value")
        display_bound_count = binding.get("displayBoundCount", {}).get("value")
        attrib = binding.get("attrib", {}).get("value")
        ifc_class = binding.get("ifcClass", {}).get("value") or None
        predefined_type = binding.get("predefinedType", {}).get("value") or None
        object_type = binding.get("objectType", {}).get("value") or None

        visible = None if _parse_int(visible_bound_count) == 0 else _parse_bool(visible_any_true)
        display = None if _parse_int(display_bound_count) == 0 else _parse_bool(display_any_true)

        output.append(
            {
                "name": name,
                "number": number,
                "visible": visible,
                "display": display,
                "attrib": attrib,
                "ifc_class": ifc_class,
                "predefined_type": predefined_type,
                "object_type": object_type,
                "psets": psets_by_node.get(name),
            }
        )

    return output


async def existing_nodes() -> list[ExistingProps]:
    base_query = """
    PREFIX x3d: <https://www.web3d.org/specifications/X3dOntology4.0#>
    PREFIX ifc: <https://w3id.org/ifc/IFC4X3_ADD2#>
    PREFIX express: <https://w3id.org/express#>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    SELECT
        ?name
        (MAX(?number) AS ?maxNumber)
        (MAX(IF(BOUND(?visibleRaw) && (?visibleRaw = true || ?visibleRaw = 1), 1, 0)) AS ?visibleAnyTrue)
        (SUM(IF(BOUND(?visibleRaw), 1, 0)) AS ?visibleBoundCount)
        (MAX(IF(BOUND(?displayRaw) && (?displayRaw = true || ?displayRaw = 1), 1, 0)) AS ?displayAnyTrue)
        (SUM(IF(BOUND(?displayRaw), 1, 0)) AS ?displayBoundCount)
        (SAMPLE(?attrib) AS ?attrib)
        (SAMPLE(?ifcClassLocal) AS ?ifcClass)
        (SAMPLE(?predefinedTypeLocal) AS ?predefinedType)
        (SAMPLE(?objectTypeLocal) AS ?objectType)
    WHERE {
        ?node x3d:hasMetadata ?name .
        ?node x3d:name ?number .

        OPTIONAL { ?node x3d:visible ?visibleRaw . }
        OPTIONAL { ?node x3d:bboxDisplay ?displayRaw . }
        OPTIONAL { ?node x3d:attrib ?attrib . }

        OPTIONAL {
            ?node rdf:type ?ifcClassUri .
            FILTER(STRSTARTS(STR(?ifcClassUri), "https://w3id.org/ifc/IFC4X3_ADD2#"))
            BIND(STRAFTER(STR(?ifcClassUri), "https://w3id.org/ifc/IFC4X3_ADD2#") AS ?ifcClassLocal)
        }

        OPTIONAL {
            ?node ?predTypeProp ?predTypeUri .
            FILTER(STRSTARTS(STR(?predTypeProp), "https://w3id.org/ifc/IFC4X3_ADD2#predefinedType_"))
            FILTER(STRSTARTS(STR(?predTypeUri), "https://w3id.org/ifc/IFC4X3_ADD2#"))
            BIND(STRAFTER(STR(?predTypeUri), "https://w3id.org/ifc/IFC4X3_ADD2#") AS ?predefinedTypeLocal)
        }

        OPTIONAL {
            ?node ifc:objectType_IfcObject ?objectTypeNode .
            ?objectTypeNode express:hasString ?objectTypeLocal .
        }
    }
    GROUP BY ?name
    """

    psets_query = """
    PREFIX x3d: <https://www.web3d.org/specifications/X3dOntology4.0#>
    PREFIX ifc: <https://w3id.org/ifc/IFC4X3_ADD2#>
    PREFIX express: <https://w3id.org/express#>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    SELECT DISTINCT ?name ?psetName ?propName ?ifcValueType ?propValue ?dataType
    WHERE {
        ?node x3d:hasMetadata ?name .
        ?node ifc:isDefinedBy_IfcObject ?relDefines .
        ?relDefines rdf:type ifc:IfcRelDefinesByProperties .
        ?relDefines ifc:relatingPropertyDefinition_IfcRelDefinesByProperties ?pset .
        ?pset rdf:type ifc:IfcPropertySet .
        ?pset ifc:name_IfcRoot ?psetNameNode .
        ?psetNameNode express:hasString ?psetName .

        OPTIONAL {
            ?pset ifc:hasProperties_IfcPropertySet ?prop .
            ?prop rdf:type ifc:IfcPropertySingleValue .
            ?prop ifc:name_IfcProperty ?propNameNode .
            ?propNameNode express:hasString ?propName .
            ?prop ifc:nominalValue_IfcPropertySingleValue ?valueNode .
            ?valueNode rdf:type ?valueTypeUri .
            FILTER(STRSTARTS(STR(?valueTypeUri), "https://w3id.org/ifc/IFC4X3_ADD2#"))
            BIND(STRAFTER(STR(?valueTypeUri), "https://w3id.org/ifc/IFC4X3_ADD2#") AS ?ifcValueType)

            OPTIONAL { ?valueNode express:hasString ?strValRaw . }
            OPTIONAL { ?valueNode express:hasInteger ?intValRaw . }
            OPTIONAL { ?valueNode express:hasDouble ?dblValRaw . }
            OPTIONAL { ?valueNode express:hasBoolean ?boolValRaw . }
            OPTIONAL { ?valueNode express:hasHexBinary ?hexValRaw . }
            BIND(COALESCE(STR(?strValRaw), STR(?intValRaw), STR(?dblValRaw), STR(?boolValRaw), STR(?hexValRaw)) AS ?propValue)
            BIND(IF(BOUND(?strValRaw), "STRING",
                 IF(BOUND(?intValRaw), "INTEGER",
                 IF(BOUND(?dblValRaw), "DOUBLE",
                 IF(BOUND(?boolValRaw), "BOOLEAN",
                 IF(BOUND(?hexValRaw), "HEX_BINARY", "STRING"))))) AS ?dataType)
        }
    }
    """

    base_result = await sparql_query(request=SparqlRequest(query=base_query))
    psets_result = await sparql_query(request=SparqlRequest(query=psets_query))
    psets_by_node = _build_psets_from_results(psets_result)
    return convert_sparql_results(base_result, psets_by_node)