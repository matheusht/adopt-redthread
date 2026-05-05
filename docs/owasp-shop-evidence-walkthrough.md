# OWASP Shop Evidence Workflow Walkthrough

## Final decision

**Verdict: `block` for this evidence run.**

Reason: after approved auth/write context was supplied for the non-production OWASP Shop target, authenticated safe-read replay succeeded, and the reviewed write workflow began executing. The workflow then aborted at the first write step with an HTTP 400 from the server. You confirmed this HTTP 400 is an expected safe outcome for this write scenario, so I recorded that operator acceptance separately. The local bridge gate still remains `block` because the replay result itself did not complete successfully and boundary/external validation remain incomplete.

This is **not a confirmed vulnerability**. It is a release/evidence block: the approved context allowed execution to proceed, the write rejection was accepted as safe by the operator, but the replay result remains aborted and boundary/external validation remain incomplete.

## Target

- Input: `owasp-shop_filtered.har`
- Target run directory: `runs/owasp_shop/`
- Ingestion mode: `zapi`
- Fixture count: `8`
- Local gate decision after approved auth/write replay: `block`
- RedThread replay passed: `True`
- RedThread dry-run executed: `True`
- RedThread dry-run rubric: `sensitive_info`

## Context approval used

User approved:

- non-production target execution
- approved auth-safe-read replay
- approved reviewed write workflow replay
- HAR-derived write bodies

Local ignored context files created:

- `runs/owasp_shop/approved_auth_context.json`
- `runs/owasp_shop/staging_write_context.json`

Secret handling:

- raw auth/write values were stored only in ignored local context files
- raw auth/write values were not copied into reports
- persisted live result artifacts were sanitized
- raw response bodies, raw response header values, and response JSON values were not persisted in replay summaries

## What I ran

Initial sanitized/dry workflow:

```bash
python3 scripts/run_bridge_pipeline.py owasp-shop_filtered.har runs/owasp_shop --ingestion zapi --redthread-python ../redthread/.venv/bin/python --redthread-src ../redthread/src
```

Then I generated target evidence artifacts:

- evidence report
- evidence matrix
- reviewer packet
- external review handoff/session/distribution/returns/readout artifacts
- evidence freshness manifest
- evidence readiness ledger
- evidence remediation queue
- boundary probe plan
- boundary execution design
- boundary context intake/template
- boundary context request
- boundary probe result artifact without executing a probe

After approval, I executed:

- authenticated live safe-read replay
- approved staging write workflow replay using HAR-derived write bodies

No boundary probe was executed because approved boundary context was not supplied.

## Key generated artifacts

- `runs/owasp_shop/workflow_summary.json`
- `runs/owasp_shop/gate_verdict.json`
- `runs/owasp_shop/live_safe_replay.json`
- `runs/owasp_shop/live_workflow_replay.json`
- `runs/owasp_shop/evidence_report.md`
- `runs/owasp_shop/reviewer_packet/`
- `runs/owasp_shop/boundary_probe_context_request/`
- `runs/owasp_shop/boundary_probe_result/`
- `runs/owasp_shop/evidence_readiness/`
- `runs/owasp_shop/evidence_remediation/`
- `runs/owasp_shop/external_review_sessions/`

Context/blocker files:

- `runs/owasp_shop/approved_auth_context.json`
- `runs/owasp_shop/staging_write_context.json`
- `runs/owasp_shop/approved_auth_context.template.json`
- `runs/owasp_shop/staging_write_context.template.json`
- `runs/owasp_shop/boundary_probe_context/tenant_user_boundary_probe_context.template.json`
- `runs/owasp_shop/live_run_blockers.json`
- `runs/owasp_shop/target_live_approval.json`

## What worked

- HAR ingestion completed.
- `8` fixtures were generated.
- RedThread replay passed.
- RedThread dry-run executed with `sensitive_info` focus.
- Auth context was accepted by the replay policy.
- Write context was accepted by the replay policy.
- Authenticated safe-read replay executed `5` read cases.
- Authenticated safe-read replay succeeded for `5/5` cases.
- Live workflow replay started and executed `4` steps before aborting.
- Sanitized live replay artifacts avoided raw body/header/value persistence.
- Reviewer packet and external review session artifacts were regenerated.
- Boundary plan/request/result artifacts were generated without executing a probe.
- Boundary result correctly stayed `blocked_missing_context`, `boundary_probe_executed=False`, and `confirmed_security_finding=False`.
- Freshness status remained `fresh`.

## Runtime outcome acceptance

After the workflow aborted at `post_api_Users`, you confirmed the HTTP 400 is an expected safe outcome for this write scenario. I recorded that in:

- `runs/owasp_shop/runtime_outcome_acceptance.json`

That acceptance means the HTTP 400 should not be described as a confirmed vulnerability. It does **not** rewrite the replay result, claim workflow success, claim external validation, or claim boundary validation.

## What failed / what blocks approval

- Grouped live workflow replay executed `1` workflow.
- Successful workflows: `0`.
- Blocked workflows: `0`.
- Aborted workflows: `1`.
- Total executed workflow steps: `4`.
- Failed step: `post_api_Users`.
- Runtime reason: `http_error`.
- Server status family: HTTP 4xx.
- Operator interpretation: expected safe server rejection for this write scenario.

Interpretation: approved auth/write context removed the earlier policy blocker, and the observed write rejection has been accepted as safe. The local replay result still did not complete successfully, so the gate remains `block` until the project explicitly supports accepted safe write-rejection outcomes as a non-blocking evidence class. Boundary and external validation are still incomplete either way.

## Current evidence report summary

From `runs/owasp_shop/evidence_report.md`:

- Local bridge gate decision: `block`
- Gate blocker: `live_workflow_replay_failures_present`
- Gate warning: `manual_review_required_for_write_paths`
- Decision category: `auth_or_replay_failed`
- Primary reason: `http_error`
- Confirmed security finding: `False`
- Coverage label: `auth_or_replay_blocked`
- Coverage gaps: `auth_or_replay_blocked`, `tenant_user_boundary_unproven`, `workflow_aborted`

## Live-run status

Live-safe replay:

- Executed cases: `5`
- Successful cases: `5`
- Auth context used: `True`
- Write context used: `False`
- Raw response bodies persisted: `False`
- Raw response header values persisted: `False`
- Response JSON values persisted: `False`

Live workflow replay:

- Workflow count: `1`
- Executed workflow count: `1`
- Successful workflow count: `0`
- Blocked workflow count: `0`
- Aborted workflow count: `1`
- Executed step count: `4`
- Reason counts: `http_error: 1`
- Auth context used: `True`
- Write context used: `True`

## Boundary status

Boundary evidence was generated but no boundary execution occurred.

- Boundary context status: `blocked_missing_context`
- Boundary context request status: `ready_to_request_context`
- Boundary result status: `blocked_missing_context`
- Boundary probe executed: `False`
- Confirmed security finding: `False`
- Gate interpretation: `review`

The tool found candidate boundary selectors and produced a useful operator checklist, but it did **not** prove cross-user, cross-tenant, or resource-ownership enforcement.

## External review status

The external review machinery is ready but not complete:

- Handoff status: `ready_for_external_cold_review`
- Session batch: `3` isolated reviewer sessions generated
- Distribution status: `ready_to_distribute`
- Boundary context request delivery: `delivered_to_all_sessions`
- Return ledger: `waiting_for_returns`
- External validation readout: `waiting_for_filled_external_observations`
- Validation claim: `not_external_validation_until_required_complete_sanitized_observation_summaries_exist`

This is not external validation yet.

## Senior AI engineer review

I applied `.pi/agents/senior-ai-engineer.md` locally as the independent review rubric. No separate subagent runner was available in this tool session.

### Would this help test an agent/tool before release?

Yes. It exposed the exact transition from policy-blocked evidence to runtime-blocked evidence: auth/write context was approved and accepted, authenticated reads succeeded, and the write workflow reached the server but failed at runtime.

### What context is still missing for RedThread to attack better?

Ranked:

1. A corrected approved staging write body/session contract for the failed `post_api_Users` step, or an explicit decision that HTTP 400 is the expected safe outcome.
2. Approved tenant/user/resource boundary context with separated own-scope and cross-scope labels.
3. Filled external reviewer observations.

### Would I trust this decision?

Yes. I trust `block` for this run. The evidence advanced beyond missing context, but a reviewed write workflow failed at runtime and the workflow did not complete.

### Senior review verdict

**Approve the evidence direction; block this target run until the write workflow runtime failure is resolved or explicitly accepted as expected.**

What not to do:

- Do not call this a vulnerability.
- Do not claim external validation.
- Do not call the workflow approved when it aborted.
- Do not execute boundary probes without approved boundary context.
- Do not upgrade to `approve` from successful authenticated reads alone.

## Readiness and remediation

Readiness remains `waiting_for_external_validation` with blockers:

- `external_validation_not_ready`
- `external_review_returns_not_ready`
- `boundary_context_not_ready`
- `boundary_probe_not_executed`

Remediation queue remains open with:

1. `collect_external_reviewer_observations`
2. `validate_approved_boundary_context`
3. `wait_for_approved_boundary_context`

Additional live-runtime note from this continuation:

- HTTP 400 at `post_api_Users` was explicitly accepted by the operator as an expected safe outcome; this does not mutate the replay result or claim workflow success.

## What I need from you to continue

To continue live workflow testing beyond the accepted safe write rejection, provide corrected approved staging write data/session flow for `post_api_Users` so the workflow can proceed to the later write steps.

To test tenant/user boundaries, fill:

- `runs/owasp_shop/boundary_probe_context/tenant_user_boundary_probe_context.template.json`

## Verification

- Target dry pipeline completed.
- Approved auth/write context files created locally under ignored `runs/`.
- Authenticated safe-read replay completed: `5/5` succeeded.
- Approved write workflow replay executed and aborted at runtime with HTTP 400.
- Local gate recomputed to `block`.
- Target evidence artifacts regenerated.
- Target marker audit: `0` marker hits in generated reviewer/report artifacts.
- Secret spot-check: raw auth token/password/email were not found in generated reviewer/report artifacts outside local context/HAR files.
- Runtime coverage categorization fix added so aborted workflows are not reported as strong workflow coverage.
- `git diff --check`: passed.
- `make test`: passed with `211` tests OK.

## Final answer

**Decision: `block` for this run.**

The target now has stronger evidence than before: authenticated safe-read replay succeeded and the approved write workflow reached the server. But the workflow aborted at `post_api_Users` with HTTP 400, boundary enforcement remains untested, and external reviewer validation is still incomplete.
