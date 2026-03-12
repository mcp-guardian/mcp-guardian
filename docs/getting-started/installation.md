# Installation

## From PyPI

```bash
pip install mcp-guardian
```

For YAML config/policy support (recommended):

```bash
pip install mcp-guardian[yaml]
```

For development with tests:

```bash
pip install mcp-guardian[dev]
```

## From Source

```bash
git clone https://github.com/mcp-guardian/mcp-guardian.git
cd mcp-guardian
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Requirements

- Python 3.10+
- [OpenAI Agents SDK](https://github.com/openai/openai-agents-python) (`openai-agents>=0.0.5`)
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
