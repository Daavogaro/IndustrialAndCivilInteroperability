from pydantic import BaseModel

from ...routes.sparql_query import sparql_query
from ..importing_STEP.RDF_conversion import NameAndNumber

class SparqlRequest(BaseModel):
    query: str

async def name_and_number_query(graph: str):
    nameAndNumber_query = f"""
            PREFIX x3d:  <https://www.web3d.org/specifications/X3dOntology4.0#>
            SELECT ?name (MAX(?number) AS ?maxNumber)
            FROM <{graph}>
            WHERE {{
              ?node x3d:hasMetadata ?name .
              ?node x3d:name ?number .
            }}
            GROUP BY ?name
        """
    nameAndNumberList = await sparql_query(request=SparqlRequest(query=nameAndNumber_query))
    def convert_sparql_results(results_json: dict) -> list[NameAndNumber]:
        output: list[NameAndNumber] = []
    
        for binding in results_json["results"]["bindings"]:
            parts = binding["name"]["value"].split("#")
            name= "#".join(parts[1:]) if len(parts) > 1 else binding["name"]["value"]

            item: NameAndNumber = {
                "name": name,
                "number": int(binding["maxNumber"]["value"]),
            }
            output.append(item)
    
        return output
    nameAndNumberList = convert_sparql_results(nameAndNumberList)
    return nameAndNumberList