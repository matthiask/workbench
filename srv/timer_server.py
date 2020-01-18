import aiohttp
import asyncio
import aiopg
from aiohttp import web


dsn = "dbname=workbench"


async def websocket_handler(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)

    pool = await aiopg.create_pool(dsn)
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await ws.send_str("Hello {}".format(request.match_info["key"]))

            await cur.execute("LISTEN %s" % request.match_info["key"])  # TODO sanitize
            cur_task = asyncio.ensure_future(conn.notifies.get())
            # asyncio.create_task in Py>=3.7
            ws_task = asyncio.ensure_future(ws.receive())

            while True:
                done, pending = await asyncio.wait(
                    {ws_task, cur_task}, return_when=asyncio.FIRST_COMPLETED
                )

                if ws_task in done:
                    msg = ws_task.result()
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        if msg.data == "close":
                            await ws.close()
                        else:
                            await ws.send_str("You sent {}".format(msg.data))
                            await cur.execute(
                                "NOTIFY %s, %%s" % request.match_info["key"], [msg.data]
                            )

                    elif msg.type == aiohttp.WSMsgType.ERROR:
                        print(
                            "WebSocket connection closed with exception {}".format(
                                ws.exception()
                            )
                        )

                    # New task
                    ws_task = asyncio.ensure_future(ws.receive())

                if cur_task in done:
                    msg = cur_task.result()

                    print("Result from LISTEN", cur_task.result())
                    await ws.send_str("NOTIFY from postgres {}".format(msg))

                    # New task
                    cur_task = asyncio.ensure_future(conn.notifies.get())

    print("WebSocket connection closed")
    return ws


app = web.Application()
app.add_routes([web.get("/{key}", websocket_handler)])

if __name__ == "__main__":
    web.run_app(app)
