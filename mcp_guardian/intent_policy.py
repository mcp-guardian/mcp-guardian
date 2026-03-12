"""
Intent Policy — defines expected agent behavior as a whitelist.

An IntentPolicy describes what a worker agent is SUPPOSED to do.
The guardian uses this to detect deviations — tool calls that don't
match the declared intent are blocked.

Example:
    policy = IntentPolicy(
        name="document-db-lookup",
        description="Read a document and find the matching database record",
        expected_workflow="Read document contents, extract key fields, "
                         "query database for matching records, return results to user",
        allowed_tools=["read_file", "query_database", "get_record"],
        forbidden_tools=["http_send", "execute_command", "write_file"],
        allowed_transitions={
            "read_file": ["query_database", "get_record"],
            "query_database": ["get_record"],
            "get_record": [],  # terminal
        },
        constraints=[
            "Must not send data to external endpoints",
            "Must not execute arbitrary commands",
            "Database queries must use parameterized inputs only",
            "File reads limited to the designated document directory",
        ],
    )
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from fnmatch import fnmatch
from typing import Any, Optional

logger = logging.getLogger(__name__)


class PolicyVerdict(str, Enum):
    """Guardian decision for a proposed tool call."""
    ALLOW = "allow"
    BLOCK = "block"
    ESCALATE = "escalate"  # ask the user


@dataclass
class VerdictResult:
    """Full verdict with reasoning chain."""
    verdict: PolicyVerdict
    tool_name: str
    tool_args: dict
    reason: str
    policy_name: str
    confidence: float = 1.0  # 0.0-1.0
    step_number: int = 0
    prior_tools: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "verdict": self.verdict.value,
            "tool_name": self.tool_name,
            "tool_args_summary": _summarize_args(self.tool_args),
            "reason": self.reason,
            "policy": self.policy_name,
            "confidence": self.confidence,
            "step": self.step_number,
            "prior_tools": self.prior_tools,
        }


@dataclass
class IntentPolicy:
    """
    Declares expected agent behavior for a specific task type.

    The guardian validates each tool call against this policy.
    The policy works at three levels:

    1. Tool-level: allowed_tools / forbidden_tools (fast, no LLM)
    2. Sequence-level: allowed_transitions (fast, no LLM)
    3. Intent-level: expected_workflow + constraints (LLM evaluation)
    """

    # Identity
    name: str
    description: str

    # Expected behavior (natural language — used for LLM evaluation)
    expected_workflow: str

    # Tool whitelist / blacklist (fast pre-filter)
    allowed_tools: list[str] = field(default_factory=list)
    forbidden_tools: list[str] = field(default_factory=list)

    # Sequence constraints: tool_name → list of allowed next tools
    # Empty dict = no sequence enforcement
    allowed_transitions: dict[str, list[str]] = field(default_factory=dict)

    # Natural-language constraints (evaluated by LLM)
    constraints: list[str] = field(default_factory=list)

    # Sensitivity threshold — below this confidence, escalate to user
    escalation_threshold: float = 0.7

    def fast_check(self, tool_name: str, prior_tools: list[str]) -> Optional[VerdictResult]:
        """
        Fast pre-filter check (no LLM call).

        Returns a VerdictResult if the decision is clear-cut (forbidden tool,
        invalid transition). Returns None if LLM evaluation is needed.

        Supports fnmatch-style glob patterns in allowed_tools and
        forbidden_tools.  For example:
            allowed_tools: ["read_*", "list_*"]      # glob patterns
            forbidden_tools: ["execute_*", "write_*"] # glob patterns
            allowed_tools: ["*"]                      # allow everything
        Plain names (no wildcards) use exact matching as before.
        """
        # Check forbidden tools
        if self.forbidden_tools and _matches_any(tool_name, self.forbidden_tools):
            return VerdictResult(
                verdict=PolicyVerdict.BLOCK,
                tool_name=tool_name,
                tool_args={},
                reason=f"Tool '{tool_name}' is explicitly forbidden by policy '{self.name}'",
                policy_name=self.name,
                confidence=1.0,
                step_number=len(prior_tools) + 1,
                prior_tools=prior_tools,
            )

        # Check allowed tools (if whitelist is defined)
        if self.allowed_tools and not _matches_any(tool_name, self.allowed_tools):
            return VerdictResult(
                verdict=PolicyVerdict.BLOCK,
                tool_name=tool_name,
                tool_args={},
                reason=f"Tool '{tool_name}' is not in the allowed set for policy '{self.name}': {self.allowed_tools}",
                policy_name=self.name,
                confidence=1.0,
                step_number=len(prior_tools) + 1,
                prior_tools=prior_tools,
            )

        # Check transition graph
        if self.allowed_transitions and prior_tools:
            last_tool = prior_tools[-1]
            if last_tool in self.allowed_transitions:
                allowed_next = self.allowed_transitions[last_tool]
                if allowed_next and tool_name not in allowed_next:
                    return VerdictResult(
                        verdict=PolicyVerdict.BLOCK,
                        tool_name=tool_name,
                        tool_args={},
                        reason=f"Invalid transition: '{last_tool}' → '{tool_name}'. "
                               f"Allowed next: {allowed_next}",
                        policy_name=self.name,
                        confidence=1.0,
                        step_number=len(prior_tools) + 1,
                        prior_tools=prior_tools,
                    )

        return None  # need LLM evaluation

    def to_prompt_context(self) -> str:
        """Render this policy as context for the guardian LLM."""
        lines = [
            f"## Intent Policy: {self.name}",
            f"**Description:** {self.description}",
            f"**Expected Workflow:** {self.expected_workflow}",
        ]
        if self.allowed_tools:
            lines.append(f"**Allowed Tools:** {', '.join(self.allowed_tools)}")
        if self.forbidden_tools:
            lines.append(f"**Forbidden Tools:** {', '.join(self.forbidden_tools)}")
        if self.constraints:
            lines.append("**Constraints:**")
            for c in self.constraints:
                lines.append(f"  - {c}")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "expected_workflow": self.expected_workflow,
            "allowed_tools": self.allowed_tools,
            "forbidden_tools": self.forbidden_tools,
            "allowed_transitions": self.allowed_transitions,
            "constraints": self.constraints,
            "escalation_threshold": self.escalation_threshold,
        }

    @classmethod
    def from_dict(cls, data: dict) -> IntentPolicy:
        return cls(**data)

    @classmethod
    def from_json(cls, path: str) -> IntentPolicy:
        """Load policy from a JSON file."""
        with open(path) as f:
            return cls.from_dict(json.load(f))

    @classmethod
    def from_yaml(cls, path: str) -> IntentPolicy:
        """Load policy from a YAML file."""
        try:
            import yaml
        except ImportError:
            raise ImportError(
                "PyYAML is required for YAML policy files. "
                "Install it with: pip install pyyaml"
            )
        with open(path) as f:
            return cls.from_dict(yaml.safe_load(f))

    @classmethod
    def from_file(cls, path: str) -> IntentPolicy:
        """Load policy from a JSON or YAML file (auto-detected by extension)."""
        if path.endswith((".yaml", ".yml")):
            return cls.from_yaml(path)
        return cls.from_json(path)

    def to_yaml(self, path: str) -> None:
        """Write policy to a YAML file."""
        try:
            import yaml
        except ImportError:
            raise ImportError(
                "PyYAML is required for YAML policy files. "
                "Install it with: pip install pyyaml"
            )
        with open(path, "w") as f:
            yaml.dump(self.to_dict(), f, default_flow_style=False, sort_keys=False)


def _matches_any(tool_name: str, patterns: list[str]) -> bool:
    """
    Check if *tool_name* matches any entry in *patterns*.

    Each pattern is either a plain tool name (exact match) or an
    fnmatch-style glob (e.g. ``read_*``, ``list_*``, ``*``).
    Plain names are compared with ``==`` for speed; globs are
    evaluated with :func:`fnmatch.fnmatch`.
    """
    for pat in patterns:
        if "*" in pat or "?" in pat or "[" in pat:
            if fnmatch(tool_name, pat):
                return True
        else:
            if tool_name == pat:
                return True
    return False


def _summarize_args(args: dict, max_len: int = 200) -> str:
    """Truncate tool args for logging (avoid leaking large payloads)."""
    s = json.dumps(args, default=str)
    if len(s) > max_len:
        return s[:max_len] + "..."
    return s
