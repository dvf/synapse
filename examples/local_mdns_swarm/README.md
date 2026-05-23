# Local mDNS swarm

A zero-config local swarm that uses shared conversation atomics.

Run in three terminals on the same machine or LAN:

```bash
uv run python examples/local_mdns_swarm/reviewer.py
uv run python examples/local_mdns_swarm/coder.py
uv run python examples/local_mdns_swarm/ask.py
```

What it shows:

- Nodes discover each other with mDNS; no seed is needed.
- Reviewer and coder publish `agent-card` artifacts.
- The asker broadcasts to `synapse.ask`.
- Reviewer and coder ACK when they wade into the conversation.
- Replies are grouped by the shared conversation nonce.

You can also watch the swarm from another terminal:

```bash
uv run sn watch foo.electron.network
```
