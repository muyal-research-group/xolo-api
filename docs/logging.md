# Logging

Xolo emits structured logs as JSON objects.

At the application level, log payloads are built with:

- `xoloapi.log.format.build_log_payload()`

At the logger level, `xoloapi/log/__init__.py` wraps those payloads with common metadata such as timestamp, level, logger name, and thread name before serializing the record as JSON.

## Log line structure

Each emitted log entry is a JSON object with two layers of fields:

1. **Logger metadata** added by `JsonFormatter`
2. **Application payload** added by `build_log_payload()`

The common top-level metadata fields are:

| Field | Source | Meaning |
| --- | --- | --- |
| `timestamp` | `JsonFormatter` | time at which the log record was formatted |
| `level` | `logging` record | log level such as `DEBUG`, `INFO`, or `ERROR` |
| `logger_name` | logger instance | logger name configured for that module |
| `thread_name` | current thread | thread handling the work |

When the log message is a dictionary, the formatter merges that dictionary directly into the same JSON object. That is why application payload fields appear beside `timestamp`, `level`, and `logger_name` instead of being nested under a separate key.

## Application payload contract

`build_log_payload()` creates the structured payload used by controllers, services, repositories, and infrastructure code.

```python
build_log_payload(
    action: str,
    *,
    started_at: float | None = None,
    error: Any | None = None,
    **context: Any,
) -> dict[str, Any]
```

The helper always returns a flat dictionary and removes fields whose value is `None`.

### Required field

| Field | Required | Meaning |
| --- | --- | --- |
| `action` | yes | stable action name for the event being logged |

The `action` value is the anchor field for searching and grouping logs. In current code it usually follows a dot-separated pattern such as:

- `users.create`
- `users.create.error`
- `scopes.assign`
- `ngac.create_node`
- `accounts.repository.find_all.error`

## Timing field

If the caller passes `started_at`, the helper adds elapsed time:

| Field | Included when | Meaning |
| --- | --- | --- |
| `time_taken_ms` | `started_at` is provided | elapsed time in milliseconds, rounded to 2 decimals |

This is typically measured at request or operation start with `time.time()` and logged both on success and failure paths.

## Context fields

Any extra keyword arguments passed to `build_log_payload()` are copied into the payload as-is.

These are module-specific identifiers or counters that provide operational context, for example:

- `username`
- `actor_user_id`
- `node_id`
- `node_name`
- `node_type`
- `scope_name`
- `count`
- `scope_count`
- `assignment_count`

This keeps the log format consistent while letting each module attach the identifiers that matter for the current action.

## Error fields

If the caller passes an `error`, the helper enriches the payload with error information.

| Field | Included when | Meaning |
| --- | --- | --- |
| `error` | `error` is provided | string form of the error object |
| `error_code` | if present on `error.detail.code` or `error.code` | application error code |
| `error_message` | if present on `error.detail.msg`, `error.detail.message`, or `error.message` | human-readable message |
| `error_status_code` | if present on `error.detail.status_code` or `error.status_code` | HTTP or domain status code |
| `raw_error` | only when non-empty | underlying raw error detail |
| `error_metadata` | only when non-empty | structured metadata attached to the error |

The helper prefers values from `error.detail` when available. This matches the codebase convention where typed application errors carry rich detail objects and controllers translate them to HTTP exceptions.

## Success and failure patterns

The most common pattern in controllers and services is:

- log `info` for successful operations
- log `error` for failed operations
- keep the same core context fields across both branches
- append `.error` to the `action` name on failures

For example, a controller may log the same actor and target identifiers on both success and failure, which makes the two outcomes easy to compare during incident review.

## Examples

### Example: successful user creation

Code pattern:

```python
log.info(build_log_payload("users.create", started_at=t1, username=user_dto.username))
```

Representative log entry:

```json
{
  "timestamp": "2026-05-15 13:20:11,024",
  "level": "INFO",
  "logger_name": "xoloapi",
  "thread_name": "MainThread",
  "action": "users.create",
  "username": "alice",
  "time_taken_ms": 18.42
}
```

### Example: successful NGAC node creation

Code pattern:

```python
log.info(
    build_log_payload(
        "ngac.create_node",
        started_at=t1,
        actor_user_id=me.key,
        node_id=node_id,
        node_name=dto.name,
        node_type=dto.node_type.value,
    )
)
```

Representative log entry:

```json
{
  "timestamp": "2026-05-15 13:20:34,901",
  "level": "INFO",
  "logger_name": "xoloapi",
  "thread_name": "MainThread",
  "action": "ngac.create_node",
  "actor_user_id": "usr_123",
  "node_id": "node_456",
  "node_name": "Medical Staff",
  "node_type": "user_attribute",
  "time_taken_ms": 7.15
}
```

### Example: failed scope creation

Code pattern:

```python
log.error(
    build_log_payload(
        "scopes.create.error",
        started_at=t1,
        error=err,
        scope_name=dto.name,
    )
)
```

Representative log entry:

```json
{
  "timestamp": "2026-05-15 13:21:02,117",
  "level": "ERROR",
  "logger_name": "xoloapi",
  "thread_name": "MainThread",
  "action": "scopes.create.error",
  "scope_name": "ADMIN",
  "time_taken_ms": 3.98,
  "error": "Scope already exists",
  "error_code": "scope_exists",
  "error_message": "The scope ADMIN already exists",
  "error_status_code": 409
}
```

### Example: failed NGAC node lookup with richer context

Representative log entry:

```json
{
  "timestamp": "2026-05-15 13:21:27,443",
  "level": "ERROR",
  "logger_name": "xoloapi",
  "thread_name": "MainThread",
  "action": "ngac.create_node.error",
  "actor_user_id": "usr_123",
  "node_name": "Medical Staff",
  "node_type": "user_attribute",
  "time_taken_ms": 5.62,
  "error": "Validation failed",
  "error_code": "validation_error",
  "error_message": "Invalid node type transition",
  "error_status_code": 400,
  "error_metadata": {
    "from_type": "user",
    "to_type": "object_attribute"
  }
}
```

## Operational guidance

When adding or reviewing logs in this codebase, prefer:

- a stable, dot-separated `action` name
- request or domain identifiers in explicit fields
- `started_at` for elapsed-time visibility
- structured error details through the `error` parameter instead of embedding an unstructured message

This keeps logs easy to filter, aggregate, and inspect during debugging and production operations.

## Related pages

- See [Configuration](configuration.md) for logging environment variables such as `XOLO_LOG_NAME`, `XOLO_LOG_INTERVAL`, `XOLO_LOG_WHEN`, and `XOLO_LOG_PATH`.
- See [Deployment](deployment.md) for operational runtime context.
