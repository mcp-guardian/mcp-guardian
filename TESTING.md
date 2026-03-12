# Testing MCP Guardian

## Setup

```bash
git clone https://github.com/mcp-guardian/mcp-guardian.git
cd mcp-guardian
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

### Demo 3 — Real MCP server (config file mode)

Connects to live MCP servers defined in `guardian.yaml`, discovers tools, wraps them with per-server policies, and runs a worker agent with full pre-execution enforcement.

```bash
python3 -m mcp_guardian.examples.mcp_guardian_demo \
    --config guardian.yaml \
    --task "List the files in the current directory"
```

### Demo 3 — Real MCP server (CLI mode)

Specify server and policy directly on the command line:

```bash
python3 -m mcp_guardian.examples.mcp_guardian_demo \
    --url https://your-mcp-server.example.com/mcp \
    --policy policies/desktop-commander-readonly.yaml \
    --task "List the files in the current directory"
```

With authentication headers:

```bash
python3 -m mcp_guardian.examples.mcp_guardian_demo \
    --url https://your-mcp-server.example.com/mcp \
    --header "Authorization: Bearer my-token" \
    --policy policies/desktop-commander-readonly.yaml \
    --task "Read document.txt"
```

## Run unit tests

```bash
pytest
```
