from synapse_p2p import Server

app = Server()


@app.background(3)
async def heartbeat():
    print("Running background task every 3 seconds")


@app.endpoint("sum")
async def sum_endpoint(a, b):
    return a + b


if __name__ == "__main__":
    app.run()
