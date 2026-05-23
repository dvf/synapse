# Basic RPC

The smallest useful Synapse example.

Run the node in one terminal:

```bash
uv run python examples/basic_rpc/node.py
```

Call it from another terminal:

```bash
uv run python examples/basic_rpc/client.py
```

What it shows:

- A `Node` exposes an async endpoint named `sum`.
- A `Client` calls that endpoint over Synapse RPC.
- No swarm discovery is needed for direct host/port RPC.
