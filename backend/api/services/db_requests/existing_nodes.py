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

def convert_sparql_results(results_json: dict) -> list[ExistingProps]:
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

        visible = None if _parse_int(visible_bound_count) == 0 else _parse_bool(visible_any_true)
        display = None if _parse_int(display_bound_count) == 0 else _parse_bool(display_any_true)

        output.append(
            {
                "name": name,
                "number": number,
                "visible": visible,
                "display": display,
                "attrib": attrib,
            }
        )

    return output


async def existing_nodes() -> list[ExistingProps]:
    query = """
    PREFIX x3d: <https://www.web3d.org/specifications/X3dOntology4.0#>
    SELECT
        ?name
        (MAX(?number) AS ?maxNumber)
        (MAX(IF(BOUND(?visibleRaw) && (?visibleRaw = true || ?visibleRaw = 1), 1, 0)) AS ?visibleAnyTrue)
        (SUM(IF(BOUND(?visibleRaw), 1, 0)) AS ?visibleBoundCount)
        (MAX(IF(BOUND(?displayRaw) && (?displayRaw = true || ?displayRaw = 1), 1, 0)) AS ?displayAnyTrue)
        (SUM(IF(BOUND(?displayRaw), 1, 0)) AS ?displayBoundCount)
        (SAMPLE(?attrib) AS ?attrib)
    WHERE {
        ?node x3d:hasMetadata ?name .
        ?node x3d:name ?number .

        OPTIONAL { ?node x3d:visible ?visibleRaw . }
        OPTIONAL { ?node x3d:bboxDisplay ?displayRaw . }
        OPTIONAL { ?node x3d:attrib ?attrib . }
    }
    GROUP BY ?name
    """

    result = await sparql_query(request=SparqlRequest(query=query))
    return convert_sparql_results(result)