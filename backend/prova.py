import asyncio
import websockets
import json

async def main():
    uri = "ws://localhost:8000/api/ws/convert"

    async with websockets.connect(uri) as websocket:
        payload = {
            "filename": "PRD-00895849_Green_Var_Tattoos_Davide_stp_-.1_In_Work.gltf",
            "graph_name": "http://localhost:8890/Elettra2/",
            "parent_uri": None
        }

        await websocket.send(json.dumps(payload))
        print("Sent:", payload)

        try:
            while True:
                msg = await websocket.recv()
                print("Received:", msg)
        except:
            print("Connection closed")

asyncio.run(main())