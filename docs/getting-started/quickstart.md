# Quick Start

MCP Guardian has three usage modes, from simplest to most complete. Pick the one that fits your situation.

## The Concept

Before diving into code, here's the mental model:

```
You write a POLICY      →  "what is the agent allowed to do?"
The guardian enforces it →  "block anything that doesn't match"
The MCP server is safe   →  "it never sees blocked calls"
```

A **policy** defines: which tools are allowed, which are forbidden, what workflow the agent should follow, what constraints apply, and optionally a **transition graph** (which tool can follow which — like a state machine for tool calls).

The guardian sits between the agent and the MCP server. Every tool call passes through it. If the call violates the policy, the MCP server never sees it.

---

## Path 1: Pure Python (No Files)

Define the policy inline. No YAML, no config files. Good for quick prototyping.

```bash
pip install mcp-guardian-ai
export OPENAI_API_KEY=sk-...
```

```python
import asyncio
from agents import Agent, Runner
from agents.mcp import MCPServerStreamableHttp
from mcp_guardian import GuardianToolGuardrail, IntentPolicy

# 1. Define the policy — what is the agent allowed to do?
policy = IntentPolicy(
    name="read-only",
    description="Read files only — no writes, no shell",
    expected_workflow="Read and list files to answer user questions",
    allowed_tools=["read_*", "list_*"],
    forbidden_tools=["write_*", "execute_*", "delete_*"],
    constraints=[
        "Do not access files outside the working directory",
        "Do not send data to external URLs",
    ],
    escalation_threshold=0.7,
)

# 2. Create the guardrail
guardrail = GuardianToolGuardrail(policy=policy)

# 3. Connect to MCP server, wrap tools, run agent
async def main():
    async with MCPServerStreamableHttp(
        name="my-server",
        params={"url": "https://my-mcp-server.example.com/mcp"},
    ) as server:
        tools = await guardrail.wrap_mcp_tools([server])
        agent = Agent(name="Worker", model="gpt-4o", tools=tools)
        result = await Runner.run(agent, "List all files")
        print(result.final_output)

asyncio.run(main())
```

**What you need:** just the Python code above. No files on disk.

**Key line:** `tools=tools` instead of `mcp_servers=[server]`. That's the switch — the agent now uses guarded tools instead of raw MCP tools.

---

## Path 2: YAML Policy File (Recommended)

Define the policy as a YAML file. Same Python code, but the policy is external, version-controlled, and easy to share.

Create `policy.yaml`:

```yaml
name: read-only
description: Read-only file access — no writes, no shell

expected_workflow: >
  Read and list files to answer user questions.
  Do not modify anything.

allowed_tools:
  - "read_*"
  - "list_*"
  - "get_*"

forbidden_tools:
  - "write_*"
  - "execute_*"
  - "delete_*"
  - "start_process"

# Transition graph — which tool can follow which (optional)
# This is enforced deterministically at Tier 1 (0ms, no LLM)
allowed_transitions:
  list_directory:
    - list_directory
    - read_file
    - get_file_info
  read_file:
    - read_file
    - list_directory
  get_file_info:
    - read_file
    - list_directory

constraints:
  - Do not access files outside the working directory
  - Do not send data to external URLs

escalation_threshold: 0.7
```

Load it in Python:

```python
from mcp_guardian import GuardianToolGuardrail, IntentPolicy

policy = IntentPolicy.from_file("policy.yaml")
guardrail = GuardianToolGuardrail(policy=policy)

# ... then wrap tools and run agent exactly as in Path 1
```

**What you need:** one `.yaml` file + the Python code.

**When to use this:** you want policies reviewed in PRs, shared across team members, or tested independently from the code.

---

## Path 3: guardian.yaml + Policy Files (Multi-Server / Production)

For production setups with multiple MCP servers, per-server policies, authentication, and model settings — use a `guardian.yaml` config file that ties everything together.

Create `guardian.yaml`:

```yaml
model: gpt-4o
guardian_model: gpt-4o
timeout: 120

# Default policy for servers that don't have their own
default_policy: policies/default.yaml

servers:
  - name: filesystem
    url: https://fs-server.example.com/mcp
    transport: streamable-http
    policy: policies/read-only.yaml

  - name: database
    url: https://db-server.example.com/mcp
    transport: streamable-http
    policy: policies/db-read-only.yaml
    headers:
      Authorization: "Bearer ${DB_TOKEN}"

  - name: search
    url: https://search-server.example.com/mcp
    transport: streamable-http
    # no policy specified → uses default_policy
```

Each server points to its own policy file. Headers support `${ENV_VAR}` expansion.

Run it with the built-in demo CLI:

```bash
python -m mcp_guardian.examples.mcp_guardian_demo \
    --config guardian.yaml \
    --task "Find all CSV files and summarize the largest one"
```

Or use it programmatically:

```python
from mcp_guardian import GuardianConfig, GuardianToolGuardrail

config = GuardianConfig.from_file("guardian.yaml")

# Each server gets its own policy and guardrail
for server_config in config.servers:
    policy = config.get_policy(server_config.name)
    guardrail = GuardianToolGuardrail(
        policy=policy,
        guardian_model=config.get_effective_guardian_model(),
    )
    tools = await guardrail.wrap_mcp_tools([server])
```

**What you need:** `guardian.yaml` + one or more policy `.yaml` files.

**When to use this:** multiple MCP servers, per-server auth, per-server policies, or when you want a single config file that defines the entire deployment.

---

## The Policy in Detail

Regardless of which path you choose, the policy has the same fields:

| Field | Purpose | Example |
|-------|---------|---------|
| `name` | Identifier | `"read-only"` |
| `description` | What the policy does | `"Read files only"` |
| `expected_workflow` | What the agent should be doing | `"Read files to answer questions"` |
| `allowed_tools` | Whitelist (glob patterns ok) | `["read_*", "list_*"]` |
| `forbidden_tools` | Blacklist — always blocked (glob patterns ok) | `["write_*", "execute_*"]` |
| `allowed_transitions` | State machine: tool A → [tool B, C] | `{read_file: [read_file, list_directory]}` |
| `constraints` | Free-text rules for the LLM evaluator | `["No files outside working dir"]` |
| `escalation_threshold` | Below this confidence → ask human | `0.7` |

**Evaluation order for each tool call:**

1. **Forbidden?** → tool matches `forbidden_tools` → **BLOCK** (0ms, Tier 1)
2. **Not allowed?** → `allowed_tools` is set and tool doesn't match → **BLOCK** (0ms, Tier 1)
3. **Bad transition?** → `allowed_transitions` is set and this sequence is invalid → **BLOCK** (0ms, Tier 1)
4. **LLM check** → evaluates tool + args + context against `expected_workflow` + `constraints` → **ALLOW / BLOCK / ESCALATE** (Tier 2)

Steps 1–3 are deterministic, instant, and impossible to bypass with prompt injection. Step 4 uses an LLM and takes 1–5 seconds.

---

## What to Expect

The output shows enforcement in action:

```
Guardian audit trail (3 evaluations):
  ✓ [pre] list_directory → ALLOW  (conf=1.00, method=llm_intent, 2100ms)
  ✓ [pre] read_file      → ALLOW  (conf=0.95, method=llm_intent, 1800ms)
  ✗ [pre] write_file     → BLOCK  (conf=1.00, method=fast_check, 0ms)
    Reason: Tool 'write_file' is explicitly forbidden by policy 'read-only'

⚠ Guardian blocked 1 tool call(s) BEFORE execution!
```

`✓` = allowed and executed. `✗` = blocked before reaching the MCP server. `method=fast_check` means it was caught by Tier 1 (deterministic, 0ms). `method=llm_intent` means the LLM evaluated it.

---

## Next Steps

- [Three Lines to Guard](three-lines.md) — before/after comparison for existing agents
- [Policy Reference](../configuration/policies.md) — full policy schema, glob patterns, transition graphs
- [How It Works](../architecture/how-it-works.md) — the three-tier pipeline in detail
- [Exfiltration Demo](../../demos/exfiltration/README.md) — live demo blocking data exfiltration
