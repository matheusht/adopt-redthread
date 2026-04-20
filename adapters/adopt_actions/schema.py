from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class AdoptAction:
    name: str
    description: str = ""
    method: str = "POST"
    path: str = "/"
    approval_required: bool = False
    scopes: list[str] = field(default_factory=list)
    input_fields: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    workflow_group: str = "default"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
