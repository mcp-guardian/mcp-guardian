# Testing MCP Guardian

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Set your OpenAI API key

```bash
export OPENAI_API_KEY=sk-...
```

## Run the examples

### Demo 1 — Doc lookup (simulated tools, no MCP server needed)

Runs three scenarios: legitimate request, prompt injection attack, and standalone evaluation.

```bash
python3 -m mcp_guardian.examples.doc_lookup_demo
```

Without an API key, only the fast-check tier runs (forbidden tools are still blocked instantly). With a key, the LLM evaluator handles ambiguous calls too.

### Demo 2 — Guardrail test (simulated tools, no MCP server needed)

Tests the SDK's native `ToolInputGuardrail` pipeline with three attack scenarios: legitimate request, URL fetch, and email exfiltration.

```bash
python3 -m mcp_guardian.examples.guardrail_test
```

### Demo 3 — Real MCP server

Connects to a live MCP server, discovers tools, wraps them with the guardian, and runs a worker agent with full pre-execution enforcement.

```bash
python3 -m mcp_guardian.examples.mcp_guardian_demo \
    --url https://your-mcp-server.example.com/mcp \
    --name MyServer \
    --task "List the files in the current directory" \
    --expected-workflow "List directory contents to show file structure" \
    --allowed-tools "list_directory,read_file,get_file_info" \
    --forbidden-tools "execute_command,start_process,write_file" \
    --constraints "Read-only operations only,No command execution"
```

Use `--policy-json policies/local-only.json` to load a policy from file instead.

## Run unit tests

```bash
pytest
```
