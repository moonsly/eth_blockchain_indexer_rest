import json
import asyncio
import websockets

async def main():
    ws = await websockets.connect('wss://mainnet.infura.io/ws')
    request = dict(jsonrpc='2.0', id=1, method='eth_blockNumber', params=[])
    while True:
        await ws.send(json.dumps(request))
        response = await ws.recv()
        print(json.loads(response)['result'])

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())