"""将 ``ConstraintObject`` 降为 ``RuntimeConstraintEngine`` 识别的 dict（无 RDF）。"""

from __future__ import annotations

import uuid

from ..models.constraint_object import ConstraintKind, ConstraintObject


def constraint_object_to_engine(co: ConstraintObject) -> dict:
    predicates = dict(co.predicates.model_dump(exclude_none=True))
    applies = co.applies_to.model_dump(exclude_none=True)

    if co.kind == ConstraintKind.THICKNESS_LIMIT:
        v = co.predicates.thickness_mm_min or co.predicates.value
        return {
            "constraint_id": co.constraint_id,
            "kind": "numeric_threshold",
            "predicates": {
                **predicates,
                "prop_key": co.predicates.prop_key or "thickness_mm",
                "op": co.predicates.op or "gte",
                "value": float(v or 0.0),
            },
            "applies_to": applies,
        }

    if co.kind == ConstraintKind.TEMPERATURE_LIMIT:
        vmax = co.predicates.temperature_c_max or co.predicates.value
        return {
            "constraint_id": co.constraint_id,
            "kind": "numeric_threshold",
            "predicates": {
                **predicates,
                "prop_key": co.predicates.prop_key or "temperature_c",
                "op": co.predicates.op or "lte",
                "value": float(vmax or 0.0),
            },
            "applies_to": applies,
        }

    if co.kind == ConstraintKind.FORBID_PAIR:
        return {"constraint_id": co.constraint_id, "kind": "forbid_pair", "predicates": predicates, "applies_to": applies}

    if co.kind == ConstraintKind.DEPENDS_ON:
        before = predicates.get("requires_ordering_before")
        return {
            "constraint_id": co.constraint_id,
            "kind": "depends_on",
            "predicates": {**predicates, "before": before},
            "applies_to": applies,
        }

    if co.kind in (ConstraintKind.BEFORE, ConstraintKind.AFTER):
        return {
            "constraint_id": co.constraint_id,
            "kind": "requires_before",
            "predicates": predicates,
            "applies_to": applies,
        }

    if co.kind == ConstraintKind.MUST_NOT:
        return {
            "constraint_id": co.constraint_id,
            "kind": "must_not_rule",
            "predicates": {**predicates, "text": co.predicates.text or co.nl_source},
            "applies_to": applies,
        }

    if co.kind == ConstraintKind.MUST:
        return {
            "constraint_id": co.constraint_id,
            "kind": "must_rule",
            "predicates": {**predicates, "text": co.predicates.text or co.nl_source},
            "applies_to": applies,
        }

    return {"constraint_id": co.constraint_id, "kind": co.kind.value, "predicates": predicates, "applies_to": applies}


def coerce_constraint_records(raws: list) -> list[dict]:
    """支持 ``ConstraintObject`` / dict。"""
    out: list[dict] = []
    for r in raws:
        if isinstance(r, ConstraintObject):
            out.append(constraint_object_to_engine(r))
        elif isinstance(r, dict):
            rcopy = dict(r)
            if "constraint_id" not in rcopy and "id" in rcopy:
                rcopy["constraint_id"] = str(rcopy.pop("id"))
            if not rcopy.get("constraint_id"):
                rcopy["constraint_id"] = uuid.uuid4().hex
            try:
                co = ConstraintObject.model_validate(rcopy)
                out.append(constraint_object_to_engine(co))
            except Exception:
                out.append(rcopy)
    return out
