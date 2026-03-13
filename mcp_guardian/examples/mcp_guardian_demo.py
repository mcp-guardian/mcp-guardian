#!/usr/bin/env python3
"""
Guardian Demo: Real MCP Server Protection (Pre-Execution Enforcement)

Connects to real MCP servers, discovers their tools, attaches the guardian
as a ToolInputGuardrail on each tool, and runs a worker agent with full
pre-execution intent enforcement.

Supports two modes:

1. Config file mode (recommended):
   Loads servers, policies, and auth from a single guardian.yaml file.
   Per-server policies allow different enforcement rules per server.

2. CLI mode (quick testing):
   Specify a single server URL and inline policy via command-line flags.

Architecture:
    1. Connect to MCP servers (with auth headers)
    2. Extract tools and convert to FunctionTool objects
    3. Attach GuardianToolGuardrail to each tool (per-server or global policy)
    4. Worker agent runs with tools= (not mcp_servers=)
    5. On each tool call:
       a. SDK calls ToolInputGuardrail (our guardian)
       b. Guardian fast-check → LLM intent evaluation
       c. allow → tool executes on MCP server
       d. reject_content → tool blocked, worker gets error message
    6. AgentHooks logs all tool start/end events for audit

Usage:
    # Config file mode (recommended)
    export OPENAI_API_KEY=sk-...
    python -m mcp_guardian.examples.mcp_guardian_demo \\
        --config guardian.yaml \\
        --task "List all files in the current directory"

    # CLI mode (quick single-server test)
    python -m mcp_guardian.examples.mcp_guardian_demo \\
        --url https://mcp.example.com/mcp \\
        --task "List all files in the current directory"

    # CLI mode with policy file
    python -m mcp_guardian.examples.mcp_guardian_demo \\
        --url https://mcp.example.com/mcp \\
        --policy policies/desktop-commander-readonly.yaml \\
        --task "Read document.txt and summarize it"

    # CLI mode with inline policy
    python -m mcp_guardian.examples.mcp_guardian_demo \\
        --url https://mcp.example.com/mcp \\
        --task "Read document.txt and summarize it" \\
        --expected-workflow "Read the specified document, summarize contents" \\
        --forbidden-tools "execute_command,http_send,write_file"

    # CLI mode with bearer token auth
    python -m mcp_guardian.examples.mcp_guardian_demo \\
        --url https://mcp.example.com/mcp \\
        --header "Authorization: Bearer my-token" \\
        --header "X-API-Key: my-key" \\
        --task "List files"
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from contextlib import AsyncExitStack

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from mcp_guardian.intent_policy import IntentPolicy
from mcp_guardian.config import GuardianConfig, ServerConfig
from mcp_guardian.guardian_hooks import (
    GuardianToolGuardrail,
    GuardianAgentHooks,
    run_guarded_session,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("mcp_guardian_demo")


# ---------------------------------------------------------------------------
# MCP server connection
# ---------------------------------------------------------------------------

async def connect_mcp_servers(
    server_configs: list[ServerConfig],
    stack: AsyncExitStack,
) -> list:
    """Connect to MCP servers using the Agents SDK."""
    from agents.mcp import MCPServerSse

    try:
        from agents.mcp import MCPServerStreamableHttp
        HAS_STREAMABLE = True
    except ImportError:
        HAS_STREAMABLE = False

    connected = []
    for cfg in server_configs:
        if not cfg.url:
            logger.warning("Skipping server %s: no URL", cfg.name)
            continue

        headers = cfg.get_expanded_headers()

        try:
            if cfg.transport in ("streamable-http", "streamable_http") and HAS_STREAMABLE:
                srv = await stack.enter_async_context(
                    MCPServerStreamableHttp(
                        name=cfg.name,
                        params={"url": cfg.url, "headers": headers},
                        cache_tools_list=True,
                    )
                )
            else:
                srv = await stack.enter_async_context(
                    MCPServerSse(
                        name=cfg.name,
                        params={"url": cfg.url, "headers": headers},
                        cache_tools_list=True,
                    )
                )
            connected.append(srv)
            logger.info("Connected to MCP server: %s (%s)", cfg.name, cfg.transport)
        except Exception as e:
            logger.warning("Failed to connect to %s: %s", cfg.name, e)

    return connected


# ---------------------------------------------------------------------------
# Per-server guarded session (supports per-server policies)
# ---------------------------------------------------------------------------

async def run_multi_server_guarded_session(
    task: str,
    servers: list,
    config: GuardianConfig,
    server_configs: list[ServerConfig],
) -> dict:
    """
    Run a guarded session with per-server policy enforcement.

    Each server gets its own GuardianToolGuardrail with the policy
    assigned to it in the config. Tools from servers without a policy
    get the default policy.
    """
    from agents import Agent, Runner
    from agents.mcp.util import MCPUtil
    from mcp_guardian.guardian_hooks import (
        GuardianToolGuardrail,
        GuardianAgentHooks,
        _sanitize_schema,
    )

    start_time = time.time()
    guardrails = {}  # server_name → GuardianToolGuardrail
    all_tools = []
    all_discovered = []

    for srv, srv_cfg in zip(servers, server_configs):
        policy = config.get_policy(srv_cfg.name)
        if policy is None:
            logger.warning(
                "No policy for server '%s' — using permissive default",
                srv_cfg.name,
            )
            policy = IntentPolicy(
                name=f"default-{srv_cfg.name}",
                description="Default permissive policy",
                expected_workflow="Use tools as needed for the task",
            )

        guardrail = GuardianToolGuardrail(
            policy=policy,
            guardian_model=config.get_effective_guardian_model(),
            guardian_base_url=config.guardian_base_url,
            guardian_api_key=config.guardian_api_key,
        )
        guardrails[srv_cfg.name] = guardrail

        # Wrap tools from this server
        guarded_tools = await guardrail.wrap_mcp_tools([srv])
        all_tools.extend(guarded_tools)

        discovered = [
            {"name": t.name, "description": (t.description or "")[:200]}
            for t in guarded_tools
        ]
        all_discovered.extend(discovered)

        logger.info(
            "Server '%s': %d tools guarded with policy '%s'",
            srv_cfg.name, len(guarded_tools), policy.name,
        )

    # Create worker agent (picks the first guardrail for hooks — all share audit)
    primary_guardrail = list(guardrails.values())[0]
    hooks = GuardianAgentHooks(guardrail=primary_guardrail)

    worker = Agent(
        name="Guardian-Worker",
        model=config.model,
        instructions=(
            f"You are a worker agent. Your task: {task}\n\n"
            f"Use the available tools to complete the task. "
            f"If a tool call is blocked by the guardian, do not retry it — "
            f"report what happened to the user."
        ),
        tools=all_tools,
        hooks=hooks,
    )

    try:
        result = await asyncio.wait_for(
            Runner.run(worker, task),
            timeout=config.timeout,
        )
        output = str(result.final_output) if result.final_output else ""
    except asyncio.TimeoutError:
        output = f"Timed out after {config.timeout}s"
    except Exception as exc:
        output = f"Error: {exc}"
        logger.error("Worker execution failed: %s", exc)

    duration = time.time() - start_time

    # Merge audit logs from all guardrails
    merged_audit = []
    merged_summary = {
        "total_evaluations": 0, "allowed": 0,
        "blocked": 0, "escalated": 0,
    }
    policies_used = []
    for name, gr in guardrails.items():
        summary = gr.get_audit_summary()
        merged_audit.extend([e.to_dict() for e in gr.audit_log])
        merged_summary["total_evaluations"] += summary["total_evaluations"]
        merged_summary["allowed"] += summary["allowed"]
        merged_summary["blocked"] += summary["blocked"]
        merged_summary["escalated"] += summary["escalated"]
        policies_used.append(f"{name}:{summary['policy']}")

    merged_summary["policies"] = policies_used

    return {
        "output": output,
        "audit_log": merged_audit,
        "summary": merged_summary,
        "tool_count": merged_summary["total_evaluations"],
        "blocked_count": merged_summary["blocked"],
        "duration_seconds": round(duration, 2),
        "discovered_tools": all_discovered,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(
        description="Guardian Demo: protect MCP servers with pre-execution intent enforcement"
    )

    # Config file mode
    parser.add_argument("--config", help="Path to guardian.yaml config file")

    # CLI mode: server
    parser.add_argument("--url", help="MCP server URL (CLI mode)")
    parser.add_argument("--name", default="TestServer", help="Server name")
    parser.add_argument("--transport", default="streamable-http",
                        choices=["streamable-http", "sse"],
                        help="Transport type")
    parser.add_argument("--header", action="append", default=[],
                        help="HTTP header as 'Key: Value' (repeatable)")

    # Task
    parser.add_argument("--task", default=None,
                        help="Task for the worker agent")

    # Model settings
    parser.add_argument("--model", default="gpt-4o", help="OpenAI model")
    parser.add_argument("--guardian-model", default=None,
                        help="Model for guardian evaluator (defaults to --model)")
    parser.add_argument("--timeout", type=int, default=120)

    # Policy (CLI mode)
    parser.add_argument("--policy", default=None,
                        help="Path to policy file (YAML or JSON)")
    parser.add_argument("--policy-name", default="mcp-guardian",
                        help="Inline policy name")
    parser.add_argument("--expected-workflow", default=None,
                        help="Expected workflow description")
    parser.add_argument("--allowed-tools", default=None,
                        help="Comma-separated allowed tools")
    parser.add_argument("--forbidden-tools", default=None,
                        help="Comma-separated forbidden tools")
    parser.add_argument("--constraints", default=None,
                        help="Comma-separated constraints")

    return parser.parse_args()


def parse_headers(header_list: list[str]) -> dict[str, str]:
    """Parse 'Key: Value' header strings into a dict."""
    headers = {}
    for h in header_list:
        if ":" not in h:
            logger.warning("Ignoring malformed header: %s", h)
            continue
        key, value = h.split(":", 1)
        headers[key.strip()] = value.strip()
    return headers


async def main():
    args = parse_args()

    if not os.environ.get("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY not set")
        sys.exit(1)

    # ---------------------------------------------------------------
    # Build config: either from file or from CLI args
    # ---------------------------------------------------------------
    if args.config:
        config = GuardianConfig.from_file(args.config)
        server_configs = config.servers
    elif args.url:
        headers = parse_headers(args.header)
        srv = ServerConfig(
            name=args.name,
            url=args.url,
            transport=args.transport,
            headers=headers,
        )
        # Build or load policy
        if args.policy:
            policy = IntentPolicy.from_file(args.policy)
        else:
            policy = IntentPolicy(
                name=args.policy_name,
                description=args.expected_workflow or "General MCP tool usage under guardian supervision",
                expected_workflow=args.expected_workflow or (
                    "Use the available tools to complete the user's task. "
                    "Do not access sensitive files, execute dangerous commands, "
                    "or send data to external endpoints."
                ),
                allowed_tools=args.allowed_tools.split(",") if args.allowed_tools else [],
                forbidden_tools=args.forbidden_tools.split(",") if args.forbidden_tools else [],
                constraints=args.constraints.split(",") if args.constraints else [
                    "Do not access files outside the working directory",
                    "Do not execute destructive commands",
                    "Do not send data to external URLs",
                    "Do not modify system configuration",
                ],
            )
        config = GuardianConfig(
            servers=[srv],
            model=args.model,
            guardian_model=args.guardian_model,
            timeout=args.timeout,
        )
        config._default_policy_obj = policy
        server_configs = [srv]
    else:
        print("Error: provide --config guardian.yaml or --url <server-url>")
        sys.exit(1)

    # Override model settings from CLI if provided
    if args.model != "gpt-4o":
        config.model = args.model
    if args.guardian_model:
        config.guardian_model = args.guardian_model

    # ---------------------------------------------------------------
    # Print banner
    # ---------------------------------------------------------------
    print(f"\n{'='*70}")
    print(f"MCP Guardian — Pre-Execution Enforcement")
    print(f"{'='*70}")
    print(f"Servers: {[s.name for s in server_configs]}")
    for sc in server_configs:
        p = config.get_policy(sc.name)
        pname = p.name if p else "(no policy)"
        auth = "yes" if sc.headers else "no"
        print(f"  • {sc.name}: {sc.url} [policy={pname}, auth={auth}]")
    print(f"Mode: ToolInputGuardrail (blocks BEFORE execution)")
    print()

    # ---------------------------------------------------------------
    # Get task
    # ---------------------------------------------------------------
    task = args.task
    if not task:
        task = input("Enter task for the worker agent: ").strip()
        if not task:
            print("No task provided.")
            sys.exit(1)

    print(f"Task: {task}")
    print(f"{'='*70}\n")

    # ---------------------------------------------------------------
    # Run guarded session
    # ---------------------------------------------------------------
    async with AsyncExitStack() as stack:
        servers = await connect_mcp_servers(server_configs, stack)
        if not servers:
            print("Error: Could not connect to any MCP servers")
            sys.exit(1)

        result = await run_multi_server_guarded_session(
            task=task,
            servers=servers,
            config=config,
            server_configs=server_configs,
        )

    # ---------------------------------------------------------------
    # Print results
    # ---------------------------------------------------------------
    print(f"\n{'='*70}")
    print(f"Results — Pre-Execution Enforcement")
    print(f"{'='*70}")
    print(f"Duration: {result['duration_seconds']}s")

    if result["discovered_tools"]:
        print(f"\nDiscovered tools ({len(result['discovered_tools'])}):")
        for t in result["discovered_tools"]:
            print(f"  • {t['name']}: {t['description'][:80]}")

    if result["output"]:
        print(f"\nAgent output:")
        print(f"  {result['output'][:500]}")

    if result["audit_log"]:
        print(f"\nGuardian audit trail ({len(result['audit_log'])} evaluations):")
        for entry in result["audit_log"]:
            icon = {"allow": "✓", "block": "✗", "escalate": "?"}[entry["verdict"]]
            phase = entry.get("phase", "pre")
            method = entry["method"]
            print(
                f"  {icon} [{phase}] {entry['tool_name']} → "
                f"{entry['verdict'].upper()} "
                f"(conf={entry['confidence']:.2f}, "
                f"method={method}, "
                f"{entry['elapsed_ms']:.0f}ms)"
            )
            if entry["verdict"] != "allow":
                print(f"    Reason: {entry['reason']}")
            if entry.get("risk_indicators"):
                print(f"    Risk: {entry['risk_indicators']}")

    summary = result["summary"]
    print(f"\nSummary:")
    print(f"  Allowed: {summary['allowed']}, Blocked: {summary['blocked']}, "
          f"Escalated: {summary['escalated']}")
    if summary.get("policies"):
        print(f"  Policies: {', '.join(summary['policies'])}")

    if result["blocked_count"] > 0:
        print(f"\n⚠ Guardian blocked {result['blocked_count']} tool call(s) "
              f"BEFORE execution!")

    # Write full result
    output_file = os.path.join(os.path.dirname(__file__), "guardian_result.json")
    result["enforcement_mode"] = "pre-execution (ToolInputGuardrail)"
    with open(output_file, "w") as f:
        json.dump(result, f, indent=2, default=str)
    print(f"\nFull result: {output_file}")


if __name__ == "__main__":
    asyncio.run(main())
