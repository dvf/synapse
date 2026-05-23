# Periodic garden caretaker

A tangible periodic-jobs demo: one Synapse node acts like a tiny garden caretaker.

It shows three scheduling styles:

- `every(...)` for frequent sensor polling
- `cron(...)` for wall-clock jobs
- `solar(...)` for sunrise/sunset behavior

Run it:

```bash
uv run python examples/periodic_tasks/garden.py
```

What to notice:

- The node starts immediately and prints each scheduled job as it fires.
- Solar jobs use real latitude/longitude and timezone data.
- The node also publishes an `agent-card` artifact so peers can inspect what it does.

This is deliberately not an agent framework. Synapse supplies the clock and node substrate; your application decides what a scheduled job actually does.
