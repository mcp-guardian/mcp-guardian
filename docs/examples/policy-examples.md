# Policy Examples

Ready-to-use policy files for common scenarios. All shipped in the `policies/` directory.

## Read-Only Filesystem

Allow reading and listing files. Block all writes, shell access, and process execution.

```yaml
name: desktop-commander-readonly
description: Read-only access to Desktop Commander MCP server

expected_workflow: >
  List directories, read files, search for files by name or content,
  and retrieve file metadata. All operations are strictly read-only.
  No file modifications, no process execution, no config changes.

allowed_tools:
  - list_directory
  - read_file
  - read_multiple_files
  - get_file_info
  - start_search
  - get_more_search_results
  - stop_search
  - list_searches

forbidden_tools:
  - write_file
  - write_pdf
  - edit_block
  - move_file
  - create_directory
  - start_process
  - interact_with_process
  - read_process_output
  - force_terminate
  - kill_process
  - set_config_value
  - execute_command

constraints:
  - All operations must be read-only
  - No file creation, modification, or deletion
  - No process or command execution
  - No configuration changes
  - Do not access sensitive system files (/etc/shadow, etc.)

escalation_threshold: 0.7
```

## Local-Only (No Network)

Allow local file and database operations. Block all network access.

```yaml
name: local-only
description: Local file and database operations only — no network access

expected_workflow: >
  Read local files, extract information, query the database
  for matching records. All operations must be local.

allowed_tools:
  - read_file
  - query_database
  - list_files

forbidden_tools:
  - fetch_url
  - http_post
  - http_get
  - send_email
  - execute_command

allowed_transitions:
  read_file:
    - query_database
    - read_file
    - list_files
  query_database:
    - read_file
    - query_database
  list_files:
    - read_file

constraints:
  - No internet access — all operations must be local
  - No sending data externally (email, HTTP, webhooks)
  - No executing shell commands
  - File reads limited to the working directory

escalation_threshold: 0.7
```

## Database Query Only

Allow database reads. Block writes, schema changes, and admin operations.

```yaml
name: db-read-only
description: Database read queries only — no writes, no DDL, no admin

expected_workflow: >
  Execute SELECT queries to retrieve data. Aggregate, filter,
  and join as needed. No INSERT, UPDATE, DELETE, or schema changes.

allowed_tools:
  - query
  - aggregate
  - find
  - count
  - explain

forbidden_tools:
  - insert
  - update
  - delete
  - drop
  - create_collection
  - create_index
  - admin_command

constraints:
  - Only SELECT/read queries allowed
  - No data modification (INSERT, UPDATE, DELETE)
  - No schema changes (CREATE, DROP, ALTER)
  - No admin operations
  - Query results must not be sent to external endpoints

escalation_threshold: 0.8
```

## Permissive Default (Logging Only)

Allow everything but log all evaluations. Useful for monitoring before enforcing.

```yaml
name: permissive-monitor
description: Allow all tools but log every evaluation for audit

expected_workflow: >
  Use tools as needed for the task. All calls are logged for review.

constraints:
  - Log all tool calls for audit trail

escalation_threshold: 0.3
```

!!! warning
    The permissive policy doesn't block anything. Use it only for initial monitoring to understand what tools your agents are actually calling before writing restrictive policies.

## Writing Your Own

Start from one of the examples above and customize:

1. Set `forbidden_tools` to block the dangerous tools for your use case
2. Write `expected_workflow` describing the legitimate use case
3. Add `constraints` for the LLM evaluator to check
4. Optionally add `allowed_tools` for strict whitelisting
5. Optionally add `allowed_transitions` for sequence enforcement
6. Tune `escalation_threshold` (lower = more permissive, higher = more conservative)

Save as YAML in your `policies/` directory and reference from `guardian.yaml`.
