# Strategy

## One-line strategy

Keep **RedThread** standalone.
Use **Adopt RedThread** as the integration layer.

That gives two strong stories instead of one blurry story.

---

## Why this split is best

## RedThread should stay clean

RedThread already has a strong identity:
- autonomous AI red-teaming
- replay and promotion logic
- self-healing
- evaluation truth
- runtime truth
- agentic-security hardening

If Adopt integration gets mixed into the core repo too early, the story gets muddy.

Bad outcomes:
- harder to explain to recruiters
- harder to keep generic abstractions clean
- easier to overfit the project to one ecosystem
- harder to show what RedThread is by itself

## Adopt RedThread should be the practical bridge

This repo should show how RedThread fits around a real agent-building stack.

That means:
- Adopt AI owns the builder plane
- RedThread owns the adversarial assurance plane
- this repo owns the connection between them

---

## Role split

## Adopt AI role

Adopt AI is the **builder plane**.

It discovers and assembles agent capabilities:
- API discovery
- tool generation
- action generation
- workflow authoring
- test/draft/publish flow

Useful components:
- **ZAPI** — API discovery from real browser traffic
- **NoUI** — website-to-API or MCP generation for browser-native targets
- **ABCD** — build/test/publish workflow discipline
- **AdoptXchange** — eval and integration patterns

## RedThread role

RedThread is the **security assurance plane**.

It should:
- attack tools and actions
- replay known failures
- validate fixes
- test authorization boundaries
- test multi-turn workflow abuse
- gate promotion with evidence

Simple truth:
- **Adopt builds**
- **RedThread breaks and proves**

## Adopt RedThread role

This repo is the **bridge**.

It should:
- import Adopt discovery output
- map it into RedThread fixtures
- generate replay packs
- run targeted attack suites
- expose pre-publish security checks
- provide tailored demos and case studies

---

## Repo boundary rules

## Keep in `redthread/`

Keep generic security logic upstream:
- attack algorithms
- judge/eval logic
- replay framework
- runtime truth primitives
- generic action/tool security models
- generic agentic-security controls

## Keep in `adopt-redthread/`

Keep integration-specific logic here:
- ZAPI importers
- Adopt action adapters
- NoUI experiments
- Adopt-specific fixture schemas or transforms
- pre-publish workflow wrappers for Adopt-style flows
- demos and recruiter-friendly examples

## Upstream rule

If something is reusable beyond Adopt AI, move it back into RedThread later.

If it is specific to Adopt output formats or workflows, keep it here.

---

## Portfolio strategy

## Main pitch

For most recruiters, lead with **RedThread**.

Why:
- it is more original
- it shows deeper system design
- it keeps the strongest standalone identity

## Personalized pitch

For selected companies, show **Adopt RedThread** as the tailored extension.

Why:
- shows practical product thinking
- shows ecosystem integration skill
- makes outreach feel custom instead of generic
- makes RedThread feel more real and deployable

This pairing is strong:
- **RedThread = depth**
- **Adopt RedThread = relevance**

---

## MVP strategy

Best first milestone:

1. ingest ZAPI-discovered API metadata
2. classify endpoint risk
3. convert results into RedThread-friendly fixtures
4. generate first replay packs

Why this is best:
- small enough to ship fast
- clear demo value
- low blast radius
- directly supports later action-level and workflow-level testing

## What not to do first

Do not start with:
- full live mutation testing
- production POST replay
- deep NoUI runtime automation
- auto-remediation loops
- large forked copies of RedThread internals

Start with intake and replay planning first.

---

## Success criteria for the first phase

The first phase is successful if this repo can:
- take a ZAPI export or documented API set
- normalize it into a fixture format
- tag risky endpoints
- generate a replay plan
- explain the result in a recruiter-friendly demo

After that, move to action-level and pre-publish testing.
