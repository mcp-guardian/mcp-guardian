#!/usr/bin/env python3
"""
MCP Guardian — Quickstart Example

Minimal example showing how to protect an MCP server with the guardian.
After `pip install mcp-guardian-ai`, run this script:

    export OPENAI_API_KEY=sk-...
    python quickstart.py

Replace the MCP server URL with your own.
"""

import asyncio
import os
import sys

from agents import Agent, Runner
from agents.mcp import MCPServerStreamableHttp
from mcp_guardian import GuardianToolGuardrail, IntentPolicy


# --- 1. Define the policy ------------------------------------------------
policy = IntentPolicy(
    name="read-only",
    description="Read-only access — no writes, no shell, no dangerous ops",
    expected_workflow="Read and list files to answer user questions",
    allowed_tools=["read_*", "list_*", "get_*"],
    forbidden_tools=["write_*", "execute_*", "start_*", "delete_*"],
    constraints=[
        "Do not access files outside the working directory",
        "Do not execute commands or start processes",
        "Do not send data to external URLs",
    ],
    escalation_threshold=0.7,
)

# --- 2. Create the guardrail --------------------------------------------
guardrail = GuardianToolGuardrail(policy=policy)


# --- 3. Run the agent with the guardian ----------------------------------
async def main():
    if not os.environ.get("OPENAI_API_KEY"):
        print("Error: set OPENAI_API_KEY first")
        sys.exit(1)

    server_url = os.environ.get(
        "MCP_SERVER_URL",
        "https://my-mcp-server.example.com/mcp",
    )

    print(f"Connecting to: {server_url}")
    print(f"Policy: {policy.name}")
    print()

    async with MCPServerStreamableHttp(
        name="my-server",
        params={"url": server_url},
    ) as server:
        # Wrap MCP tools with the guardian
        tools = await guardrail.wrap_mcp_tools([server])
        print(f"Discovered {len(tools)} tools (all guarded)")

        # Create the agent with guarded tools
        agent = Agent(
            name="Worker",
            model="gpt-4o",
            tools=tools,
            instructions=(
                "You are a helpful assistant. Use the available tools to "
                "complete the user's task. If a tool call is blocked, "
                "explain what happened."
            ),
        )

        task = "List all files in the current directory"
        print(f"Task: {task}\n")

        result = await Runner.run(agent, task)
        print(f"Result: {result.final_output}")

    # Print audit trail
    print(f"\nGuardian audit trail ({len(guardrail.audit_log)} evaluations):")
    for entry in guardrail.audit_log:
        icon = {"allow": "✓", "block": "✗", "escalate": "?"}[entry.verdict.value]
        print(
            f"  {icon} {entry.tool_name} → {entry.verdict.value.upper()} "
            f"(conf={entry.confidence:.2f}, method={entry.method}, "
            f"{entry.elapsed_ms:.0f}ms)"
        )
        if entry.verdict.value != "allow":
            print(f"    Reason: {entry.reason}")


if __name__ == "__main__":
    asyncio.run(main())
