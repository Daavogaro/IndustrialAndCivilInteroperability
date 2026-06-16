import requests
from fastapi import APIRouter, WebSocket
from ...models.models import VIRTUOSO_URL
async def import_to_db(websocket: WebSocket|None, graph:str, triples:str):

  sparql_update = """
  INSERT DATA {
    GRAPH <""" + graph + """> {
      """ + triples + """
    }
  }
  """

  response = requests.post(
      VIRTUOSO_URL,
      data={"update": sparql_update},
  )
  if websocket:
    await websocket.send_json({"status": "wip", "text": "Importing RDF data into the database..."})


async def delete_from_db(graph: str, delete_template: str, where_body: str):
  """Run a scoped DELETE/WHERE against a single graph.

  `delete_template` lists the triple patterns to remove; `where_body` binds the
  variables those patterns reference. Both are already-serialized SPARQL graph
  bodies (no surrounding GRAPH clause)."""
  sparql_update = """
  DELETE {
    GRAPH <""" + graph + """> {
      """ + delete_template + """
    }
  }
  WHERE {
    GRAPH <""" + graph + """> {
      """ + where_body + """
    }
  }
  """

  requests.post(
      VIRTUOSO_URL,
      data={"update": sparql_update},
  )
