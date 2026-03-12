# IntentPolicy

`mcp_guardian.IntentPolicy` — defines expected agent behavior as a whitelist.

## Class Definition

```python
@dataclass
class IntentPolicy:
    name: str
    description: str
    expected_workflow: str
    allowed_tools: list[str] = []
    forbidden_tools: list[str] = []
    allowed_transitions: dict[str, list[str]] = {}
    constraints: list[str] = []
    escalation_threshold: float = 0.7
```

## Constructor

```python
policy = IntentPolicy(
    name="my-policy",
    description="What this policy is for",
    expected_workflow="Natural language description of the expected workflow",
    allowed_tools=["read_file", "list_directory"],
    forbidden_tools=["execute_command", "write_file"],
    allowed_transitions={
        "list_directory": ["read_file"],
        "read_file": ["read_file"],
    },
    constraints=[
        "No file modifications",
        "No shell commands",
    ],
    escalation_threshold=0.7,
)
```

## Methods

### `fast_check(tool_name, prior_tools) → Optional[VerdictResult]`

Deterministic pre-filter. Returns a `VerdictResult` if the decision is clear-cut (forbidden tool, not in whitelist, invalid transition). Returns `None` if LLM evaluation is needed.

```python
verdict = policy.fast_check("write_file", ["read_file"])
if verdict:
    print(f"{verdict.verdict}: {verdict.reason}")
# Output: block: Tool 'write_file' is explicitly forbidden by policy 'my-policy'
```

### `to_prompt_context() → str`

Renders the policy as a markdown string for the guardian LLM prompt.

### `to_dict() → dict`

Serializes the policy to a dictionary.

### `from_dict(data) → IntentPolicy` (classmethod)

Creates a policy from a dictionary.

### `from_file(path) → IntentPolicy` (classmethod)

Loads from a YAML or JSON file (auto-detected by extension).

```python
policy = IntentPolicy.from_file("policies/read-only.yaml")
```

### `from_yaml(path) → IntentPolicy` (classmethod)

Loads from a YAML file. Requires `pyyaml`.

### `from_json(path) → IntentPolicy` (classmethod)

Loads from a JSON file.

### `to_yaml(path) → None`

Writes the policy to a YAML file.

## Related Types

### PolicyVerdict

```python
class PolicyVerdict(str, Enum):
    ALLOW = "allow"
    BLOCK = "block"
    ESCALATE = "escalate"
```

### VerdictResult

```python
@dataclass
class VerdictResult:
    verdict: PolicyVerdict
    tool_name: str
    tool_args: dict
    reason: str
    policy_name: str
    confidence: float = 1.0
    step_number: int = 0
    prior_tools: list[str] = []
```
