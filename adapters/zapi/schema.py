from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class ZapiEndpoint:
    method: str
    path: str
    summary: str = ""
    description: str = ""
    query_params: list[str] = field(default_factory=list)
    body_fields: list[str] = field(default_factory=list)
    auth_hints: list[str] = field(default_factory=list)
    source: str = "zapi"
    workflow_group: str = "default"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class RedThreadFixture:
    name: str
    method: str
    path: str
    summary: str
    query_params: list[str] = field(default_factory=list)
    body_fields: list[str] = field(default_factory=list)
    auth_hints: list[str] = field(default_factory=list)
    workflow_group: str = "default"
    risk_level: str = "unknown"
    replay_class: str = "manual_review"
    reasons: list[str] = field(default_factory=list)
    source: str = "zapi"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
