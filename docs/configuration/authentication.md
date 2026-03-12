# Authentication

MCP Guardian supports bearer tokens and custom HTTP headers for authenticated MCP server connections.

## Config File Headers

Add headers to any server in `guardian.yaml`:

```yaml
servers:
  - name: my-server
    url: https://mcp.example.com/mcp
    headers:
      Authorization: "Bearer my-secret-token"
      X-API-Key: "my-api-key"
```

## Environment Variable Expansion

Use `${VAR_NAME}` in header values to reference environment variables. This keeps secrets out of your config files:

```yaml
servers:
  - name: my-server
    url: https://mcp.example.com/mcp
    headers:
      Authorization: "Bearer ${MCP_TOKEN}"
      X-Custom-Key: "${MY_API_KEY}"
```

Set the variables before running:

```bash
export MCP_TOKEN=my-secret-token
export MY_API_KEY=my-api-key
python3 -m mcp_guardian.examples.mcp_guardian_demo --config guardian.yaml --task "..."
```

If an environment variable is not set, the original `${VAR_NAME}` text is kept and a warning is logged.

## CLI Mode Headers

In CLI mode, pass headers with the `--header` flag (repeatable):

```bash
python3 -m mcp_guardian.examples.mcp_guardian_demo \
    --url https://mcp.example.com/mcp \
    --header "Authorization: Bearer my-token" \
    --header "X-API-Key: my-key" \
    --task "List files"
```

## In Code

Access expanded headers via `ServerConfig`:

```python
from mcp_guardian import GuardianConfig

config = GuardianConfig.from_file("guardian.yaml")
for srv in config.servers:
    headers = srv.get_expanded_headers()
    # headers now have ${VAR} replaced with actual values
```

## Security Notes

!!! warning "Keep secrets out of config files"
    Always use `${ENV_VAR}` expansion for tokens and keys. Never commit plaintext secrets to version control.

The guardian config file should contain `${VAR_NAME}` references, not actual secret values. Add your `guardian.yaml` to version control, but set the environment variables in your deployment environment (CI/CD secrets, `.env` files excluded from git, etc.).
