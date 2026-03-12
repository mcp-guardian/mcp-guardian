"""
Tests for _sanitize_schema() — the compatibility shim between MCP server
tool schemas and OpenAI's strict function calling mode.

Every MCP server produces its own JSON Schema for tools, and OpenAI only
accepts a subset. These tests verify that _sanitize_schema() handles the
full range of real-world MCP schema patterns.
"""

import pytest
from mcp_guardian.guardian_hooks import _sanitize_schema


class TestBasicStructure:
    """Root-level object requirements."""

    def test_root_gets_additional_properties_false(self):
        schema = {"type": "object", "properties": {"x": {"type": "string"}}}
        result = _sanitize_schema(schema)
        assert result["additionalProperties"] is False

    def test_root_without_type_gets_additional_properties(self):
        schema = {"description": "bare root"}
        result = _sanitize_schema(schema, is_root=True)
        assert result["additionalProperties"] is False

    def test_required_auto_generated(self):
        schema = {
            "type": "object",
            "properties": {"a": {"type": "string"}, "b": {"type": "integer"}},
        }
        result = _sanitize_schema(schema)
        assert sorted(result["required"]) == ["a", "b"]

    def test_existing_required_preserved(self):
        schema = {
            "type": "object",
            "properties": {"a": {"type": "string"}, "b": {"type": "integer"}},
            "required": ["a"],
        }
        result = _sanitize_schema(schema)
        assert result["required"] == ["a"]

    def test_empty_properties_added_to_bare_object(self):
        schema = {"type": "object"}
        result = _sanitize_schema(schema)
        assert result["properties"] == {}
        assert result["required"] == []


class TestAdditionalProperties:
    """OpenAI requires additionalProperties: false on all objects."""

    def test_additional_properties_true_replaced(self):
        schema = {
            "type": "object",
            "properties": {"x": {"type": "string"}},
            "additionalProperties": True,
        }
        result = _sanitize_schema(schema)
        assert result["additionalProperties"] is False

    def test_additional_properties_schema_replaced(self):
        """Some MCP servers use additionalProperties: {type: string}."""
        schema = {
            "type": "object",
            "properties": {},
            "additionalProperties": {"type": "string"},
        }
        result = _sanitize_schema(schema)
        assert result["additionalProperties"] is False

    def test_nested_additional_properties_stripped(self):
        schema = {
            "type": "object",
            "properties": {
                "options": {
                    "type": "object",
                    "additionalProperties": True,
                    "properties": {},
                }
            },
        }
        result = _sanitize_schema(schema)
        assert result["properties"]["options"]["additionalProperties"] is False


class TestFormatStripping:
    """OpenAI rejects format on string properties."""

    def test_format_uri_stripped(self):
        schema = {"type": "string", "format": "uri"}
        result = _sanitize_schema(schema, is_root=False)
        assert "format" not in result

    def test_format_date_time_stripped(self):
        schema = {"type": "string", "format": "date-time"}
        # date-time is not in the explicit set but we strip ALL formats now
        result = _sanitize_schema(schema, is_root=False)
        assert "format" not in result

    def test_format_email_stripped(self):
        schema = {"type": "string", "format": "email"}
        result = _sanitize_schema(schema, is_root=False)
        assert "format" not in result

    def test_format_ipv4_stripped(self):
        schema = {"type": "string", "format": "ipv4"}
        result = _sanitize_schema(schema, is_root=False)
        assert "format" not in result

    def test_format_in_nested_property(self):
        """Real-world: fetch MCP server has url with format: uri."""
        schema = {
            "type": "object",
            "properties": {
                "url": {"type": "string", "format": "uri", "description": "URL to fetch"},
            },
        }
        result = _sanitize_schema(schema)
        assert "format" not in result["properties"]["url"]
        assert result["properties"]["url"]["type"] == "string"


class TestConstraintStripping:
    """OpenAI rejects type-specific constraints."""

    def test_string_constraints_stripped(self):
        schema = {"type": "string", "minLength": 1, "maxLength": 255, "pattern": "^[a-z]+$"}
        result = _sanitize_schema(schema, is_root=False)
        assert "minLength" not in result
        assert "maxLength" not in result
        assert "pattern" not in result
        assert result["type"] == "string"

    def test_numeric_constraints_stripped(self):
        schema = {"type": "number", "minimum": 0, "maximum": 100, "multipleOf": 5}
        result = _sanitize_schema(schema, is_root=False)
        assert "minimum" not in result
        assert "maximum" not in result
        assert "multipleOf" not in result

    def test_array_constraints_stripped(self):
        schema = {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 1,
            "maxItems": 10,
            "uniqueItems": True,
        }
        result = _sanitize_schema(schema, is_root=False)
        assert "minItems" not in result
        assert "maxItems" not in result
        assert "uniqueItems" not in result
        assert result["items"]["type"] == "string"

    def test_object_constraints_stripped(self):
        schema = {
            "type": "object",
            "properties": {"x": {"type": "string"}},
            "minProperties": 1,
            "maxProperties": 5,
        }
        result = _sanitize_schema(schema, is_root=False)
        assert "minProperties" not in result
        assert "maxProperties" not in result


class TestMissingType:
    """OpenAI requires every property to have a type."""

    def test_typeless_property_defaults_to_string(self):
        schema = {"description": "some value"}
        result = _sanitize_schema(schema, is_root=False)
        assert result["type"] == "string"

    def test_typeless_with_anyof_kept(self):
        schema = {"anyOf": [{"type": "string"}, {"type": "integer"}]}
        result = _sanitize_schema(schema, is_root=False)
        assert "type" not in result
        assert "anyOf" in result

    def test_typeless_with_oneof_kept(self):
        schema = {"oneOf": [{"type": "string"}, {"type": "null"}]}
        result = _sanitize_schema(schema, is_root=False)
        assert "type" not in result
        assert "oneOf" in result


class TestAnnotationStripping:
    """OpenAI doesn't use these and they add noise."""

    def test_title_stripped(self):
        schema = {"type": "string", "title": "My Field"}
        result = _sanitize_schema(schema, is_root=False)
        assert "title" not in result

    def test_examples_stripped(self):
        schema = {"type": "string", "examples": ["foo", "bar"]}
        result = _sanitize_schema(schema, is_root=False)
        assert "examples" not in result

    def test_default_stripped(self):
        schema = {"type": "string", "default": "hello"}
        result = _sanitize_schema(schema, is_root=False)
        assert "default" not in result

    def test_description_preserved(self):
        """description IS used by OpenAI for tool understanding."""
        schema = {"type": "string", "description": "The URL to fetch"}
        result = _sanitize_schema(schema, is_root=False)
        assert result["description"] == "The URL to fetch"


class TestRefAndMeta:
    """JSON Schema meta-keywords that OpenAI doesn't support."""

    def test_ref_stripped(self):
        schema = {"$ref": "#/definitions/Foo"}
        result = _sanitize_schema(schema, is_root=False)
        assert "$ref" not in result

    def test_defs_stripped(self):
        schema = {
            "type": "object",
            "properties": {"x": {"type": "string"}},
            "$defs": {"Foo": {"type": "string"}},
        }
        result = _sanitize_schema(schema)
        assert "$defs" not in result

    def test_schema_keyword_stripped(self):
        schema = {"$schema": "http://json-schema.org/draft-07/schema#", "type": "string"}
        result = _sanitize_schema(schema, is_root=False)
        assert "$schema" not in result


class TestAllOfFlattening:
    """allOf should be flattened into the parent."""

    def test_allof_merged(self):
        schema = {
            "allOf": [
                {"type": "object", "properties": {"a": {"type": "string"}}},
                {"properties": {"b": {"type": "integer"}}},
            ]
        }
        result = _sanitize_schema(schema, is_root=False)
        assert "allOf" not in result
        assert "a" in result["properties"]
        assert "b" in result["properties"]

    def test_allof_required_merged(self):
        schema = {
            "allOf": [
                {"required": ["a"], "properties": {"a": {"type": "string"}}},
                {"required": ["b"], "properties": {"b": {"type": "integer"}}},
            ]
        }
        result = _sanitize_schema(schema, is_root=False)
        assert "a" in result["required"]
        assert "b" in result["required"]


class TestConditionals:
    """if/then/else/not are not supported."""

    def test_if_then_else_stripped(self):
        schema = {
            "type": "object",
            "properties": {"x": {"type": "string"}},
            "if": {"properties": {"x": {"const": "a"}}},
            "then": {"properties": {"y": {"type": "string"}}},
            "else": {"properties": {"z": {"type": "integer"}}},
        }
        result = _sanitize_schema(schema)
        assert "if" not in result
        assert "then" not in result
        assert "else" not in result

    def test_not_stripped(self):
        schema = {"type": "string", "not": {"enum": ["bad"]}}
        result = _sanitize_schema(schema, is_root=False)
        assert "not" not in result


class TestRealWorldMCPSchemas:
    """Schemas from actual MCP servers we've encountered."""

    def test_desktop_commander_read_file(self):
        """DesktopCommander: object with additionalProperties and no properties."""
        schema = {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "offset": {"default": 0, "type": "number"},
                "length": {"default": 1000, "type": "number"},
                "options": {
                    "additionalProperties": True,
                    "properties": {},
                    "type": "object",
                },
            },
            "required": ["path"],
        }
        result = _sanitize_schema(schema)
        assert result["additionalProperties"] is False
        opts = result["properties"]["options"]
        assert opts["additionalProperties"] is False
        assert opts["type"] == "object"
        # default values stripped
        assert "default" not in result["properties"]["offset"]

    def test_desktop_commander_edit_block_content(self):
        """DesktopCommander: property with no type (union)."""
        schema = {
            "type": "object",
            "properties": {
                "file_path": {"type": "string"},
                "content": {},  # no type — intentionally a union
            },
            "required": ["file_path"],
        }
        result = _sanitize_schema(schema)
        assert result["properties"]["content"]["type"] == "string"

    def test_fetch_mcp_server(self):
        """Fetch MCP server: url with format: uri."""
        schema = {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "format": "uri",
                    "description": "URL to fetch",
                },
                "max_length": {
                    "type": "integer",
                    "default": 5000,
                    "minimum": 0,
                    "maximum": 1000000,
                    "description": "Maximum response length",
                },
                "raw": {
                    "type": "boolean",
                    "default": False,
                    "description": "Return raw HTML",
                },
            },
            "required": ["url"],
        }
        result = _sanitize_schema(schema)
        url_prop = result["properties"]["url"]
        assert "format" not in url_prop
        assert url_prop["type"] == "string"
        ml_prop = result["properties"]["max_length"]
        assert "minimum" not in ml_prop
        assert "maximum" not in ml_prop
        assert "default" not in ml_prop

    def test_deeply_nested_schema(self):
        """Schema with multiple nesting levels."""
        schema = {
            "type": "object",
            "properties": {
                "config": {
                    "type": "object",
                    "properties": {
                        "filters": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "field": {"type": "string", "minLength": 1},
                                    "value": {"type": "string", "pattern": "^[a-z]+$"},
                                },
                            },
                            "minItems": 1,
                        },
                    },
                },
            },
        }
        result = _sanitize_schema(schema)
        filters = result["properties"]["config"]["properties"]["filters"]
        assert "minItems" not in filters
        item = filters["items"]
        assert item["additionalProperties"] is False
        assert "minLength" not in item["properties"]["field"]
        assert "pattern" not in item["properties"]["value"]


class TestIdempotency:
    """Sanitizing an already-clean schema should be a no-op."""

    def test_clean_schema_unchanged(self):
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "A name"},
                "count": {"type": "integer"},
            },
            "required": ["name", "count"],
            "additionalProperties": False,
        }
        result = _sanitize_schema(schema)
        assert result == schema

    def test_double_sanitize_idempotent(self):
        schema = {
            "type": "object",
            "properties": {
                "url": {"type": "string", "format": "uri"},
                "options": {"additionalProperties": True, "type": "object"},
            },
        }
        first = _sanitize_schema(schema)
        second = _sanitize_schema(first)
        assert first == second
