# Sanitized intent review manual test guide

This guide validates the full sanitized intent review pipeline, including the optional offline LLM-agent path, without exposing raw HARs or running live endpoint requests.

## Preconditions

- Work from the repository root.
- Use an existing sanitized HAR batch, for example `runs/har_batches/latest`.
- Do not paste raw HARs, raw URLs, paths, headers, cookies, request/response bodies, auth values, app IDs, secrets, or app field names into any LLM.

## 1. Deterministic minimum viable proof

```bash
rm -rf runs/har_batches/latest/intent_review
make evidence-intent-review HAR_BATCH_OUTPUT=runs/har_batches/latest
python3 -m unittest tests.test_sanitized_intent_review
```

Expected artifacts:

```text
runs/har_batches/latest/intent_review/intent_review_context.json
runs/har_batches/latest/intent_review/intent_review.json
runs/har_batches/latest/intent_review/intent_review.md
runs/har_batches/latest/intent_review/redthread_evidence_export.json
runs/har_batches/latest/intent_review/advancement_summary.json
runs/har_batches/latest/intent_review/advancement_summary.md
runs/har_batches/latest/intent_review/business_validation_plan.json
runs/har_batches/latest/intent_review/schema_validation.json
runs/har_batches/latest/intent_review/redthread_evidence_contract_preview.json
runs/har_batches/latest/intent_review/privacy_audit.json
```

Expected pass checks:

```bash
python3 - <<'PY'
import json
from pathlib import Path
out = Path('runs/har_batches/latest/intent_review')
assert json.loads((out / 'privacy_audit.json').read_text())['passed'] is True
assert json.loads((out / 'schema_validation.json').read_text())['passed'] is True
export = json.loads((out / 'redthread_evidence_export.json').read_text())
assert export['promotion_semantics']['redthread_evaluation_required'] is True
assert export['promotion_semantics']['confirmed_security_finding_claimed'] is False
assert export['promotion_semantics']['release_gate_override'] is False
print('deterministic intent review proof passed')
PY
```

## 1a. Phase 1–3 context intake proof

```bash
rm -rf runs/har_batches/latest/intent_review_with_context
make evidence-intent-review \
  HAR_BATCH_OUTPUT=runs/har_batches/latest \
  INTENT_REVIEW_OUTPUT=runs/har_batches/latest/intent_review_with_context \
  INTENT_REVIEW_BOUNDARY_RUBRIC=fixtures/sanitized_intent_review/boundary_rubric.example.json \
  INTENT_REVIEW_REVIEWER_OBSERVATIONS=fixtures/sanitized_intent_review/reviewer_observations.example.json
```

Expected impact: proof subjects with reviewer observations should show more specific advisory intent labels, context signals, and reviewer questions. Subjects without reviewer observations should remain cautious. RedThread evaluation remains required before any security conclusion.

## 2. Prepare the sanitized LLM-agent prompt

```bash
rm -rf runs/har_batches/latest/intent_review_llm_manual
make evidence-intent-review \
  HAR_BATCH_OUTPUT=runs/har_batches/latest \
  INTENT_REVIEW_OUTPUT=runs/har_batches/latest/intent_review_llm_manual \
  INTENT_REVIEW_AGENT_MODE=llm \
  INTENT_REVIEW_PREPARE_LLM_PROMPT=1
```

Expected artifacts at this point:

```text
runs/har_batches/latest/intent_review_llm_manual/intent_review_context.json
runs/har_batches/latest/intent_review_llm_manual/llm_intent_review_prompt.json
```

No `intent_review.json` is expected yet because the model output has not been supplied.

## 3. Run the LLM agent manually

Give the LLM agent only this file:

```text
runs/har_batches/latest/intent_review_llm_manual/llm_intent_review_prompt.json
```

Ask it to write only a JSON object matching `adopt_redthread.sanitized_intent_review.v0` to:

```text
runs/har_batches/latest/intent_review_llm_manual/llm_review_output.json
```

The LLM output must keep the same subject IDs as `sanitized_context.subjects`, must use sanitized context only, and must not claim findings, severity, scanner output, exploitability, live execution, final local decisions, or release overrides.

If no LLM provider is configured locally, you can still validate the offline LLM ingestion path with a schema-valid fixture output:

```bash
python3 - <<'PY'
import json
from pathlib import Path
from scripts.build_sanitized_intent_review import build_intent_review_context, build_intent_review
batch = Path('runs/har_batches/latest')
out = batch / 'intent_review_llm_manual'
out.mkdir(parents=True, exist_ok=True)
review = build_intent_review(build_intent_review_context(batch))
(out / 'llm_review_output.json').write_text(json.dumps(review, indent=2, sort_keys=True) + '\n', encoding='utf-8')
print(out / 'llm_review_output.json')
PY
```

## 4. Validate LLM-agent output through the guarded pipeline

```bash
python3 scripts/build_sanitized_intent_review.py \
  --batch-dir runs/har_batches/latest \
  --output-dir runs/har_batches/latest/intent_review_llm_manual \
  --agent-mode llm \
  --llm-review-output runs/har_batches/latest/intent_review_llm_manual/llm_review_output.json \
  --fail-on-marker-hit
```

Expected pass checks:

```bash
python3 - <<'PY'
import json
from pathlib import Path
out = Path('runs/har_batches/latest/intent_review_llm_manual')
for name in [
    'intent_review_context.json',
    'llm_intent_review_prompt.json',
    'llm_review_output.json',
    'intent_review.json',
    'intent_review.md',
    'redthread_evidence_export.json',
    'schema_validation.json',
    'redthread_evidence_contract_preview.json',
    'privacy_audit.json',
]:
    assert (out / name).exists(), name
assert json.loads((out / 'privacy_audit.json').read_text())['passed'] is True
assert json.loads((out / 'schema_validation.json').read_text())['passed'] is True
export = json.loads((out / 'redthread_evidence_export.json').read_text())
assert export['promotion_semantics']['redthread_evaluation_required'] is True
assert export['promotion_semantics']['confirmed_security_finding_claimed'] is False
assert export['promotion_semantics']['severity_claimed'] is False
assert export['promotion_semantics']['release_gate_override'] is False
preview = json.loads((out / 'redthread_evidence_contract_preview.json').read_text())
assert preview['status'] == 'proposal_preview_not_upstreamed'
assert preview['promotion_recommendation']['not_proven'] is True
print('llm guarded intent review proof passed')
PY
```

## 5. Validate batch workflow integration

```bash
rm -rf runs/har_batches/latest/review_workflow
make evidence-har-batch-review-workflow HAR_BATCH_OUTPUT=runs/har_batches/latest
python3 -m unittest tests.test_har_batch_review_workflow
```

Expected artifacts:

```text
runs/har_batches/latest/review_workflow/phase_6_sanitized_intent_review.json
runs/har_batches/latest/review_workflow/phase_6_sanitized_intent_review.md
runs/har_batches/latest/intent_review/schema_validation.json
runs/har_batches/latest/intent_review/redthread_evidence_contract_preview.json
```

## 6. Full validation before merging

```bash
python3 -m py_compile scripts/build_sanitized_intent_review.py scripts/build_har_batch_review_workflow.py
python3 -m unittest tests.test_sanitized_intent_review tests.test_har_batch_review_workflow
make test
git diff --check
```

The pipeline is valid when all commands pass, `privacy_audit.json.passed` is `true`, `schema_validation.json.passed` is `true`, and RedThread evaluation remains required in every export.
