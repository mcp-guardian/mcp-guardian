# MCP Guardian

**Intent enforcement for MCP tool calls — whitelist-based security for AI agents.**

MCP Guardian wraps untrusted worker agents with a supervisory layer that validates every tool call against declared intent policies *before execution*. If a tool call doesn't match the policy, it's blocked — the tool never runs.

```
User → Guardian Orchestrator → Worker Agent → MCP Servers
              ↓
       Intent Validator (LLM)
              ↓
       Allow / Block / Escalate
```

## Why?

MCP servers expose powerful tools — file systems, databases, shell access, APIs. When an AI agent has access to these tools, a prompt injection or a misaligned model can cause real damage. MCP Guardian adds a policy layer between the agent and the tools:

- **Whitelist enforcement** — only tools and sequences you've declared are allowed
- **Three-tier evaluation** — fast deterministic checks first, LLM intent analysis only when needed
- **Pre-execution blocking** — forbidden calls are stopped before they reach the MCP server
- **Per-server policies** — different rules for different servers
- **Full audit trail** — every evaluation is logged with verdict, confidence, and timing

## Quick Example

```python
from mcp_guardian import GuardianToolGuardrail, IntentPolicy

policy = IntentPolicy(
    name="read-only",
    description="Read files only — no writes, no shell",
    expected_workflow="Read and list files to answer user questions",
    allowed_tools=["read_file", "list_directory"],
    forbidden_tools=["write_file", "execute_command"],
)

guardrail = GuardianToolGuardrail(policy=policy)
tools = await guardrail.wrap_mcp_tools(mcp_servers)

agent = Agent(name="Worker", tools=tools)
```

That's it. Every tool call the agent proposes now passes through the guardian before execution.

## Features

- **Core library** — `IntentPolicy`, `GuardianToolGuardrail`, `GuardianAgentHooks`
- **Multi-server support** — connect N servers, wrap all tools, enforce per-server or global policies
- **Auth passthrough** — bearer tokens and custom headers per server, with `${ENV_VAR}` expansion
- **Hand-written policies** — YAML or JSON, version-controlled alongside your config
- **Config file** — single `guardian.yaml` defines servers, policies, auth, and model settings
- **OpenAI Agents SDK native** — uses `ToolInputGuardrail` and `AgentHooksBase`, no monkey-patching
- **Schema sanitization** — handles real-world MCP server schemas that break OpenAI strict mode

## Next Steps

- [Installation](getting-started/installation.md) — pip install and setup
- [Quick Start](getting-started/quickstart.md) — run the demo in 5 minutes
- [Three Lines to Guard](getting-started/three-lines.md) — add the guardian to your existing agent
- [Architecture](architecture/overview.md) — how it works under the hood
