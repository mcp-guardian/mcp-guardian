"""
Tests for wildcard/glob pattern matching in IntentPolicy.fast_check().

Verifies that allowed_tools and forbidden_tools support fnmatch-style
glob patterns (*, ?, [seq]) in addition to exact tool names.
"""

import pytest
from mcp_guardian.intent_policy import IntentPolicy, PolicyVerdict, _matches_any


# ---------------------------------------------------------------------------
# Unit tests for _matches_any helper
# ---------------------------------------------------------------------------

class TestMatchesAny:
    """Low-level tests for the _matches_any() helper."""

    def test_exact_match(self):
        assert _matches_any("read_file", ["read_file", "write_file"])

    def test_exact_no_match(self):
        assert not _matches_any("execute_command", ["read_file", "write_file"])

    def test_star_wildcard(self):
        assert _matches_any("read_file", ["read_*"])

    def test_star_wildcard_no_match(self):
        assert not _matches_any("write_file", ["read_*"])

    def test_question_mark(self):
        assert _matches_any("read_a", ["read_?"])
        assert not _matches_any("read_ab", ["read_?"])

    def test_bracket_pattern(self):
        assert _matches_any("tool_a", ["tool_[abc]"])
        assert not _matches_any("tool_d", ["tool_[abc]"])

    def test_star_matches_everything(self):
        assert _matches_any("anything_at_all", ["*"])

    def test_empty_patterns(self):
        assert not _matches_any("read_file", [])

    def test_mixed_exact_and_glob(self):
        assert _matches_any("write_file", ["read_*", "write_file"])
        assert _matches_any("read_config", ["read_*", "write_file"])
        assert not _matches_any("execute_cmd", ["read_*", "write_file"])

    def test_multiple_globs(self):
        patterns = ["read_*", "list_*", "get_*"]
        assert _matches_any("read_file", patterns)
        assert _matches_any("list_directory", patterns)
        assert _matches_any("get_info", patterns)
        assert not _matches_any("write_file", patterns)


# ---------------------------------------------------------------------------
# Integration tests: fast_check with glob patterns
# ---------------------------------------------------------------------------

class TestFastCheckGlobForbidden:
    """Forbidden tools with glob patterns."""

    def test_glob_forbidden_blocks(self):
        policy = IntentPolicy(
            name="test",
            description="test",
            expected_workflow="test",
            forbidden_tools=["write_*", "execute_*"],
        )
        result = policy.fast_check("write_file", [])
        assert result is not None
        assert result.verdict == PolicyVerdict.BLOCK

    def test_glob_forbidden_allows_non_matching(self):
        policy = IntentPolicy(
            name="test",
            description="test",
            expected_workflow="test",
            forbidden_tools=["write_*", "execute_*"],
        )
        result = policy.fast_check("read_file", [])
        assert result is None  # passes to LLM

    def test_exact_forbidden_still_works(self):
        policy = IntentPolicy(
            name="test",
            description="test",
            expected_workflow="test",
            forbidden_tools=["start_process"],
        )
        result = policy.fast_check("start_process", [])
        assert result is not None
        assert result.verdict == PolicyVerdict.BLOCK

    def test_star_forbidden_blocks_everything(self):
        """forbidden_tools: ['*'] blocks all tools."""
        policy = IntentPolicy(
            name="test",
            description="test",
            expected_workflow="test",
            forbidden_tools=["*"],
        )
        result = policy.fast_check("anything", [])
        assert result is not None
        assert result.verdict == PolicyVerdict.BLOCK


class TestFastCheckGlobAllowed:
    """Allowed tools with glob patterns."""

    def test_glob_allowed_permits_matching(self):
        policy = IntentPolicy(
            name="test",
            description="test",
            expected_workflow="test",
            allowed_tools=["read_*", "list_*"],
        )
        result = policy.fast_check("read_file", [])
        assert result is None  # passes

    def test_glob_allowed_blocks_non_matching(self):
        policy = IntentPolicy(
            name="test",
            description="test",
            expected_workflow="test",
            allowed_tools=["read_*", "list_*"],
        )
        result = policy.fast_check("write_file", [])
        assert result is not None
        assert result.verdict == PolicyVerdict.BLOCK

    def test_star_allowed_permits_everything(self):
        """allowed_tools: ['*'] acts as a wildcard allow-all."""
        policy = IntentPolicy(
            name="test",
            description="test",
            expected_workflow="test",
            allowed_tools=["*"],
        )
        result = policy.fast_check("anything_at_all", [])
        assert result is None  # passes

    def test_mixed_exact_and_glob_allowed(self):
        policy = IntentPolicy(
            name="test",
            description="test",
            expected_workflow="test",
            allowed_tools=["read_*", "specific_tool"],
        )
        assert policy.fast_check("read_file", []) is None
        assert policy.fast_check("specific_tool", []) is None
        result = policy.fast_check("write_file", [])
        assert result is not None
        assert result.verdict == PolicyVerdict.BLOCK


class TestFastCheckGlobCombined:
    """Both allowed and forbidden with globs."""

    def test_forbidden_takes_precedence(self):
        """If a tool matches both allowed and forbidden, forbidden wins."""
        policy = IntentPolicy(
            name="test",
            description="test",
            expected_workflow="test",
            allowed_tools=["*"],         # allow everything
            forbidden_tools=["write_*"], # except writes
        )
        # write_file matches forbidden first
        result = policy.fast_check("write_file", [])
        assert result is not None
        assert result.verdict == PolicyVerdict.BLOCK

        # read_file passes forbidden, then passes allowed
        result = policy.fast_check("read_file", [])
        assert result is None

    def test_realistic_pattern(self):
        """Real-world: allow read/list/get/search, block write/execute/kill."""
        policy = IntentPolicy(
            name="readonly-glob",
            description="Read-only via globs",
            expected_workflow="Read and search files",
            allowed_tools=["read_*", "list_*", "get_*", "search_*"],
            forbidden_tools=["write_*", "execute_*", "kill_*", "start_process"],
        )
        # Should pass
        assert policy.fast_check("read_file", []) is None
        assert policy.fast_check("list_directory", []) is None
        assert policy.fast_check("get_file_info", []) is None
        assert policy.fast_check("search_content", []) is None

        # Should block (forbidden)
        result = policy.fast_check("write_file", [])
        assert result.verdict == PolicyVerdict.BLOCK

        result = policy.fast_check("execute_command", [])
        assert result.verdict == PolicyVerdict.BLOCK

        result = policy.fast_check("start_process", [])
        assert result.verdict == PolicyVerdict.BLOCK

        # Should block (not in allowed)
        result = policy.fast_check("unknown_tool", [])
        assert result.verdict == PolicyVerdict.BLOCK


class TestBackwardCompatibility:
    """Existing exact-match behavior must be preserved."""

    def test_exact_allowed_unchanged(self):
        policy = IntentPolicy(
            name="test",
            description="test",
            expected_workflow="test",
            allowed_tools=["read_file", "list_directory"],
        )
        assert policy.fast_check("read_file", []) is None
        result = policy.fast_check("write_file", [])
        assert result.verdict == PolicyVerdict.BLOCK

    def test_exact_forbidden_unchanged(self):
        policy = IntentPolicy(
            name="test",
            description="test",
            expected_workflow="test",
            forbidden_tools=["write_file", "execute_command"],
        )
        result = policy.fast_check("write_file", [])
        assert result.verdict == PolicyVerdict.BLOCK
        assert policy.fast_check("read_file", []) is None

    def test_empty_lists_unchanged(self):
        policy = IntentPolicy(
            name="test",
            description="test",
            expected_workflow="test",
        )
        # No allowed_tools or forbidden_tools → always passes to LLM
        assert policy.fast_check("anything", []) is None

    def test_transition_graph_unchanged(self):
        policy = IntentPolicy(
            name="test",
            description="test",
            expected_workflow="test",
            allowed_transitions={"read_file": ["list_directory"]},
        )
        result = policy.fast_check("write_file", ["read_file"])
        assert result is not None
        assert result.verdict == PolicyVerdict.BLOCK
