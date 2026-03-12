# Installation

## From PyPI

```bash
pip install mcp-guardian-ai
```

This installs the core library with all dependencies (including PyYAML).

For development with tests:

```bash
pip install mcp-guardian-ai[dev]
```

## From Source (GitHub)

If you prefer to install directly from the repository:

```bash
git clone https://github.com/mcp-guardian/mcp-guardian.git
cd mcp-guardian
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

This is the recommended approach during early development, or if you want to modify the guardian code.

!!! note "Package name vs import name"
    The **PyPI package** is `mcp-guardian-ai` (what you `pip install`).
    The **Python import** is `mcp_guardian` (what you `import` in code).
    This is because the name `mcp-guardian` was already taken on PyPI.

## Requirements

- Python 3.10+
- [OpenAI Agents SDK](https://github.com/openai/openai-agents-python) (`openai-agents>=0.3.0`)
- An OpenAI API key (for LLM-based intent evaluation)

## Verify Installation

```bash
python3 -c "from mcp_guardian import IntentPolicy, GuardianToolGuardrail; print('OK')"
```

## Environment Setup

Set your OpenAI API key:

```bash
export OPENAI_API_KEY=sk-...
```

The guardian uses this key for the LLM intent evaluator. The fast-check tier (forbidden/allowed tool lists, transition graph) runs without any API call.
