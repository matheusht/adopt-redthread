# Offline HAR Evidence Batch

The offline HAR evidence batch is a local QA harness for the bridge evidence path. It is not a scanner, replay engine, autonomous attack loop, validation result, or release approval.

## Purpose

Use it when you have multiple local `.har` captures and want to see whether the existing bridge can repeatedly produce sanitized evidence, preserve `approve` / `review` / `block` gate semantics, and expose recurring engine gaps.

## Command

```bash
make evidence-har-batch \
  HAR_INPUT_DIR=./captures \
  HAR_BATCH_OUTPUT=runs/har_batches/batch_001 \
  HAR_BATCH_LIMIT=10
```

Equivalent direct command:

```bash
python3 scripts/run_har_evidence_batch.py \
  --input-dir ./captures \
  --output-dir runs/har_batches/batch_001 \
  --ingestion zapi \
  --redthread-python ../redthread/.venv/bin/python \
  --redthread-src ../redthread/src \
  --limit 10 \
  --fail-on-marker-hit
```

Manifest input is also supported. Relative `.har` entries resolve from the manifest file's directory:

```json
{"inputs": ["captures/case_001.har", "captures/case_002.har"]}
```

```bash
python3 scripts/run_har_evidence_batch.py \
  --manifest ./manifests/batch.json \
  --output-dir runs/har_batches/batch_001 \
  --fail-on-marker-hit
```

## What it does

For each explicit local `.har` input, the script:

1. assigns a sanitized subject id such as `subject_001`;
2. creates an isolated subject run directory;
3. runs the existing offline bridge workflow;
4. forces live replay, authenticated replay, write execution, and boundary execution off;
5. writes only sanitized subject artifacts to the batch output;
6. audits generated subject and batch outputs for configured sensitive markers and forbidden raw-field keys;
7. writes aggregate processed/non-processed, privacy-audit, blocker, and gap counts for engine planning.

## Outputs

```text
runs/har_batches/batch_001/
  batch_manifest.json
  batch_manifest.md
  subject_index.json
  subject_index.md
  aggregate_blockers.json
  aggregate_blockers.md
  engine_gaps.md
  privacy_audit.json
  subjects/
    subject_001/
      workflow_summary.json
      gate_verdict.json
      evidence_report.md
      subject_summary.json
      subject_summary.md
      privacy_audit.json
```

## Semantics

Processed subjects keep the bridge gate decision exactly as `approve`, `review`, or `block`. Batch processing states are separate and include `processed`, `failed`, and `privacy_blocked`. Empty or fully limited batches report batch status `no_inputs` and do not run the bridge workflow.

`batch_manifest.json` includes sanitized `input_source_type` accounting (`input_dir` or `manifest`) without persisting input paths, plus sanitized `execution_controls` accounting. In V1 all controls are false: live safe replay, live workflow replay, reviewed auth, reviewed writes, and boundary probe execution are forced off.

Do not treat batch observations as confirmed findings, severity truth, validation, regression proof, execution proof, or release approval.

## Safety boundaries

This lane must not:

- run live replay;
- reuse auth context;
- execute writes;
- probe boundaries;
- gather approval;
- send raw HARs to an LLM;
- persist raw HAR/session/cookie/header/body/request/response/app values in generated aggregate artifacts;
- introduce a new gate outcome;
- upgrade `review` or `block` to `approve`.

If a subject privacy audit fails, the subject directory is replaced with minimal sanitized `privacy_audit.json`, `subject_summary.json`, and `subject_summary.md`. With `--fail-on-marker-hit`, the command exits non-zero.
