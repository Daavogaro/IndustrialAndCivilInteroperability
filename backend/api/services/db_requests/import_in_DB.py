import requests
from fastapi import APIRouter, WebSocket
from ...models.models import VIRTUOSO_URL
async def import_to_db(websocket: WebSocket|None,graph:str,triples:str):

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
