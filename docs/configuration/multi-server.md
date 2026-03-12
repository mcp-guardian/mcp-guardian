# Multi-Server Setup

MCP Guardian supports connecting to multiple MCP servers simultaneously, each with its own policy and authentication.

## Config File

```yaml
model: gpt-4o
guardian_model: gpt-4o-mini
default_policy: policies/permissive.yaml

servers:
  - name: filesystem
    url: https://fs.example.com/mcp
    transport: streamable-http
    policy: policies/read-only.yaml

  - name: database
    url: https://db.example.com/mcp
    transport: sse
    policy: policies/db-query-only.yaml

  - name: search
    url: https://search.example.com/mcp
    # uses default_policy
```

## How It Works

When you load this config, the guardian:

1. Connects to each server and discovers its tools
2. Creates a separate `GuardianToolGuardrail` for each server, using the server's assigned policy
3. Wraps all discovered tools with their respective guardrails
4. Gives the worker agent the full set of guarded tools

The worker agent sees tools from all servers, but each tool is protected by its own server's policy. A `write_file` call on the filesystem server is governed by `read-only.yaml`, while a `query` call on the database server is governed by `db-query-only.yaml`.

## In Code

```python
from contextlib import AsyncExitStack
from agents.mcp import MCPServerStreamableHttp
from mcp_guardian import GuardianConfig, GuardianToolGuardrail

config = GuardianConfig.from_file("guardian.yaml")

async with AsyncExitStack() as stack:
    all_tools = []

    for srv_cfg in config.servers:
        # Connect to server
        server = await stack.enter_async_context(
            MCPServerStreamableHttp(
                name=srv_cfg.name,
                params={
                    "url": srv_cfg.url,
                    "headers": srv_cfg.get_expanded_headers(),
                },
            )
        )

        # Get per-server policy and create guardrail
        policy = config.get_policy(srv_cfg.name)
        guardrail = GuardianToolGuardrail(
            policy=policy,
            guardian_model=config.get_effective_guardian_model(),
        )

        # Wrap this server's tools
        tools = await guardrail.wrap_mcp_tools([server])
        all_tools.extend(tools)

    # Create agent with all guarded tools
    agent = Agent(name="Worker", model=config.model, tools=all_tools)
    result = await Runner.run(agent, "Your task here")
```

## Policy Fallback

If a server doesn't have an explicit `policy:` field, the guardian uses `default_policy`. If neither exists, a permissive default is created and a warning is logged.

## Audit Merging

When running with multiple servers, each guardrail maintains its own audit log. The demo merges them into a single summary:

```
Summary:
  Allowed: 3, Blocked: 1, Escalated: 0
  Policies: filesystem:read-only, database:db-query-only
```

You can access individual guardrail audit logs for per-server reporting.

## Demo

The built-in demo supports multi-server configs directly:

```bash
python3 -m mcp_guardian.examples.mcp_guardian_demo \
    --config guardian.yaml \
    --task "Your task"
```
