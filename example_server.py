from synapse_p2p.server import Server

app = Server()


@app.background(3)
async def some_background_task():
    print("Running background task every 3 seconds")


@app.endpoint("sum")
async def my_endpoint(a, b, response, **kwargs):
    response.write(f"The sum is {a + b}".encode())


app.run()
