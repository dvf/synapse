from synapse_p2p import Node

node = Node(name="calculator", port=9999)


@node.endpoint("sum", description="Add two numbers")
async def sum_endpoint(a: int, b: int) -> int:
    return a + b


if __name__ == "__main__":
    node.run()
