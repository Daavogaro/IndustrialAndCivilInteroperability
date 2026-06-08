import asyncio
import websockets
import json

async def main():
    uri = "ws://localhost:8000/api/ws/convert"

    async with websockets.connect(uri) as websocket:
        payload = {
            "filename": "Beam_line_-.1_In_Work_1.gltf",
            "graph_name": "http://localhost:8890/Elettra2/",
            "parent_uri": None,
            "ownerFirstName": "Davide",
            "ownerLastName": "Avogaro",
            "time": "2024-06-19T12:00:00Z"
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