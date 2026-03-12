# GuardianToolGuardrail

`mcp_guardian.GuardianToolGuardrail` — the enforcement engine that validates tool calls against an `IntentPolicy`.

## Class Definition

```python
class GuardianToolGuardrail:
    def __init__(
        self,
        policy: IntentPolicy,
        guardian_model: str = "gpt-4o",
    )
```

## Constructor

```python
from mcp_guardian import GuardianToolGuardrail, IntentPolicy

policy = IntentPolicy.from_file("policies/read-only.yaml")
guardrail = GuardianToolGuardrail(
    policy=policy,
    guardian_model="gpt-4o-mini",  # model for intent evaluation
)
```

## Key Methods

### `wrap_mcp_tools(servers) → list[FunctionTool]`

Discovers tools from MCP servers, wraps each as a `FunctionTool` with the guardrail attached.

```python
tools = await guardrail.wrap_mcp_tools([server1, server2])
agent = Agent(name="Worker", tools=tools)
```

This is the primary integration point. Instead of `mcp_servers=[...]` on the Agent, you pass `tools=` with the guarded tools.

### `run_guardrail(ctx, agent, tool_input) → GuardrailFunctionOutput`

Called by the SDK on every tool call. Runs the three-tier evaluation pipeline. You don't call this directly — the SDK calls it automatically when a guarded tool is invoked.

### `get_audit_summary() → dict`

Returns a summary of all evaluations:

```python
summary = guardrail.get_audit_summary()
# {
#     "total_evaluations": 5,
#     "allowed": 3,
#     "blocked": 2,
#     "escalated": 0,
#     "policy": "read-only",
# }
```

### `audit_log → list[AuditEntry]`

Access the full audit log:

```python
for entry in guardrail.audit_log:
    print(f"{entry.tool_name}: {entry.verdict} ({entry.method})")
```

## AuditEntry Fields

| Field | Type | Description |
|-------|------|-------------|
| `tool_name` | str | The tool that was evaluated |
| `verdict` | str | `allow`, `block`, or `escalate` |
| `confidence` | float | 0.0-1.0 |
| `reason` | str | Human-readable explanation |
| `method` | str | `fast_check` or `llm_intent` |
| `elapsed_ms` | float | Evaluation time in milliseconds |
| `phase` | str | `pre` (before execution) |
| `risk_indicators` | list | Risk factors identified by LLM |

## GuardianAgentHooks

Optional lifecycle hooks for audit logging:

```python
from mcp_guardian import GuardianAgentHooks

hooks = GuardianAgentHooks(guardrail=guardrail)
agent = Agent(name="Worker", tools=tools, hooks=hooks)
```

Logs agent start/end and tool start/end events. Not required for enforcement — the guardrail works without hooks.

## run_guarded_session

Convenience function that wraps the full workflow:

```python
from mcp_guardian import run_guarded_session

result = await run_guarded_session(
    task="List files in /tmp",
    mcp_servers=[server],
    policy=policy,
    model="gpt-4o",
    guardian_model="gpt-4o-mini",
)
print(result.output)
print(result.audit_summary)
```
