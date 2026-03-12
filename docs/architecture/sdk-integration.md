# SDK Integration

MCP Guardian integrates natively with the [OpenAI Agents SDK](https://github.com/openai/openai-agents-python) using its built-in extension points.

## ToolInputGuardrail

The SDK provides a `ToolInputGuardrail` interface — a function that runs *before* any tool call is executed. If the guardrail raises `OutputGuardrailTripwireTriggered`, the tool call is blocked and the agent receives an error message.

MCP Guardian's `GuardianToolGuardrail` implements this interface:

```python
class GuardianToolGuardrail:
    async def run_guardrail(self, ctx, agent, tool_input) -> GuardrailFunctionOutput:
        # 1. Fast check (forbidden tools, whitelist, transitions)
        verdict = self.policy.fast_check(tool_name, prior_tools)

        # 2. If fast-check can't decide, run LLM evaluation
        if verdict is None:
            verdict = await self._llm_evaluate(tool_name, tool_args, ...)

        # 3. Block or allow
        if verdict.verdict == PolicyVerdict.BLOCK:
            return GuardrailFunctionOutput(
                output_info=OutputInfo(tripwire_triggered=True)
            )
        return GuardrailFunctionOutput(output_info=OutputInfo())
```

## AgentHooksBase

The SDK's `AgentHooksBase` provides lifecycle hooks for agents. `GuardianAgentHooks` uses these for audit logging:

- `on_agent_start` — log session start
- `on_agent_end` — log session end with summary
- `on_tool_start` — log tool execution start
- `on_tool_end` — log tool execution end

## Tool Wrapping

The key technique is wrapping MCP tools as `FunctionTool` objects with guardrails attached, instead of passing MCP servers directly to the agent:

```python
# Standard SDK (unguarded):
agent = Agent(mcp_servers=[server])

# Guardian (guarded):
tools = await guardrail.wrap_mcp_tools([server])
agent = Agent(tools=tools)
```

`wrap_mcp_tools()` does the following:

1. Calls `server.list_tools()` to discover available tools
2. Converts each MCP tool to a `FunctionTool` using `MCPUtil.to_function_tool()`
3. Sanitizes the JSON schema for OpenAI strict mode compatibility
4. Attaches the `GuardianToolGuardrail` as an `input_guardrail` on each tool
5. Returns the list of guarded `FunctionTool` objects

## Schema Sanitization

Real MCP servers produce tool schemas that often break OpenAI's strict function calling mode. Common issues:

- `additionalProperties: true` on object types (OpenAI requires `false`)
- Missing `properties` key on objects
- Missing `type` field on union-type parameters
- Missing `required` array

The `_sanitize_schema()` function handles all of these, recursively normalizing the schema to be OpenAI-compatible. If strict mode conversion still fails, the guardian falls back to non-strict mode with post-hoc sanitization.

## Minimal Integration

To add guardian enforcement to an existing SDK project:

```python
from mcp_guardian import GuardianToolGuardrail, IntentPolicy

# Define what the agent should do
policy = IntentPolicy.from_file("policy.yaml")

# Create guardrail
guardrail = GuardianToolGuardrail(policy=policy)

# Wrap MCP tools (instead of passing mcp_servers= to Agent)
tools = await guardrail.wrap_mcp_tools(mcp_servers)

# Use guarded tools
agent = Agent(name="Worker", tools=tools)
```

No changes to the agent's instructions, model, or task logic. The guardian is transparent — the agent doesn't know it's being supervised.
