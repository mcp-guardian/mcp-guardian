# Guardian Config

The `guardian.yaml` file is the central configuration for MCP Guardian. It defines which MCP servers to connect to, which policies to enforce, and how authentication works.

## Full Example

```yaml
model: gpt-4o
guardian_model: gpt-4o-mini
timeout: 120
default_policy: policies/default.yaml

servers:
  - name: filesystem
    url: https://fs.example.com/mcp
    transport: streamable-http
    policy: policies/read-only.yaml
    headers:
      Authorization: "Bearer ${FS_TOKEN}"

  - name: database
    url: https://db.example.com/mcp
    transport: sse
    policy: policies/db-query.yaml
    headers:
      X-API-Key: "${DB_API_KEY}"

  - name: search
    url: https://search.example.com/mcp
    # No policy → uses default_policy
    # No headers → no auth
```

## Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `model` | string | `gpt-4o` | Model for the worker agent |
| `guardian_model` | string | same as `model` | Model for the guardian intent evaluator |
| `timeout` | integer | `120` | Max seconds for the agent session |
| `default_policy` | string | none | Path to the default policy file (used for servers without an explicit policy) |
| `servers` | list | `[]` | MCP server configurations |

### Server Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | string | required | Unique server identifier |
| `url` | string | required | MCP server endpoint URL |
| `transport` | string | `streamable-http` | Transport type: `streamable-http` or `sse` |
| `policy` | string | none | Path to server-specific policy file |
| `headers` | map | `{}` | HTTP headers for authentication |

## Policy Resolution

When the guardian evaluates a tool call, it looks up the policy for the server that owns the tool:

1. If the server has an explicit `policy:` field → use that policy
2. Otherwise → use the `default_policy`
3. If neither exists → a permissive default is created (logs a warning)

All policy paths are resolved relative to the directory containing `guardian.yaml`.

## Loading in Code

```python
from mcp_guardian import GuardianConfig

config = GuardianConfig.from_file("guardian.yaml")

# Access resolved policies
for server in config.servers:
    policy = config.get_policy(server.name)
    print(f"{server.name}: {policy.name}")

# Access model settings
print(config.get_effective_guardian_model())
```

## JSON Format

The config also supports JSON:

```json
{
  "model": "gpt-4o",
  "default_policy": "policies/default.json",
  "servers": [
    {
      "name": "filesystem",
      "url": "https://fs.example.com/mcp",
      "policy": "policies/read-only.json"
    }
  ]
}
```
