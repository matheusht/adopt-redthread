from __future__ import annotations

# ---------------------------------------------------------------------------
# Phase A2 — Alias Table Bootstrap
#
# A narrow, manually-curated table of source-key → target-path mappings
# seeded from patterns proven in practice (ATP Tennis Bot test et al.).
#
# Rules:
#   - Source keys are dot-paths as they appear in response_json (e.g. "chat.id")
#   - Target paths are dot-paths as they appear in request_body_json or URL slot names
#   - Tier is one of: "exact_name_match", "alias_match", "heuristic_match"
#   - This table is human-curated; programmatic extension is Phase E territory
# ---------------------------------------------------------------------------

from typing import NamedTuple


class AliasEntry(NamedTuple):
    source_key: str
    target_path: str
    tier: str


# Primary alias table: exact dot-path source → target-path mappings
_ALIAS_TABLE: list[AliasEntry] = [
    AliasEntry("resource.id", "resourceId", "alias_match"),
    AliasEntry("chat.id", "chatId", "alias_match"),
    AliasEntry("chat.id", "id", "alias_match"),
    AliasEntry("thread.id", "threadId", "alias_match"),
    AliasEntry("session.id", "sessionId", "alias_match"),
    AliasEntry("session.id", "query.sessionId", "alias_match"),
    AliasEntry("user.id", "userId", "alias_match"),
    AliasEntry("account.id", "accountId", "alias_match"),
    AliasEntry("item.id", "itemId", "alias_match"),
    AliasEntry("order.id", "orderId", "alias_match"),
    AliasEntry("post.id", "postId", "alias_match"),
    AliasEntry("message.id", "messageId", "alias_match"),
]

# Source key suffix patterns for heuristic matching.
# When a source key ends with one of these suffixes, we propose a target
# by removing the dot and camel-casing (e.g. "resource.id" → "resourceId").
_HEURISTIC_SUFFIX = ".id"


def alias_lookup(source_key: str) -> list[tuple[str, str]]:
    """Return a list of (target_path, tier) for a given source_key.

    Performs three passes in priority order:
    1. exact_name_match  — source_key leaf == target_path
    2. alias_match       — curated alias table entry
    3. heuristic_match   — source key ends with ".id", derive target by camel-case
    """
    results: list[tuple[str, str]] = []
    seen_targets: set[str] = set()

    # Pass 1 — exact leaf name match
    leaf = source_key.split(".")[-1]
    results.append((leaf, "exact_name_match"))
    seen_targets.add(leaf)

    # Pass 2 — alias table
    for entry in _ALIAS_TABLE:
        if entry.source_key == source_key and entry.target_path not in seen_targets:
            results.append((entry.target_path, entry.tier))
            seen_targets.add(entry.target_path)

    # Pass 3 — heuristic: "parent.id" → "parentId"
    if source_key.endswith(_HEURISTIC_SUFFIX):
        parts = source_key.split(".")
        if len(parts) >= 2:
            parent = parts[-2]
            heuristic_target = f"{parent}Id"
            if heuristic_target not in seen_targets:
                results.append((heuristic_target, "heuristic_match"))
                seen_targets.add(heuristic_target)

    return results


def all_entries() -> list[AliasEntry]:
    """Return the full alias table for inspection or testing."""
    return list(_ALIAS_TABLE)
