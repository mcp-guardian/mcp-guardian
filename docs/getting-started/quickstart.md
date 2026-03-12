# Quick Start

Run the guardian against a real MCP server in under 5 minutes.

## 1. Install

```bash
pip install mcp-guardian-ai
export OPENAI_API_KEY=sk-...
```

!!! note "Package name vs import name"
    The **PyPI package** is `mcp-guardian-ai` (what you `pip install`).
    The **Python import** is `mcp_guardian` (what you `import` in code).

## 2. Write a Script

Create `run_guardian.py`:

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

Run it:

```bash
python run_guardian.py
```

## 3. Use a Policy File

Instead of inline policies, create `policy.yaml`:

```yaml
name: read-only
description: Read-only file access
expected_workflow: Read and list files to answer user questions
allowed_tools:
  - "read_*"
  - "list_*"
forbidden_tools:
  - "write_*"
  - "execute_*"
  - "start_*"
constraints:
  - Do not access files outside the working directory
escalation_threshold: 0.7
```

Load it in your script:

```python
policy = IntentPolicy.from_file("policy.yaml")
guardrail = GuardianToolGuardrail(policy=policy)
```

## 4. Use the Built-In Demo CLI

The package includes a demo CLI that supports config files and inline policies:

```bash
# Single server, inline policy
python -m mcp_guardian.examples.mcp_guardian_demo \
    --url https://my-mcp-server.example.com/mcp \
    --task "List all files" \
    --forbidden-tools "execute_command,write_file,start_process"

# Single server, policy file
python -m mcp_guardian.examples.mcp_guardian_demo \
    --url https://my-mcp-server.example.com/mcp \
    --policy policy.yaml \
    --task "Read document.txt and summarize it"

# Multi-server config file
python -m mcp_guardian.examples.mcp_guardian_demo \
    --config guardian.yaml \
    --task "List all files in the current directory"

# With authentication headers
python -m mcp_guardian.examples.mcp_guardian_demo \
    --url https://my-mcp-server.example.com/mcp \
    --header "Authorization: Bearer my-token" \
    --task "List files"
```

## 5. What to Expect

The output shows enforcement in action:

```
======================================================================
MCP Guardian — Pre-Execution Enforcement
======================================================================
Servers: ['my-server']
  • my-server: https://... [policy=read-only, auth=no]
Mode: ToolInputGuardrail (blocks BEFORE execution)

Guardian audit trail (2 evaluations):
  ✓ [pre] list_directory → ALLOW (conf=1.00, method=llm_intent, 3058ms)
  ✗ [pre] write_file → BLOCK (conf=1.00, method=fast_check, 0ms)
    Reason: Tool 'write_file' is explicitly forbidden by policy 'read-only'

⚠ Guardian blocked 1 tool call(s) BEFORE execution!
```

`✓` = allowed and executed. `✗` = blocked *before* reaching the MCP server.

## 6. Standalone Demo (No MCP Server)

To test the guardian logic without connecting to any server:

```bash
python -m mcp_guardian.examples.doc_lookup_demo
```

This runs three scenarios with simulated tools — a legitimate workflow, a prompt injection attack, and a standalone guardrail test.

## Next Steps

- [Three Lines to Guard](three-lines.md) — integrate the guardian into your existing agent
- [Policy Reference](../configuration/policies.md) — full policy schema and glob patterns
- [Exfiltration Demo](../../demos/exfiltration/README.md) — live demo blocking data exfiltration
