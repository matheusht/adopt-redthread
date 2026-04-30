# Deterministic Reviewed-Write Reference Demo

## Why this exists

The ATP Tennis ZAPI reference proves a real-ish reviewed-write run, but the external app can drift. A fresh live replay already showed why: external behavior can stream, timeout, mutate responses, or change session handling.

This demo gives the operator a deterministic local version of the same proof shape without requiring them to understand HAR files, auth contexts, write contexts, binding overrides, or RedThread paths.

## Operator command

Run:

```bash
make demo-reviewed-write-reference
```

That one command:

1. starts a local ATP-like HTTP server
2. writes a synthetic HAR under `runs/reviewed_write_reference/`
3. builds normalized ZAPI fixtures
4. builds the live workflow plan
5. injects approved auth/write context internally
6. injects the three approved response bindings internally
7. runs reviewed workflow replay
8. exports RedThread runtime inputs
9. runs RedThread replay/dry-run
10. emits the local gate verdict
11. writes the evidence report

Primary output:

```text
runs/reviewed_write_reference/evidence_report.md
```

You can rebuild only the report with:

```bash
make evidence-report
```

## Expected result

The correct result is **review**, not approve.

Expected evidence:

- fixture count: `5`
- workflow count: `1`
- workflow class: `reviewed_write_workflow`
- successful workflows: `1`
- blocked workflows: `0`
- aborted workflows: `0`
- declared response bindings: `3`
- applied response bindings: `3`
- RedThread replay passed: `true`
- RedThread dry-run executed: `true`
- local gate decision: `review`
- gate warning: `manual_review_required_for_write_paths`

## Endpoint shape

The local server mimics the ATP chat workflow:

```text
GET  /api/chats
POST /api/chats
POST /api/chat
```

The synthetic HAR also includes two historical chat reads so the normalized fixture shape matches the real ATP-style run with five fixtures.

## Why this hides complexity correctly

The operator should not need to know the internal files required for safe replay:

- approved auth context
- approved staging write context
- response binding override contract
- RedThread runtime input path
- replay-plan path
- gate-verdict path

Those still exist as generated artifacts for inspection, but the command owns the setup. The operator sees one command and one report.

## What this proves

Proven:

- a realistic reviewed-write workflow can be replayed locally without external drift
- response-derived values can be carried from `POST /api/chats` into `POST /api/chat`
- body and header bindings both apply
- RedThread replay/dry-run evidence can be generated from the bridge artifacts
- the local gate preserves safety semantics and returns `review`

Not proven:

- production Adopt service integration
- real publish-system enforcement
- broad authenticated write coverage
- external ATP app stability
- RedThread independently owning live workflow execution
