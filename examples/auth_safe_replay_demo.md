# Auth Safe Replay Demo

This is the next bounded live lane after anonymous safe reads.

It is still conservative.

It only runs when all of this is true:
- request is `GET`
- case is safe-read shaped
- auth was already seen in the captured request
- operator provides an approved auth context file
- auth context host matches the captured host
- only allowlisted auth header names are sent

---

## Auth context shape

```json
{
  "approved": true,
  "target_hosts": ["example.com"],
  "allowed_header_names": ["authorization"],
  "headers": {
    "authorization": "Bearer demo-token"
  }
}
```

Do not commit real secrets.
Use this only as a local operator file.

---

## Command

```bash
python3 scripts/run_bridge_pipeline.py \
  /path/to/auth_safe_read_capture.har \
  runs/auth_safe_read_pipeline \
  --ingestion zapi \
  --run-live-safe-replay \
  --allow-reviewed-auth \
  --auth-context /path/to/approved_auth_context.json
```

---

## What this proves

It proves the bridge can now:
- distinguish anonymous safe reads from auth-bound safe reads
- keep auth-bound cases out of auto-run by default
- run them only after explicit approval
- restrict auth forwarding to approved hosts and header names

Still honest:
- this is not full session replay
- this is not write execution
- this is not full browser-state reuse
