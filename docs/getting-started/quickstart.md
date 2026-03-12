# Quick Start

Run the guardian demo against a real MCP server in under 5 minutes.

## 1. Setup

```bash
cd mcp-guardian
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
export OPENAI_API_KEY=sk-...
```

## 2. Config File Mode (Recommended)

Create a `guardian.yaml`:

```yaml
model: gpt-4o
guardian_model: gpt-4o
timeout: 120
default_policy: policies/local-only.yaml

servers:
  - name: my-server
    url: https://my-mcp-server.example.com/mcp
    transport: streamable-http
    policy: policies/read-only.yaml
```

Run the demo:

```bash
python3 -m mcp_guardian.examples.mcp_guardian_demo \
    --config guardian.yaml \
    --task "List all files in the current directory"
```

## 3. CLI Mode (Quick Testing)

No config file needed — specify everything on the command line:

```bash
python3 -m mcp_guardian.examples.mcp_guardian_demo \
    --url https://my-mcp-server.example.com/mcp \
    --task "List all files" \
    --forbidden-tools "execute_command,write_file,start_process"
```

With a policy file:

```bash
python3 -m mcp_guardian.examples.mcp_guardian_demo \
    --url https://my-mcp-server.example.com/mcp \
    --policy policies/desktop-commander-readonly.yaml \
    --task "Read document.txt and summarize it"
```

With authentication headers:

```bash
python3 -m mcp_guardian.examples.mcp_guardian_demo \
    --url https://my-mcp-server.example.com/mcp \
    --header "Authorization: Bearer my-token" \
    --header "X-API-Key: my-key" \
    --task "List files"
```

## 4. What to Expect

The output shows the enforcement in action:

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

The `✓` means the tool was allowed and executed. The `✗` means it was blocked *before* reaching the MCP server. The `method` field tells you which tier made the decision — `fast_check` (0ms, no LLM) or `llm_intent` (LLM evaluation).

## 5. Standalone Demo (No MCP Server)

To test the guardian logic without connecting to any server:

```bash
python3 -m mcp_guardian.examples.doc_lookup_demo
```

This runs three scenarios with simulated tools — a legitimate workflow, a prompt injection attack, and a standalone guardrail test.
