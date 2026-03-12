# MCP Guardian

**Intent enforcement for MCP tool calls — whitelist-based security for AI agents.**

MCP Guardian validates every tool call **before execution**. If it doesn't match the policy, the call is blocked — the MCP server never sees it.

## Install

```bash
pip install mcp-guardian-ai
```

> **Note:** The PyPI package is `mcp-guardian-ai`. The Python import is `mcp_guardian`.

You also need an OpenAI API key (for the LLM intent evaluator):

```bash
export OPENAI_API_KEY=sk-...
```

## Quick Start

```python
import asyncio
from agents import Agent, Runner
from agents.mcp import MCPServerStreamableHttp
from mcp_guardian import GuardianToolGuardrail, IntentPolicy

policy = IntentPolicy(
    name="read-only",
    description="Read files only — no writes, no shell",
    expected_workflow="Read and list files to answer user questions",
    forbidden_tools=["write_file", "execute_command", "start_process"],
)

guardrail = GuardianToolGuardrail(policy=policy)

async def main():
    async with MCPServerStreamableHttp(
        name="my-server",
        params={"url": "https://my-mcp-server.example.com/mcp"},
    ) as server:
        tools = await guardrail.wrap_mcp_tools([server])
        agent = Agent(name="Worker", model="gpt-4o", tools=tools)
        result = await Runner.run(agent, "List all files in the current directory")
        print(result.final_output)

asyncio.run(main())
```

Every tool call the agent proposes now passes through the guardian before execution. Forbidden tools are blocked instantly (0ms, no LLM call). All other calls go through the LLM intent evaluator.

## How It Works

Three-tier enforcement pipeline:

1. **Fast check (0ms)** — forbidden tools, whitelist enforcement, transition graph. No LLM, no network call.
2. **LLM intent evaluation (1–5s)** — analyzes tool name, arguments, and context against the policy.
3. **Escalation** — when confidence is below threshold, the call is flagged for human review.

Every evaluation is logged with verdict, confidence, timing, and reasoning.

## Policy Files (YAML)

Define policies as YAML files and load them:

```python
policy = IntentPolicy.from_file("policies/read-only.yaml")
guardrail = GuardianToolGuardrail(policy=policy)
```

Example policy (`policies/read-only.yaml`):

```yaml
name: read-only
description: Read-only access to the file system
expected_workflow: Read and list files to answer user questions
allowed_tools:
  - "read_*"
  - "list_*"
  - "get_*"
forbidden_tools:
  - "write_*"
  - "execute_*"
  - "start_*"
  - "delete_*"
constraints:
  - Do not access files outside the working directory
  - Do not execute any commands
escalation_threshold: 0.7
```

Glob patterns (`*`, `?`, `[seq]`) are supported in `allowed_tools` and `forbidden_tools`.

## Multi-Server Config

For multiple MCP servers with per-server policies, use a `guardian.yaml`:

```yaml
model: gpt-4o
guardian_model: gpt-4o
timeout: 120
default_policy: policies/default.yaml

servers:
  - name: filesystem
    url: https://fs-server.example.com/mcp
    transport: streamable-http
    policy: policies/read-only.yaml
  - name: database
    url: https://db-server.example.com/mcp
    transport: streamable-http
    headers:
      Authorization: "Bearer ${DB_TOKEN}"
    policy: policies/db-read-only.yaml
```

## Demo: Exfiltration Prevention

A working demo shows the guardian blocking a data exfiltration attack across two real MCP servers:

```bash
export OPENAI_API_KEY=sk-...
export FETCH_MCP_TOKEN="eyJhbGci..."
./demos/exfiltration/run_demo.sh
```

Scenario 1 (legitimate) reads a secret — **allowed**. Scenario 2 (adversarial) tries to send the secret to an attacker URL — **blocked before execution**.

See [`demos/exfiltration/README.md`](demos/exfiltration/README.md) for details.

## Built On

- [OpenAI Agents SDK](https://github.com/openai/openai-agents-python) — `ToolInputGuardrail`, `AgentHooksBase`
- [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) — tool server standard

## License

Apache 2.0
