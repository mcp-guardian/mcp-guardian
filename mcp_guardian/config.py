"""
Guardian Configuration — multi-server setup with per-server policies and auth.

A single guardian.yaml (or JSON) file defines:
- Which MCP servers to connect to
- Authentication headers per server (bearer tokens, API keys, custom headers)
- Which policy applies to each server (or a global default)

Example guardian.yaml:

    model: gpt-4o
    guardian_model: gpt-4o-mini
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

Environment variables in header values (${VAR_NAME}) are expanded at load time.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Optional

from mcp_guardian.intent_policy import IntentPolicy

logger = logging.getLogger(__name__)

# Pattern for ${ENV_VAR} expansion
_ENV_PATTERN = re.compile(r"\$\{([^}]+)\}")


def _expand_env(value: str) -> str:
    """Replace ${VAR_NAME} with environment variable values."""
    def replacer(match):
        var_name = match.group(1)
        env_val = os.environ.get(var_name)
        if env_val is None:
            logger.warning("Environment variable '%s' is not set", var_name)
            return match.group(0)  # keep original if not set
        return env_val
    return _ENV_PATTERN.sub(replacer, value)


def _expand_headers(headers: dict[str, str]) -> dict[str, str]:
    """Expand environment variables in all header values."""
    return {k: _expand_env(v) for k, v in headers.items()}


@dataclass
class ServerConfig:
    """Configuration for a single MCP server connection."""
    name: str
    url: str
    transport: str = "streamable-http"
    headers: dict[str, str] = field(default_factory=dict)
    policy: Optional[str] = None  # path to policy file (overrides default)

    def get_expanded_headers(self) -> dict[str, str]:
        """Return headers with environment variables expanded."""
        return _expand_headers(self.headers)

    @classmethod
    def from_dict(cls, data: dict) -> ServerConfig:
        return cls(
            name=data["name"],
            url=data["url"],
            transport=data.get("transport", "streamable-http"),
            headers=data.get("headers", {}),
            policy=data.get("policy"),
        )


@dataclass
class GuardianConfig:
    """
    Full guardian configuration: servers, policies, and model settings.

    Supports loading from YAML or JSON. Handles:
    - Multiple MCP servers with individual auth headers
    - Per-server policy assignment with a global default fallback
    - Environment variable expansion in header values
    """
    servers: list[ServerConfig] = field(default_factory=list)
    default_policy: Optional[str] = None  # path to default policy file
    model: str = "gpt-4o"
    guardian_model: Optional[str] = None  # defaults to model
    timeout: int = 120

    # Resolved policies (populated by resolve_policies)
    _policies: dict[str, IntentPolicy] = field(
        default_factory=dict, repr=False
    )
    _default_policy_obj: Optional[IntentPolicy] = field(
        default=None, repr=False
    )

    def resolve_policies(self, base_dir: str = ".") -> None:
        """
        Load all referenced policy files.

        Resolves paths relative to base_dir (typically the directory
        containing the guardian config file).
        """
        # Load default policy
        if self.default_policy:
            path = os.path.join(base_dir, self.default_policy)
            self._default_policy_obj = IntentPolicy.from_file(path)
            logger.info(
                "Loaded default policy '%s' from %s",
                self._default_policy_obj.name, path,
            )

        # Load per-server policies
        for srv in self.servers:
            if srv.policy:
                path = os.path.join(base_dir, srv.policy)
                policy = IntentPolicy.from_file(path)
                self._policies[srv.name] = policy
                logger.info(
                    "Loaded policy '%s' for server '%s' from %s",
                    policy.name, srv.name, path,
                )

    def get_policy(self, server_name: str) -> Optional[IntentPolicy]:
        """
        Get the policy for a server.

        Returns the server-specific policy if one is assigned,
        otherwise falls back to the default policy.
        """
        return self._policies.get(server_name, self._default_policy_obj)

    def get_effective_guardian_model(self) -> str:
        """Return the guardian model, defaulting to the worker model."""
        return self.guardian_model or self.model

    @classmethod
    def from_dict(cls, data: dict) -> GuardianConfig:
        servers = [
            ServerConfig.from_dict(s) for s in data.get("servers", [])
        ]
        return cls(
            servers=servers,
            default_policy=data.get("default_policy"),
            model=data.get("model", "gpt-4o"),
            guardian_model=data.get("guardian_model"),
            timeout=data.get("timeout", 120),
        )

    @classmethod
    def from_file(cls, path: str) -> GuardianConfig:
        """Load config from a YAML or JSON file."""
        base_dir = os.path.dirname(os.path.abspath(path))

        if path.endswith((".yaml", ".yml")):
            try:
                import yaml
            except ImportError:
                raise ImportError(
                    "PyYAML is required for YAML config files. "
                    "Install it with: pip install pyyaml"
                )
            with open(path) as f:
                data = yaml.safe_load(f)
        else:
            with open(path) as f:
                data = json.load(f)

        config = cls.from_dict(data)
        config.resolve_policies(base_dir)
        return config

    def to_dict(self) -> dict:
        result = {
            "model": self.model,
            "timeout": self.timeout,
            "servers": [
                {
                    "name": s.name,
                    "url": s.url,
                    "transport": s.transport,
                    **({"headers": s.headers} if s.headers else {}),
                    **({"policy": s.policy} if s.policy else {}),
                }
                for s in self.servers
            ],
        }
        if self.guardian_model:
            result["guardian_model"] = self.guardian_model
        if self.default_policy:
            result["default_policy"] = self.default_policy
        return result
