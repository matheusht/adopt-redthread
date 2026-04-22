# Reviewed Staging Write Demo

This is the first bounded write lane.

It is still very controlled.

It only runs when all of this is true:
- case is classified as `live_reviewed_write_staging`
- method is `POST`, `PUT`, or `PATCH`
- case is not destructive
- case is not admin, payment, or account family
- case stays single-tenant
- operator provides an approved write context file
- write context says `target_env: staging`
- write context includes explicit per-case approval for method, path, headers, and body

---

## Write context shape

```json
{
  "approved": true,
  "target_env": "staging",
  "target_base_url": "https://staging.example.com",
  "target_hosts": ["staging.example.com"],
  "case_approvals": {
    "post_api_v1_user_preferences": {
      "method": "POST",
      "path": "/api/v1/user/preferences",
      "headers": {
        "authorization": "Bearer stage-token"
      },
      "json_body": {
        "theme": "dark"
      }
    }
  }
}
```

Do not commit real secrets.
Do not point this at production.

---

## Command

```bash
python3 scripts/run_bridge_pipeline.py \
  /path/to/write_review_capture.har \
  runs/reviewed_write_pipeline \
  --ingestion zapi \
  --run-live-safe-replay \
  --allow-reviewed-writes \
  --write-context /path/to/approved_write_context.json
```

---

## What this proves

It proves the bridge can now:
- distinguish safe reads from reviewed writes
- keep writes out of auto-run
- require staging-only target approval
- require explicit per-case approved request bodies
- execute a bounded write lane with evidence saved to `live_safe_replay.json`

Still honest:
- this is not destructive execution
- this is not prod write execution
- this is not multi-step workflow replay
