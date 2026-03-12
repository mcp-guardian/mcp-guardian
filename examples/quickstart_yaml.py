#!/usr/bin/env python3
"""
MCP Guardian — YAML Policy Example

Shows how to load a policy from a YAML file and use the GuardianConfig
for multi-server setups.

    export OPENAI_API_KEY=sk-...
    python quickstart_yaml.py
"""

import asyncio
import os
import sys
from contextlib import AsyncExitStack

from agents import Agent, Runner
from agents.mcp import MCPServerStreamableHttp
from mcp_guardian import GuardianToolGuardrail, IntentPolicy, GuardianConfig


async def single_server_example():
    """Load a policy from YAML and guard a single server."""
    print("=" * 60)
    print("Example 1: Single server with YAML policy")
    print("=" * 60)

    # Load policy from file
    policy = IntentPolicy.from_file("policies/exfiltration-prevention.yaml")
    guardrail = GuardianToolGuardrail(policy=policy)

    print(f"Policy: {policy.name}")
    print(f"Constraints: {len(policy.constraints)}")
    for c in policy.constraints:
        print(f"  • {c}")
    print()


async def multi_server_example():
    """Load a full guardian.yaml config for multi-server setup."""
    print("=" * 60)
    print("Example 2: Multi-server with guardian.yaml")
    print("=" * 60)

    config = GuardianConfig.from_file("guardian.yaml")

    print(f"Model: {config.model}")
    print(f"Servers: {len(config.servers)}")
    for srv in config.servers:
        policy = config.get_policy(srv.name)
        print(f"  • {srv.name}: {srv.url}")
        if policy:
            print(f"    Policy: {policy.name}")
            print(f"    Forbidden: {policy.forbidden_tools}")
    print()


async def main():
    if not os.environ.get("OPENAI_API_KEY"):
        print("Error: set OPENAI_API_KEY first")
        sys.exit(1)

    # These examples just show config loading — no server connection needed
    os.chdir(os.path.join(os.path.dirname(__file__), ".."))

    await single_server_example()

    if os.path.exists("guardian.yaml") or os.path.exists("guardian.yaml.example"):
        config_file = "guardian.yaml" if os.path.exists("guardian.yaml") else "guardian.yaml.example"
        # Patch for demo
        if config_file == "guardian.yaml.example":
            print("(Using guardian.yaml.example for demo)")
        await multi_server_example()
    else:
        print("Skipping multi-server example (no guardian.yaml found)")


if __name__ == "__main__":
    asyncio.run(main())
