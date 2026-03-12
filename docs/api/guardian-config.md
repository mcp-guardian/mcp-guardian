# GuardianConfig

`mcp_guardian.GuardianConfig` — multi-server configuration with per-server policies and auth.

## Class Definition

```python
@dataclass
class GuardianConfig:
    servers: list[ServerConfig] = []
    default_policy: Optional[str] = None
    model: str = "gpt-4o"
    guardian_model: Optional[str] = None
    timeout: int = 120
```

## Loading

```python
from mcp_guardian import GuardianConfig

config = GuardianConfig.from_file("guardian.yaml")
```

Supports YAML and JSON. Policy files referenced in the config are automatically loaded and resolved relative to the config file's directory.

## Methods

### `from_file(path) → GuardianConfig` (classmethod)

Loads config from a YAML or JSON file. Automatically calls `resolve_policies()`.

### `get_policy(server_name) → Optional[IntentPolicy]`

Returns the policy for a server. Falls back to the default policy if no server-specific policy is set.

```python
policy = config.get_policy("filesystem")
```

### `get_effective_guardian_model() → str`

Returns `guardian_model` if set, otherwise falls back to `model`.

### `resolve_policies(base_dir) → None`

Loads all referenced policy files. Called automatically by `from_file()`.

### `to_dict() → dict`

Serializes the config to a dictionary.

## ServerConfig

```python
@dataclass
class ServerConfig:
    name: str
    url: str
    transport: str = "streamable-http"
    headers: dict[str, str] = {}
    policy: Optional[str] = None
```

### `get_expanded_headers() → dict[str, str]`

Returns headers with `${ENV_VAR}` patterns replaced by environment variable values.

```python
# guardian.yaml:
#   headers:
#     Authorization: "Bearer ${MY_TOKEN}"

import os
os.environ["MY_TOKEN"] = "secret"

headers = server_config.get_expanded_headers()
# {"Authorization": "Bearer secret"}
```

## Usage with Demo

```python
config = GuardianConfig.from_file("guardian.yaml")

# Connect to servers
for srv_cfg in config.servers:
    server = MCPServerStreamableHttp(
        name=srv_cfg.name,
        params={"url": srv_cfg.url, "headers": srv_cfg.get_expanded_headers()},
    )

    # Per-server guardrail
    policy = config.get_policy(srv_cfg.name)
    guardrail = GuardianToolGuardrail(
        policy=policy,
        guardian_model=config.get_effective_guardian_model(),
    )
    tools = await guardrail.wrap_mcp_tools([server])
```
