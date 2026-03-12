# MCP Guardian

**Agent intent enforcement for MCP tool calls — pre-execution security for AI agents.**

MCP Guardian is not a firewall for MCP servers. It's a guardrail for **agent behavior**. It validates every tool call against declared intent policies *before execution*. If the call doesn't match the policy, the MCP server never sees it.

## Install

```bash
pip install mcp-guardian-ai
```

This pulls in all dependencies: `openai-agents`, `pydantic`, `pyyaml`.

Or install everything explicitly:

```bash
pip install mcp-guardian-ai openai-agents pydantic pyyaml
```

Set your OpenAI API key (used by the LLM intent evaluator — the fast check tier runs without it):

```bash
export OPENAI_API_KEY=sk-...
```

> **Note:** The PyPI package is `mcp-guardian-ai`. The Python import is `mcp_guardian`.

For development from source:

```bash
git clone https://github.com/mcp-guardian/mcp-guardian.git
cd mcp-guardian
pip install -e ".[dev]"
```

## Three Ways to Use It

### Path 1: Pure Python (no files needed)

```python
import asyncio
from agents import Agent, Runner
from agents.mcp import MCPServerStreamableHttp
from mcp_guardian import GuardianToolGuardrail, IntentPolicy

policy = IntentPolicy(
    name="read-only",
    description="Read files only — no writes, no shell",
    expected_workflow="Read and list files to answer user questions",
    forbidden_tools=["write_*", "execute_*", "delete_*"],
)
guardrail = GuardianToolGuardrail(policy=policy)

async def main():
    async with MCPServerStreamableHttp(
        name="my-server",
        params={"url": "https://my-mcp-server.example.com/mcp"},
    ) as server:
        tools = await guardrail.wrap_mcp_tools([server])
        agent = Agent(name="Worker", model="gpt-4o", tools=tools)
        result = await Runner.run(agent, "List all files")
        print(result.final_output)

    # Print audit log
    for entry in guardrail.audit_log:
        verdict = str(entry.verdict)
        icon = "✓" if verdict == "allow" else "✗"
        print(f"  {icon} {entry.tool_name} → {verdict.upper()} "
              f"(conf={entry.confidence:.2f}, {entry.method}, {entry.elapsed_ms:.0f}ms)")
        if verdict != "allow":
            print(f"    Reason: {entry.reason}")

asyncio.run(main())
```

### Path 2: YAML policy file (recommended)

Define a `policy.yaml`:

```yaml
name: read-only
description: Read-only file access
expected_workflow: Read and list files to answer user questions
allowed_tools: ["read_*", "list_*"]
forbidden_tools: ["write_*", "execute_*", "delete_*"]
allowed_transitions:
  list_directory: [read_file, list_directory]
  read_file: [read_file, list_directory]
constraints:
  - Do not access files outside the working directory
escalation_threshold: 0.7
```

Load it:

```python
policy = IntentPolicy.from_file("policy.yaml")
guardrail = GuardianToolGuardrail(policy=policy)
```

### Path 3: guardian.yaml + policy files (multi-server / production)

A single `guardian.yaml` ties together multiple servers, per-server policies, auth headers, and model settings:

```yaml
model: gpt-4o
guardian_model: gpt-4o
default_policy: policies/default.yaml
servers:
  - name: filesystem
    url: https://fs-server.example.com/mcp
    policy: policies/read-only.yaml
  - name: database
    url: https://db-server.example.com/mcp
    policy: policies/db-read-only.yaml
    headers:
      Authorization: "Bearer ${DB_TOKEN}"
```

```python
config = GuardianConfig.from_file("guardian.yaml")
```

See the [Quick Start](docs/getting-started/quickstart.md) for complete examples of all three paths.

## How It Works

Three-tier enforcement pipeline on every tool call:

1. **Fast check (0ms)** — forbidden tools, whitelists, glob patterns, **transition graph**. Deterministic, no LLM, impossible to bypass with prompt injection.
2. **LLM intent evaluation (1–5s)** — analyzes the call against policy constraints and workflow context.
3. **Escalation** — low-confidence decisions flagged for human review.

The **transition graph** (`allowed_transitions`) is a state machine over tool calls — similar to [LangGraph](https://github.com/langchain-ai/langgraph), but enforced externally on the agent rather than built into the agent's own execution graph. After tool A, only tools B and C are allowed. Everything else is blocked deterministically at 0ms.

Every evaluation is logged with verdict, confidence, timing, and reasoning.

## Policy Fields

| Field | Purpose |
|-------|---------|
| `allowed_tools` | Whitelist with glob patterns (`read_*`, `list_*`) |
| `forbidden_tools` | Blacklist — always blocked (`write_*`, `execute_*`) |
| `allowed_transitions` | State machine: tool A → [tool B, C] |
| `constraints` | Free-text rules for the LLM evaluator |
| `expected_workflow` | What the agent should be doing (LLM context) |
| `escalation_threshold` | Below this confidence → ask human |

## Demo: Exfiltration Prevention

A working demo blocks a data exfiltration attack across two MCP servers. The agent reads a secret (allowed), then an adversarial prompt tries to send it to an attacker URL — blocked at Tier 1 by the transition graph (0ms) and independently at Tier 2 by the LLM constraints.

See [`demos/exfiltration/`](demos/exfiltration/README.md) for details.

## Documentation

The full docs are built with [MkDocs Material](https://squidfunk.github.io/mkdocs-material/). Run them locally with Docker:

```bash
docker build -f Dockerfile.docs -t mcp-guardian-docs .
docker run -p 8000:8000 -v $(pwd)/docs:/docs/docs mcp-guardian-docs
```

Then open [http://localhost:8000](http://localhost:8000). The `-v` mount gives you live reload as you edit.

Or without Docker:

```bash
pip install mkdocs-material
mkdocs serve
```

## Built On

- [OpenAI Agents SDK](https://github.com/openai/openai-agents-python) — `ToolInputGuardrail`, `AgentHooksBase`
- [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) — tool server standard

## License

Apache 2.0
