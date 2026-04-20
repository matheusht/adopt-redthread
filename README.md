# Adopt RedThread

Adopt RedThread is the bridge repo between **Adopt AI** and **RedThread**.

It exists to prove one clear idea:

> **Adopt builds the agent plane. RedThread attacks, validates, and hardens it.**

## Why this repo exists

`redthread/` stays standalone.

That repo is the main portfolio project and should keep its own identity:
- autonomous AI red-teaming
- replay and validation
- self-healing
- runtime-truth and agentic-security work

This repo is different.
It is the integration lab for:
- ZAPI ingestion
- Adopt action/tool mapping
- NoUI target generation
- replay-pack generation
- pre-publish security gates
- recruiter-ready demos for practical agent hardening

## Repo goals

Short term:
- ingest ZAPI-discovered API metadata
- classify endpoint risk
- convert the catalog into RedThread-friendly fixtures
- generate first replay packs

Medium term:
- test Adopt-generated actions with RedThread attack suites
- add multi-turn workflow replay
- add pre-publish security gate experiments

Long term:
- become a practical reference implementation for agent-builder security assurance

## Docs

- `docs/strategy.md` — why the repo split exists and what each system owns
- `docs/architecture.md` — proposed end-to-end integration architecture
- `docs/recruiter-demo-notes.md` — how to present this repo in outreach

## Initial structure

- `adapters/zapi/` — ZAPI ingestion code
- `adapters/adopt_actions/` — Adopt action/tool catalog mapping
- `fixtures/zapi_samples/` — sample discovery artifacts
- `fixtures/replay_packs/` — generated replay suites
- `scripts/` — helper scripts and MVP entrypoints
- `examples/` — end-to-end demos

## Working rule

If logic is generic and reusable, it should probably belong upstream in `redthread/`.

If logic is Adopt-specific, integration-specific, or demo-specific, it belongs here.
