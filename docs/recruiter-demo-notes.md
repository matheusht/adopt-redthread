# Recruiter Demo Notes

## Main story

Lead with `redthread/` first.

That is the stronger proof of:
- original architecture
- security thinking
- multi-agent design
- replay and hardening discipline

Then show `adopt-redthread/` as the personalized extension.

## Short pitch

> RedThread is my standalone autonomous AI red-teaming and self-hardening project.
> Adopt RedThread is a targeted integration repo that shows how I would use RedThread to harden a real agent-builder stack with ZAPI-style discovery, replay packs, and pre-publish security gates.

## What this repo proves

- I can connect research systems to real product workflows
- I can work at the seam between platform engineering and AI security
- I think in terms of release gates, not just demos
- I can tailor a project to a company without losing core architecture discipline

## Best demo order

1. show RedThread identity
2. show why Adopt is the builder plane
3. show why RedThread is the attack/validation plane
4. show the ZAPI intake → fixture generation → replay path
5. show what the next pre-publish gate would look like

## Avoid

Do not present this repo as replacing RedThread.

Present it as:
- a bridge repo
- a practical integration layer
- a personalized extension for real-world agent security
