"""Verification: did reality actually change the way the action expected?

An action records an `expected_effect` (entity -> attribute -> expected value)
at execution time. Verification compares that against the world's current
BELIEVED state (which only observations update) and reports:

  verified            every expected attribute matches observed state
  partially_verified  some match, some do not
  failed              none match (or an expected entity/attribute is unknown)
  unknown             no observation evidence exists for the expected effects

This is the layer that catches "the executor reported success but the
package is still in Zone A".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from reality.core.models import Action

VERIFIED = "verified"
PARTIALLY_VERIFIED = "partially_verified"
FAILED = "failed"
UNKNOWN = "unknown"


@dataclass
class VerificationResult:
    action_id: str
    status: str
    checked: list[dict[str, Any]] = field(default_factory=list)
    discrepancies: list[str] = field(default_factory=list)
    verified_at: float = 0.0
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id,
            "status": self.status,
            "checked": self.checked,
            "discrepancies": self.discrepancies,
            "verified_at": self.verified_at,
            "notes": self.notes,
            # Observation ids the verification actually rested on.
            "evidence_ids": [c["evidence"] for c in self.checked if c.get("evidence")],
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> VerificationResult:
        return VerificationResult(
            action_id=str(data["action_id"]),
            status=str(data["status"]),
            checked=list(data.get("checked", [])),
            discrepancies=list(data.get("discrepancies", [])),
            verified_at=float(data.get("verified_at", 0.0)),
            notes=str(data.get("notes", "")),
        )


def _values_equal(expected: Any, actual: Any) -> bool:
    if isinstance(expected, float) or isinstance(actual, float):
        try:
            return abs(float(expected) - float(actual)) < 1e-6
        except (TypeError, ValueError):
            return False
    if isinstance(expected, list) and isinstance(actual, list):
        return len(expected) == len(actual) and all(
            _values_equal(e, a) for e, a in zip(expected, actual)
        )
    return expected == actual


def verify_action(action: Action, world, ts: float) -> VerificationResult:
    """Compare the action's expected effect with believed world state."""
    result = VerificationResult(action_id=action.id, status=UNKNOWN, verified_at=ts)

    if not action.expected_effect:
        result.status = VERIFIED
        result.notes = "action declares no observable effect; nothing to check"
        return result

    matched = 0
    total = 0
    for entity_id, attrs in action.expected_effect.items():
        entity = world.spatial.entities.get(entity_id)
        if entity is None:
            result.discrepancies.append(
                f"expected entity {entity_id!r} does not exist in the world"
            )
            continue
        for attr, expected in attrs.items():
            total += 1
            prov = world.get_provenance(entity_id, attr)
            actual = world.get_attribute(entity_id, attr)
            check = {
                "entity_id": entity_id,
                "attribute": attr,
                "expected": expected,
                "actual": actual,
                "match": False,
                "evidence": prov.observation_id if prov else None,
            }
            if prov is None:
                check["note"] = "no observation evidence for this attribute"
                result.checked.append(check)
                continue
            if _values_equal(expected, actual):
                check["match"] = True
                matched += 1
            else:
                result.discrepancies.append(
                    f"{entity_id}.{attr}: expected {expected!r}, "
                    f"observed {actual!r} "
                    f"(via {prov.source} @ {prov.observation_id})"
                )
            result.checked.append(check)

    if total == 0:
        result.status = FAILED
        result.notes = "expected effect referenced no checkable attributes"
    elif matched == total:
        result.status = VERIFIED
    elif matched == 0:
        # Distinguish "evidence exists and contradicts" from "no evidence".
        evidenced = any(c.get("evidence") for c in result.checked)
        result.status = FAILED if evidenced else UNKNOWN
        if result.status == UNKNOWN:
            result.notes = (
                "no observation evidence yet for the expected effects; "
                "the action may not have been observed"
            )
    else:
        result.status = PARTIALLY_VERIFIED
    return result
