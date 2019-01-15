from electron.server import Server

app = Server()


@app.background(3)
async def some_background_task():
    print("Running background task every 3 seconds")


@app.endpoint("sum")
async def my_endpoint(a, b, **kwargs):
    return f"Result: {a + b}"


app.run()
