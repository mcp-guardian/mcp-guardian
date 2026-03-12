"""
Guardian — Multi-agent intent enforcement for MCP tool calls.

The Guardian pattern wraps untrusted worker agents with a supervisory
orchestrator that validates every tool call against declared intent
policies before execution.

Architecture:
    User → Guardian Orchestrator → Worker Agent → MCP Servers
                ↓
         Intent Validator (LLM)
                ↓
         Allow / Block / Escalate

Two enforcement modes:

1. orchestrator.py — monkey-patch approach (wraps FunctionTool.on_invoke_tool)
   Good for: custom tool functions, doc_lookup_demo.py

2. guardian_hooks.py — native SDK approach (ToolInputGuardrail + AgentHooks)
   Good for: MCP servers, production deployments
   Uses the SDK's own pre-execution guardrail pipeline.
"""

from mcp_guardian.intent_policy import IntentPolicy, PolicyVerdict, VerdictResult
from mcp_guardian.orchestrator import GuardianOrchestrator
from mcp_guardian.config import GuardianConfig, ServerConfig
from mcp_guardian.guardian_hooks import (
    GuardianToolGuardrail,
    GuardianAgentHooks,
    GuardedSessionResult,
    run_guarded_session,
)

__all__ = [
    "IntentPolicy",
    "PolicyVerdict",
    "VerdictResult",
    "GuardianOrchestrator",
    "GuardianConfig",
    "ServerConfig",
    "GuardianToolGuardrail",
    "GuardianAgentHooks",
    "GuardedSessionResult",
    "run_guarded_session",
]
