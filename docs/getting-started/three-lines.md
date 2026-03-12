# Three Lines to Guard

Adding the guardian to an existing OpenAI Agents SDK project takes three lines of code.

## Before (Unguarded)

```python
from agents import Agent, Runner
from agents.mcp import MCPServerStreamableHttp

async with MCPServerStreamableHttp(
    name="my-server",
    params={"url": "https://mcp.example.com/mcp"},
) as server:
    agent = Agent(
        name="Worker",
        model="gpt-4o",
        mcp_servers=[server],  # tools discovered automatically
    )
    result = await Runner.run(agent, "List all files")
```

The agent has unrestricted access to every tool the MCP server exposes.

## After (Guarded) — Three Lines

```python
from agents import Agent, Runner
from agents.mcp import MCPServerStreamableHttp
from mcp_guardian import GuardianToolGuardrail, IntentPolicy  # (1)

policy = IntentPolicy(                                         # (2)
    name="read-only",
    description="Read files only",
    expected_workflow="Read and list files to answer questions",
    forbidden_tools=["write_file", "execute_command", "start_process"],
)

guardrail = GuardianToolGuardrail(policy=policy)               # (3)

async with MCPServerStreamableHttp(
    name="my-server",
    params={"url": "https://mcp.example.com/mcp"},
) as server:
    tools = await guardrail.wrap_mcp_tools([server])

    agent = Agent(
        name="Worker",
        model="gpt-4o",
        tools=tools,  # guarded tools instead of mcp_servers=
    )
    result = await Runner.run(agent, "List all files")
```

The three additions:

1. **Import** — `GuardianToolGuardrail` and `IntentPolicy`
2. **Define policy** — what the agent is allowed to do
3. **Create guardrail** — wraps the policy as an SDK `ToolInputGuardrail`

The key change is `tools=tools` instead of `mcp_servers=[server]`. The guardian wraps each MCP tool as a `FunctionTool` with the guardrail attached. On every tool call:

- Fast-check runs first (forbidden list, allowed list, transition graph) — 0ms, no LLM
- If fast-check can't decide, the LLM intent evaluator analyzes the call against the policy
- If confidence is below the escalation threshold, the call is escalated to the user

## Loading Policy from a File

Instead of defining policies inline, use YAML files:

```python
policy = IntentPolicy.from_file("policies/read-only.yaml")
guardrail = GuardianToolGuardrail(policy=policy)
```

## Using GuardianConfig for Multi-Server

For production with multiple servers and per-server policies:

```python
from mcp_guardian import GuardianConfig, GuardianToolGuardrail

config = GuardianConfig.from_file("guardian.yaml")

for server_config in config.servers:
    policy = config.get_policy(server_config.name)
    guardrail = GuardianToolGuardrail(
        policy=policy,
        guardian_model=config.get_effective_guardian_model(),
    )
    tools = await guardrail.wrap_mcp_tools([server])
```

See [Multi-Server Setup](../configuration/multi-server.md) for the full pattern.
