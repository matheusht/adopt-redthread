# Adopt RedThread Project Direction

## Bottom Line

Adopt RedThread should become an evidence bridge for agent-builder security assurance, not a general scanner and not a fake autonomous attack platform. The main use now is simple: take Adopt/ZAPI/NoUI discovery artifacts, turn them into inspectable workflow and RedThread evidence, then make a conservative `approve`, `review`, or `block` decision. Yes, we should execute requests, but only inside the current safety envelope: deterministic demos, safe reads, and reviewed staging writes with explicit approved context. The next direction is not more integrations; it is making one reviewer-facing proof path boringly clear, then moving the generic evidence contract upstream into RedThread.

## Current Reality

What exists now is a real prototype bridge, not a full production loop.

Evidence in this repo:

- `README.md` defines the system honestly: Adopt discovers/builds tool surfaces, this repo turns them into security-testable evidence, RedThread evaluates normalized inputs, and the local bridge gate emits `approve`, `review`, or `block`.
- `docs/architecture.md` shows the current ownership split: Adopt owns discovery and builder UX, RedThread owns generic attack/evaluation/hardening, and `adopt-redthread` owns schema mapping, replay plans, integration demos, and the current local gate.
- `scripts/run_bridge_pipeline.py` is the one-input pipeline that can ingest ZAPI, NoUI, or Adopt action artifacts, generate bridge outputs, optionally run live safe/workflow replay, call RedThread replay/dry-run paths, and emit a workflow summary.
- `scripts/prepublish_gate.py` is the current final decision point. RedThread replay evidence is an input; RedThread is not yet the final bridge gate owner.
- `scripts/build_evidence_report.py` turns a run directory into a human-readable report with decision, workflow evidence, binding evidence, RedThread evidence, and plain-English blocker reasons.
- `scripts/build_evidence_matrix.py` produces an approve/review/block matrix with three decision agents:
  - `ReleaseApprovalAgent` for clean approve cases
  - `SecurityReviewAgent` for manual-review cases
  - `SafetyBlockAgent` for fail-closed cases
- `runs/evidence_matrix/evidence_matrix.md` currently demonstrates:
  - `approve`: deterministic safe-read binding demo
  - `review`: deterministic reviewed-write demo
  - `block`: Victoria HAR block example due to missing approved staging write context
- `docs/reviewed-write-reference-demo.md` documents the deterministic reviewed-write proof path: one command, one evidence report, correct result `review`.
- `docs/reviewer-validation-loop.md` documents the cold-review protocol, observation summary, and multi-review validation rollup.
- `docs/zapi-reference-demo.md` documents the real ATP/ZAPI reference and correctly preserves `review`, not `approve`, because write paths require manual review.
- `fixtures/reference_demos/victoria_expected_block.json` captures a sanitized Victoria block expectation without committing raw HAR or run artifacts.

Current proof level:

- Artifact translation works for ZAPI/HAR, first NoUI MCP shape, and Adopt action samples.
- Bridge-owned workflow replay works for bounded safe/read and reviewed-write scenarios.
- Response binding evidence exists: planned, applied, unapplied, and failed.
- RedThread replay and dry-run handoff are real.
- The local gate can produce `approve`, `review`, and `block` from combined bridge + RedThread evidence.

Current limits:

- No direct pull from real Adopt services yet.
- No broad NoUI coverage beyond the first MCP manifest/tools shape.
- No full production publish gate.
- No fully autonomous live Adopt -> RedThread attack loop.
- RedThread does not yet independently own live workflow execution for Adopt-managed sessions.
- Real write execution is only safe with explicit approved non-production staging context.

External direction check:

- OWASP LLM guidance identifies excessive agency as a major LLM risk when systems can call tools/functions and perform actions; the recommended direction is scoping, deterministic controls, threat modeling, authorization, and observability, which matches this repo's conservative gate model.[^owasp-llm06]
- MCP security guidance warns about authorization/confused-deputy risks and stresses explicit consent and least privilege for tool-connected systems, which supports blocking writes without approved context.[^mcp-security]
- OWASP's MCP Tool Poisoning page describes tool metadata/results as an indirect prompt-injection attack surface, which supports the project's focus on tool/runtime evidence rather than trusting discovered tool descriptions blindly.[^owasp-mcp-poisoning]

## Main Use Case Now

The wedge is **evidence-backed workflow assurance for agent-built tools before they are trusted or published**.

In plain English:

> "Show me what this discovered/generated tool can do, what evidence was replayed, what RedThread said, and whether it should be approved, reviewed, or blocked."

This is useful before:

- publishing an Adopt-generated tool/action
- approving an MCP/NoUI tool surface
- trusting an agent workflow that touches authenticated or write-capable operations
- showing a buyer or reviewer a concrete safety artifact instead of a claim

The product is not yet "RedThread automatically attacks every app live." The product today is "RedThread-informed evidence and gate decisions for discovered agent/tool workflows."

## Latest AI Engineer Feedback Direction

A target AI engineer reviewed ATP Tennis, Gainly, and Venice evidence and confirmed the core wedge: the reports help pre-release agent/tool testing and conservative `review` / `block` decisions are trusted.

The main lesson is not to hand-fix each run. The next effort should strengthen the engine around decision reason taxonomy, coverage confidence, automatic attack-brief synthesis, targeted rubric selection, tenant/user boundary detection, auth/replay diagnostics, and binding review auditability.

Durable direction memo: [`docs/next-efforts-ai-engineer-feedback.md`](next-efforts-ai-engineer-feedback.md).

## Should We Execute Requests?

### Safe to run now

Run these because they are deterministic, local, read-only, or explicitly bounded:

- `make demo-hero-binding-truth`
- `make demo-reviewed-write-reference`
- `make evidence-report`
- `make evidence-matrix`
- `make evidence-packet`
- `make evidence-external-review-handoff` (sanitized handoff packaging only; not validation by itself)
- `make evidence-external-review-sessions` (isolated reviewer folders from sanitized handoff only; not validation by itself)
- `make evidence-external-validation-readout` (sanitized summary/readout state only; missing summaries remain non-validation)
- `make evidence-freshness` (hash/freshness checks for sanitized reviewer-facing copies only; stale copies mean regenerate, not a security finding)
- `make evidence-readiness` (one-page sanitized readiness ledger; current no-reviewer state remains waiting, not validation)
- `make evidence-external-review-distribution` (sanitized per-review send list and expected summary paths; ready to distribute is not validation)
- `make evidence-external-review-returns` (sanitized per-review return/follow-up ledger; does not read filled observation markdown or copy free-form reviewer answers)
- `make evidence-remediation-queue` (ordered local work queue from sanitized readiness/distribution blockers; does not execute probes or contact reviewers)
- `make evidence-boundary-probe-plan` (plan-only artifact; no live execution)
- `make evidence-boundary-execution-design` (design-only contract; no live execution)
- `make evidence-boundary-probe-result` (sanitized result template/validator; no live execution; current default is `blocked_missing_context`)
- `make check-zapi-reference` when the local ignored HAR/run artifacts are present
- `make test`
- `scripts/run_bridge_pipeline.py` against sanitized fixture inputs
- live safe-read GET replay only when the policy class allows it and no secrets are exposed
- RedThread replay/dry-run against generated normalized inputs

### Safe only with approved staging context

Run these only after a human supplies and approves non-production context:

- reviewed auth-safe reads that require approved auth headers/session context
- reviewed non-destructive staging writes
- Victoria-style write workflows
- any workflow that needs request bodies, IDs, auth headers, cookies, or app-specific values from a real session

Required conditions:

- target is non-production or explicitly approved for test execution
- approved auth/write context is supplied
- target host and environment are pinned
- request bodies are reviewed
- no production mutation is possible
- evidence report records what was executed and why the outcome is `review` or `block`

### Not safe / do not run

Do not run:

- production writes
- destructive operations
- broad authenticated replay using copied session cookies without explicit approval
- automatic RedThread live attacks against real Adopt-managed sessions
- hidden retries that mutate state
- replay against unknown third-party targets
- anything that requires exposing raw HAR/session/cookie/header/body data in docs or git

Victoria is the correct example: the system blocked because no approved staging write context was supplied. That is a good safety result, not a failure to hide.

## What Approve / Review / Block Means

| Decision | Meaning today | What it proves | What it does not prove |
|---|---|---|---|
| `approve` | Workflow evidence and RedThread replay passed with no blockers or review warnings. | The tested path matched the expected safe evidence envelope. | It does not prove the whole app is safe or production-integrated. |
| `review` | Evidence passed, but risk requires a human checkpoint, usually because write paths are present. | The bridge can preserve risk semantics instead of forcing a happy-path approve. | It does not authorize silent publish or production mutation. |
| `block` | Required evidence/context is missing, workflow execution failed/blocked, or RedThread replay failed. | The system can fail closed and explain why. | It does not mean the app is bad; it means this run is not publishable as-is. |

## Direction Options

### 1. Make the evidence report and matrix the product surface

- **Value:** Highest near-term value. A reviewer can inspect one report/matrix and understand what was tested, what passed, what requires review, and what blocked.
- **Risk:** Could become a polished artifact without real buyer pull if not tested with users.
- **Scope fit:** Excellent. It uses what already exists and does not expand the system boundary.
- **CEO view:** Approve. This is the narrowest wedge: proof people can read.
- **CTO view:** Approve with changes. Hide complexity behind fewer commands and one evidence artifact; keep raw run files local.
- **Office Hours view:** The demand test is still weak. Watch one real target reviewer read it silently.
- **Recommendation:** Primary direction for the next week.

### 2. Upstream a tiny generic RedThread evidence contract

- **Value:** Strong long-term leverage. RedThread should eventually own generic replay verdicts, evidence schemas, promotion-gate recommendations, and attack/judge/defend loops.
- **Risk:** Premature upstreaming can freeze the wrong schema before reviewer comprehension is proven.
- **Scope fit:** Good if tiny and generic; bad if Adopt-specific names leak into RedThread.
- **CEO view:** Approve later, after the proof artifact survives user review.
- **CTO view:** Approve with changes. The generic engine should own generic evidence; `adopt-redthread` should stay glue.
- **Office Hours view:** Do not build architecture because it feels clean. Build it after someone understands and wants the evidence.
- **Recommendation:** Secondary direction, gated by reviewer feedback.

### 3. Execute more real requests against captured apps

- **Value:** Produces stronger real-world proof and exposes integration gaps.
- **Risk:** High if it touches production, sessions, cookies, or writes without approved context.
- **Scope fit:** Medium. Safe reads fit; reviewed staging writes fit; autonomous live attacks do not fit yet.
- **CEO view:** Selective approve. Real proof matters, but one uncontrolled live run can derail the story.
- **CTO view:** Defer broad execution. Keep execution policy-gated and explicit.
- **Office Hours view:** Useful only if it maps to a real buyer workflow. "We ran more requests" is not demand.
- **Recommendation:** Run safe reads and approved staging writes only. Keep Victoria blocked until approved staging context exists.

### 4. Give RedThread more application context so attacks are better

- **Value:** High. More context from NoUI/MCP/tool manifests, action semantics, auth strategy, parameter shapes, workflow hints, and response bindings can make RedThread attacks more realistic.
- **Risk:** Can become a large schema project without better findings.
- **Scope fit:** Good if context is normalized and generic; bad if it becomes a one-off Adopt parser inside RedThread.
- **CEO view:** Approve with discipline. Better context is leverage, but only if it improves evidence quality.
- **CTO view:** Approve with changes. Feed context quietly under the hood; do not add operator burden.
- **Office Hours view:** The target user will not buy "more context." They buy "caught a dangerous workflow before publish."
- **Recommendation:** Add only the smallest context fields that improve RedThread attack/replay quality and appear in evidence.

### 5. Integrate another scanner/tool

- **Value:** Could increase coverage quickly.
- **Risk:** High scope drift. The repo becomes a wrapper around tools instead of a clear Adopt -> RedThread bridge.
- **Scope fit:** Poor now.
- **CEO view:** Reject for now. Focus beats breadth.
- **CTO view:** Reject for now. RedThread should not become a wrapper around external scanners.
- **Office Hours view:** Tool integrations are not demand validation.
- **Recommendation:** Do not do this until the core proof path has real reviewer/buyer pull.

### 6. Customer/user validation before more architecture

- **Value:** Highest business de-risking. It tests whether the evidence artifact is understandable and valuable.
- **Risk:** Low, except it may reveal the product is not framed correctly.
- **Scope fit:** Excellent.
- **CEO view:** Strong approve. Demand beats architecture.
- **CTO view:** Approve. Use findings to remove friction before adding features.
- **Office Hours view:** Mandatory. Sit behind a target reviewer and watch where they get confused.
- **Recommendation:** Do this immediately.

## Recommended Path

Primary direction: **make the reviewer-facing evidence path unmistakably clear.**

The project should optimize for one credible workflow:

```text
Discovery artifact
  -> normalized fixtures
  -> workflow replay evidence
  -> RedThread replay/dry-run evidence
  -> evidence report + matrix
  -> approve / review / block
```

Secondary direction: **prepare a tiny generic RedThread evidence contract, but do not upstream it until one real reviewer understands the current report.** The current local proposal is [`docs/redthread-evidence-contract-proposal.md`](redthread-evidence-contract-proposal.md); it is proposal-only and deliberately avoids new integration plumbing.

Decision rule:

- If a change makes the evidence easier to inspect, safer to execute, or more useful to RedThread, consider it.
- If a change adds a new integration, new platform surface, or new autonomous execution path without improving proof quality, defer it.

## Long-Term Direction

### 3-month direction

Goal: make Adopt RedThread a credible local/reference implementation for agent-tool workflow assurance.

What should exist:

- one stable operator command that produces a report and matrix from a supported input
- deterministic approve/review/block examples that are generated and tested
- one real sanitized reference run that remains truthful as `review`
- Victoria preserved as a sanitized `block` example
- clearer evidence wording for non-expert reviewers
- a small set of generic RedThread runtime/evidence fields proposed upstream
- at least one silent reviewer observation recorded
- a three-review validation rollup when enough complete cold-review summaries exist
- external human reviewer validation after the current no-tools AI cold-review readout

Success standard:

- A security engineer, AI engineer, or founder can read the evidence report without explanation and answer:
  - what input was tested
  - what workflow ran
  - what RedThread evaluated
  - why the gate approved/reviewed/blocked
  - what is not proven

### 6-month direction

Goal: move generic assurance logic closer to RedThread while keeping Adopt-specific glue here.

What should exist:

- RedThread-owned generic evidence schema for replay verdicts, dry-run evidence, workflow/control facts, and promotion-gate recommendations
- `adopt-redthread` acting mostly as an adapter from Adopt/ZAPI/NoUI artifacts into that schema
- stronger RedThread attack generation using normalized context:
  - operation purpose
  - read/write/destructive classification
  - auth requirements
  - parameter shapes
  - response fields and bindings
  - workflow ordering
- approved-staging execution path for one real customer-like app, not production
- CI-style or pre-publish demo gate that consumes evidence without pretending to be production-ready

Success standard:

- The system catches or blocks at least one realistic unsafe agent/tool workflow that a target reviewer agrees matters.

### 12-month direction

Goal: become the reference safety layer for agent-builder workflows: discover tools, test them, produce evidence, and prevent unsafe publish.

What the product should become:

- a security assurance layer for generated/discovered agent tools
- a bridge from builder-plane artifacts into RedThread's attack/judge/defend/regress loop
- a reviewer-friendly gate that explains risk in operational terms
- eventually, an enterprise pre-publish control for tool/action releases

What RedThread should own:

- generic attack generation
- replay evaluation
- dry-run and later live execution engines
- judge/defend/validate/regress loops
- generic promotion gate recommendations
- generic evidence schemas
- finding confirmation and severity truth

What `adopt-redthread` should own:

- Adopt/ZAPI/NoUI-specific ingestion
- HAR and discovery-artifact normalization
- integration demos and reference fixtures
- local operator workflows while the integration is still experimental
- mapping source artifacts into RedThread-owned generic contracts

Integrations worth considering later:

- more NoUI/MCP output families
- direct Adopt service pull only after artifact proof has demand
- CI/release-system gate adapters
- private registry or tool-governance layer for MCP/tool approval
- browser/session capture helpers that preserve explicit approval and least privilege

Integrations to avoid now:

- generic scanner aggregation
- Strix-style platform expansion unless it directly improves the proof path
- outreach automation
- production release enforcement before buyer/user validation
- broad autonomous live attacks

What must be proven before expanding scope:

- one target reviewer understands the report without a walkthrough
- one real-world reviewed workflow produces evidence a buyer cares about
- the system blocks unsafe execution in a way the buyer agrees is correct
- RedThread context improvements produce better attacks/findings, not just prettier schemas
- raw artifact safety remains intact

## 1-Week Execution Plan

1. Rebuild the current evidence matrix locally with `make evidence-matrix`.
2. Give only `runs/evidence_matrix/evidence_matrix.md` and `runs/reviewed_write_reference/evidence_report.md` to one target reviewer.
3. Watch silently. Do not explain first.
4. Record where they get confused:
   - input tested
   - workflow executed
   - binding evidence
   - RedThread evidence
   - why `review`, not `approve`
   - why Victoria blocks
   - what is not proven
5. Edit report wording only where comprehension fails.
6. Keep Victoria as the `block` row. Do not try to turn it into a success case without approved staging context.
7. Draft a tiny RedThread evidence-contract proposal only after the reviewer test.
8. Do not add another integration this week.

## Do Not Do

- Do not run production writes.
- Do not mark write-path evidence as `approve` just to make the demo look better.
- Do not commit raw `runs/` artifacts, HARs, cookies, headers, sessions, or request/response bodies.
- Do not add another scanner/tool integration yet.
- Do not move Adopt-specific parsing into RedThread.
- Do not pretend RedThread owns live workflow execution today.
- Do not build a broad platform before one buyer/reviewer understands the proof artifact.
- Do not optimize for "more requests executed" over "better evidence and safer decisions."
- Do not let the evidence matrix become self-referential; it must answer a real reviewer's question.

## Open Questions

- Who is the first target reviewer: security engineer, AI engineer, founder, or buyer?
- What concrete workflow would they be willing to judge as valuable if blocked before publish?
- What minimum app context would materially improve RedThread's attacks: auth model, tool schema, workflow order, data sensitivity, or tenant boundary?
- Should the final `approve/review/block` gate eventually move into RedThread, or should RedThread emit recommendations while the bridge/product layer owns the final business decision?
- What is the first non-production target where approved staging write context can be safely supplied?

[^owasp-llm06]: OWASP GenAI Security Project, "LLM06:2025 Excessive Agency," https://genai.owasp.org/llmrisk/llm06/
[^mcp-security]: Model Context Protocol, "Security Best Practices," https://modelcontextprotocol.io/specification/latest/basic/security_best_practices
[^owasp-mcp-poisoning]: OWASP Foundation, "MCP Tool Poisoning," https://owasp.org/www-community/attacks/MCP_Tool_Poisoning
