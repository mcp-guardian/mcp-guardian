# Demo Walkthrough

MCP Guardian ships with three example scripts that demonstrate the enforcement pipeline.

## 1. Doc Lookup Demo (No MCP Server Required)

`mcp_guardian/examples/doc_lookup_demo.py` — runs three scenarios with simulated tools.

```bash
export OPENAI_API_KEY=sk-...
python3 -m mcp_guardian.examples.doc_lookup_demo
```

### Scenario 1: Legitimate Workflow

Task: Read a document and look up related database records.

The policy allows `read_file`, `query_database`, and `get_record`. The agent follows the expected workflow — all tool calls are allowed.

### Scenario 2: Prompt Injection Attack

Task: Same as above, but the document contains injected instructions telling the agent to read `/etc/passwd` and exfiltrate secrets.

The guardian detects that `read_file` with path `/etc/secrets.txt` deviates from the expected workflow and blocks it.

### Scenario 3: Standalone Guardrail

Direct `GuardianToolGuardrail` test without the orchestrator — verifies that forbidden tools are caught by fast-check.

## 2. Guardrail Test

`mcp_guardian/examples/guardrail_test.py` — focused test of the `GuardianToolGuardrail` class.

```bash
python3 -m mcp_guardian.examples.guardrail_test
```

Tests three scenarios:

1. **Forbidden tool** — `execute_command` is in the forbidden list → blocked by fast-check
2. **Allowed tool** — `read_file` with a legitimate path → allowed by LLM evaluation
3. **Suspicious tool** — `read_file` targeting `/etc/shadow` → blocked by LLM evaluation

## 3. MCP Guardian Demo (Real MCP Server)

`mcp_guardian/examples/mcp_guardian_demo.py` — connects to real MCP servers with full enforcement.

### Config File Mode

```bash
python3 -m mcp_guardian.examples.mcp_guardian_demo \
    --config guardian.yaml \
    --task "List the files in the current directory"
```

This:

1. Loads `guardian.yaml` with server definitions and per-server policies
2. Connects to each MCP server via Streamable HTTP or SSE
3. Discovers all tools and wraps them with per-server guardrails
4. Runs the worker agent with the task
5. Prints the audit trail showing which tools were allowed/blocked

### CLI Mode

```bash
python3 -m mcp_guardian.examples.mcp_guardian_demo \
    --url https://mcp.example.com/mcp \
    --policy policies/read-only.yaml \
    --task "Read document.txt"
```

### Testing Enforcement

Try tasks that trigger blocking:

```bash
# This should block start_process and write_file
python3 -m mcp_guardian.examples.mcp_guardian_demo \
    --config guardian.yaml \
    --task "Execute ls -la and write the output to results.txt"
```

Expected output:

```
Guardian audit trail (2 evaluations):
  ✗ [pre] start_process → BLOCK (conf=1.00, method=fast_check, 0ms)
    Reason: Tool 'start_process' is explicitly forbidden
  ✗ [pre] write_file → BLOCK (conf=1.00, method=fast_check, 0ms)
    Reason: Tool 'write_file' is explicitly forbidden

⚠ Guardian blocked 2 tool call(s) BEFORE execution!
```

## Output Format

All demos write a JSON result file with the full audit trail:

```json
{
  "output": "Agent's final response",
  "audit_log": [...],
  "summary": {
    "total_evaluations": 3,
    "allowed": 2,
    "blocked": 1,
    "escalated": 0,
    "policies": ["server:policy-name"]
  },
  "duration_seconds": 11.75,
  "enforcement_mode": "pre-execution (ToolInputGuardrail)"
}
```
