from synapse_p2p import Server

app = Server()


@app.background(3)
async def heartbeat():
    print("Running background task every 3 seconds")


@app.endpoint("sum")
async def sum_endpoint(a, b, response, **kwargs):
    response.write(f"The sum is {a + b}".encode())


if __name__ == "__main__":
    app.run()
