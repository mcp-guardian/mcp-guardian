# Policies

An `IntentPolicy` defines what a worker agent is *supposed* to do. The guardian uses it to detect deviations — tool calls that don't match the declared intent are blocked.

## Policy Structure

```yaml
name: read-only-filesystem
description: Read and list files — no writes, no shell access

expected_workflow: >
  Read local files, list directory contents, and retrieve file metadata.
  All operations are read-only. No modifications allowed.

allowed_tools:
  - read_file
  - list_directory
  - get_file_info
  - read_multiple_files

forbidden_tools:
  - write_file
  - edit_block
  - move_file
  - create_directory
  - start_process
  - execute_command

allowed_transitions:
  read_file:
    - read_file
    - list_directory
    - get_file_info
  list_directory:
    - read_file
    - get_file_info
  get_file_info:
    - read_file

constraints:
  - No file modifications of any kind
  - No shell command execution
  - No network requests to external endpoints
  - File reads limited to the working directory

escalation_threshold: 0.7
```

## Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | yes | Policy identifier |
| `description` | string | yes | Human-readable description |
| `expected_workflow` | string | yes | Natural language description of what the agent should do (used by LLM evaluator) |
| `allowed_tools` | list | no | Tool whitelist — if set, only these tools are allowed. Supports glob patterns (`read_*`, `*`). |
| `forbidden_tools` | list | no | Tool blacklist — these tools are always blocked. Supports glob patterns (`write_*`, `execute_*`). |
| `allowed_transitions` | map | no | Valid tool sequences: `tool_a → [tool_b, tool_c]` |
| `constraints` | list | no | Natural language constraints (used by LLM evaluator) |
| `escalation_threshold` | float | no | Confidence below this → escalate to user (default: 0.7) |

## How Policies Are Evaluated

The guardian evaluates each tool call against the policy in three tiers:

### Tier 1: Fast Check (No LLM)

Deterministic, instant (0ms):

- Is the tool in `forbidden_tools`? → **Block**
- Is `allowed_tools` set and the tool not in it? → **Block**
- Does `allowed_transitions` forbid this sequence? → **Block**
- Otherwise → proceed to Tier 2

### Tier 2: LLM Intent Evaluation

The guardian sends the `expected_workflow`, `constraints`, tool name, and arguments to an LLM evaluator. The LLM returns a verdict with confidence:

- Confidence ≥ threshold and aligned → **Allow**
- Confidence ≥ threshold and misaligned → **Block**
- Confidence < `escalation_threshold` → **Escalate**

### Tier 3: Escalation

The tool call is flagged for human review. In the demo, this appears as a warning; in production, you can hook this into your approval workflow.

## Allowed vs Forbidden Tools

You can use either or both:

- **`allowed_tools` only** — strict whitelist; anything not listed is blocked
- **`forbidden_tools` only** — blacklist; everything except listed tools is allowed (after LLM check)
- **Both** — tool must be in the allowed list AND not in the forbidden list

!!! tip "Recommendation"
    For production, use `forbidden_tools` to explicitly block dangerous tools, and let the LLM evaluator handle the rest via `expected_workflow` and `constraints`. The whitelist approach (`allowed_tools`) is stricter but requires updating the policy every time a new tool is added to the server.

## Wildcard / Glob Patterns

Both `allowed_tools` and `forbidden_tools` support **fnmatch-style glob patterns** in addition to exact tool names. This makes policies much easier to maintain when MCP servers expose many tools with consistent naming conventions.

### Supported Patterns

| Pattern | Meaning | Example |
|---------|---------|---------|
| `*` | Match everything | `"*"` allows/blocks all tools |
| `read_*` | Match prefix | Matches `read_file`, `read_multiple_files`, etc. |
| `*_process` | Match suffix | Matches `start_process`, `interact_with_process`, etc. |
| `get_?` | Single character | Matches `get_a`, `get_b`, but not `get_ab` |
| `tool_[abc]` | Character set | Matches `tool_a`, `tool_b`, `tool_c` |

Plain tool names (no wildcards) still use exact matching — existing policies work unchanged.

### Examples

**Read-only via globs** — much shorter than listing every tool:

```yaml
allowed_tools:
  - "read_*"
  - "list_*"
  - "get_*"
  - "search_*"

forbidden_tools:
  - "write_*"
  - "execute_*"
  - "kill_*"
  - "start_process"
```

**Allow-all with explicit blocks** — useful when you only want to blacklist dangerous tools:

```yaml
allowed_tools:
  - "*"

forbidden_tools:
  - "write_*"
  - "execute_*"
  - "start_process"
  - "kill_*"
```

**Mix exact names and patterns:**

```yaml
allowed_tools:
  - "read_*"
  - "list_directory"    # exact name
  - "get_file_info"     # exact name
```

### Evaluation Order

Forbidden tools are checked **before** allowed tools. If a tool name matches both a forbidden pattern and an allowed pattern, it is **blocked**. This ensures the blacklist always takes precedence:

```yaml
allowed_tools: ["*"]            # allow everything ...
forbidden_tools: ["write_*"]    # ... except writes → write_file is BLOCKED
```

## Transition Graph

The `allowed_transitions` map defines valid tool sequences:

```yaml
allowed_transitions:
  read_file:
    - query_database
    - read_file
  query_database:
    - get_record
  get_record: []  # terminal — no tools allowed after this
```

This means: after `read_file`, the agent can call `query_database` or `read_file` again. After `query_database`, only `get_record` is allowed. After `get_record`, nothing is allowed.

An empty map (`{}`) disables sequence enforcement entirely.

## File Formats

Policies can be written in YAML or JSON:

=== "YAML"

    ```yaml
    name: my-policy
    description: Example policy
    expected_workflow: Read files and answer questions
    forbidden_tools:
      - execute_command
    ```

=== "JSON"

    ```json
    {
      "name": "my-policy",
      "description": "Example policy",
      "expected_workflow": "Read files and answer questions",
      "forbidden_tools": ["execute_command"]
    }
    ```

Load from code:

```python
policy = IntentPolicy.from_file("policies/my-policy.yaml")  # auto-detects format
```
