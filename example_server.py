from electron.server import Server

server = Server(address="127.0.0.1", port=9999)


@server.background(3)
async def some_background_task():
    print("Testing background task every 3 seconds")


@server.endpoint("sum")
async def my_endpoint(a, b, **kwargs):
    return f"Result: {a + b}"


server.run()
