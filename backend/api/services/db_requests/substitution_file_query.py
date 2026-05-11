from typing import TypedDict

from pydantic import BaseModel

from ...routes.sparql_query import sparql_query

class NodeToSubstitute(TypedDict):
    metadata: str
    numbers: list[int]
    toBeDeleted: bool|None
    toBeSimplified: bool|None
    fundamental: bool|None
    ifcClass: str|None
    guid: str|None
    ifcName: str|None
    psets: list[str]

class SparqlRequest(BaseModel):
    query: str

async def substitution_file_query(graph:str, original_file_url:str):
    print(original_file_url)

    # Escape backslashes and quotes so the file path is a valid SPARQL string literal
    safe_original_file_url = (original_file_url or "").replace("\\", "/")

    substitutionFileQuery = f"""
            PREFIX ifc: <https://w3id.org/ifc/IFC4X3_ADD2#>
            PREFIX express: <https://w3id.org/express#>
            PREFIX owl: <http://www.w3.org/2002/07/owl#>
            PREFIX x3d:  <https://www.web3d.org/specifications/X3dOntology4.0#>
            PREFIX pre: <http://www.loc.gov/premis/rdf/v3/>

            SELECT 
              ?metadata 
              ?cad 
              (GROUP_CONCAT(DISTINCT ?number; separator=",") AS ?numbers)
              ?toBeDeleted 
              ?toBeSimplified 
              ?fundamental 
              ?ifcClass 
              ?guid 
              ?ifcName 
              (GROUP_CONCAT(DISTINCT ?ifcRDBP; separator=",") AS ?psets)
            FROM <{graph}>
            WHERE {{
              ?metadata a x3d:MetadataString.
              ?s x3d:hasMetadata ?metadata.
              ?s a ?cad.
              ?s x3d:name ?number.
              ?s x3d:hasParentX3D ?a.
              ?a pre:storedAt ?url.

              OPTIONAL {{?s x3d:visible ?toBeDeleted}}.
              OPTIONAL {{?s x3d:bboxDisplay ?toBeSimplified}}.
              OPTIONAL {{?s x3d:attrib ?fundamental}}.

              OPTIONAL {{
                ?s a ?ifcClass.
                ?s ifc:globalId_IfcRoot ?guid.
                ?s ifc:name_IfcRoot ?ifcName.
                OPTIONAL {{?s ifc:isDefinedBy_IfcObject ?ifcRDBP}}
                FILTER(STRSTARTS(STR(?ifcClass),"https://w3id.org/ifc/IFC4X3_ADD2#"))
              }}

              FILTER(STR(?url) = "file:///{safe_original_file_url}")
            }}
            GROUP BY 
              ?metadata 
              ?cad 
              ?toBeDeleted 
              ?toBeSimplified 
              ?fundamental 
              ?ifcClass 
              ?guid 
              ?ifcName
        """
    
    try:
      nameAndNumberList = await sparql_query(request=SparqlRequest(query=substitutionFileQuery))
    except Exception as e:
      print("sparql_query raised exception:", e)
      import traceback
      traceback.print_exc()
      raise
    def convert_sparql_results(results_json: dict) -> list[NodeToSubstitute]:
        output: list[NodeToSubstitute] = []
    
        for binding in results_json["results"]["bindings"]:
            metadata = binding["metadata"]["value"].split("#")[1]
            

            item: NodeToSubstitute = {
                "metadata": metadata,
                "numbers": [int(num) for num in binding["numbers"]["value"].split(",")],
                "toBeDeleted": binding.get("toBeDeleted", {}).get("value") == "true",
                "toBeSimplified": binding.get("toBeSimplified", {}).get("value") == "true",
                "fundamental": binding.get("fundamental", {}).get("value") == "true",
                "ifcClass": binding.get("ifcClass", {}).get("value"),
                "guid": binding.get("guid", {}).get("value"),
                "ifcName": binding.get("ifcName", {}).get("value"),
                "psets": binding.get("psets", {}).get("value", "").split(",") if binding.get("psets") else []
            }
            output.append(item)
    
        return output
    nameAndNumberList = convert_sparql_results(nameAndNumberList)
    return nameAndNumberList