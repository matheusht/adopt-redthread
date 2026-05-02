# Evidence Freshness Manifest

## Purpose

The evidence freshness manifest checks whether generated reviewer-facing copies still match their sanitized source artifacts. It exists to catch stale handoff/session folders before a reviewer sees an outdated packet.

It is local evidence plumbing only. It is not validation, not boundary execution, and not a release approval.

## Command

```bash
make evidence-freshness
```

Default output:

```text
runs/evidence_freshness/
├── evidence_freshness_manifest.md
└── evidence_freshness_manifest.json
```

Schema:

```text
adopt_redthread.evidence_freshness_manifest.v1
```

## What it reads

Only known sanitized reviewer-facing artifacts and manifests:

- `runs/reviewed_write_reference/evidence_report.md`
- `runs/evidence_matrix/evidence_matrix.md`
- `runs/reviewer_packet/reviewer_packet.md`
- `runs/reviewer_packet/reviewer_observation_template.md`
- `runs/boundary_probe_result/tenant_user_boundary_probe_result.md`
- `runs/boundary_probe_context_request/tenant_user_boundary_probe_context_request.md`
- `runs/reviewer_packet/reviewer_packet.json`
- `runs/external_review_handoff/external_review_handoff_manifest.json`
- `runs/external_review_sessions/external_review_session_batch.json`
- copied sanitized artifacts under `runs/external_review_handoff/`
- copied sanitized artifacts under `runs/external_review_sessions/review_*/artifacts/`

## What it does not read

It must not read or copy:

- raw HAR files
- session cookies or auth headers
- request or response bodies
- source files
- production or staging write-context values
- boundary actor, tenant, resource, credential, selector, request, or response values

## Statuses

- `fresh` — all checked copies match their expected source/manifest hashes and marker audit passed.
- `stale_or_missing` — at least one checked copy is missing or no longer matches the expected hash.
- `privacy_blocked` — configured sensitive-marker audit failed.

## Checks performed

The script checks three copy layers:

1. Reviewer packet manifest entries still match source artifacts.
2. External handoff copies still match source artifacts.
3. External review session copies still match the external handoff artifact hashes.

For each copy, the JSON records:

- stage
- artifact label
- source path
- copy path
- expected source hash
- manifest hash
- actual copy hash
- status
- reason labels

## Failure semantics

A stale or missing copy means the evidence packet should be regenerated before review or distribution. It does not mean the underlying bridge run is unsafe; it means the reviewer-facing package cannot be trusted as current. For the boundary context request, freshness only proves the copied checklist matches the generated sanitized request; it does not prove context approval or boundary execution. `make evidence-external-review-distribution` consumes this status and blocks the send list when freshness is not `fresh`.

A marker hit fails closed by default. Marker checks are bounded privacy tripwires, not complete secret scanning.

## Non-claims

The freshness manifest does not prove:

- external human validation
- buyer demand
- production readiness
- whole-app safety
- boundary execution

It does not change local bridge `approve` / `review` / `block` semantics.
