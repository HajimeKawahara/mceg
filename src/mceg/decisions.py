"""Inspect recorded choices and their pinned basis without choosing a model."""

from .schema_v04 import decision_basis_digest, decision_basis_records


def select_decisions(contract, decision_id=None, revision=None):
    """Keep every matching revision; identifiers have no chronological ordering."""
    if revision is not None and decision_id is None:
        raise ValueError("--decision-revision requires --decision ID")
    return [d for d in getattr(contract, "decisions", [])
            if (decision_id is None or d.id == decision_id)
            and (revision is None or d.revision == revision)]


def decision_basis_checks(contract, decision):
    """Compare stored record fingerprints, preserving the historical choice."""
    pins = []
    for reference in decision.basis:
        actual = decision_basis_digest(contract, reference.kind, reference.id)
        pins.append({"kind": reference.kind, "id": reference.id,
                     "expected_sha256": reference.sha256, "actual_sha256": actual,
                     "status": "PASS" if actual == reference.sha256 else "FAIL"})
    changed = [p for p in pins if p["status"] == "FAIL"]
    status = "FAIL" if changed else "PASS" if pins else "UNKNOWN"
    return [{"name": "decision_basis", "status": status,
             "message": (f"Decision {decision.id}@{decision.revision}: "
                         f"{len(pins) - len(changed)}/{len(pins)} basis snapshots match"
                         if pins else f"Decision {decision.id}@{decision.revision}: no basis references recorded"),
             "details": ["Record fingerprints only; selection, implementation and scientific support are not inferred.",
                         *(f"{p['kind']} {p['id']}: recorded basis changed; review this choice without overwriting its history."
                           for p in changed)],
             "decision": {"id": decision.id, "revision": decision.revision}, "pins": pins}]


def decision_records(contract, decisions):
    """Return the exact recorded dependency closure of the selected choices."""
    records = {}
    for decision in decisions:
        for reference in decision.basis:
            for item in decision_basis_records(contract, reference.kind, reference.id):
                records[(item["kind"], item["id"], item.get("revision"))] = item
    return list(records.values())


def decision_detail(contract, path, decision):
    from .explain import command

    references = decision_records(contract, [decision])
    checks = decision_basis_checks(contract, decision)
    next_commands = [command(path, "--" + b.kind, b.id) for b in decision.basis]
    predecessors = [decision.supersedes] if decision.supersedes else []
    successors = [d for d in contract.decisions if d.supersedes is not None
                  and (d.supersedes.id, d.supersedes.revision) == (decision.id, decision.revision)]
    next_commands += [command(path, "--decision", d.id, "--decision-revision", d.revision)
                      for d in [*predecessors, *successors]]
    steps = []
    if checks[0]["status"] != "PASS":
        steps.append({"action": "Review the missing or changed basis for this recorded choice.",
                      "requires": [],
                      "completion": "Preserve the earlier Decision and evidence; record a new revision if the choice or its reviewed basis changes."})
    return {"id": decision.id, "record": decision.model_dump(exclude_none=True),
            "basis_assessments": [r["record"] for r in references if r["kind"] == "assessment"],
            "basis_checks": checks,
            "superseded_by": [{"id": d.id, "revision": d.revision} for d in successors],
            "recorded_follow_ups": [], "suggested_steps": steps,
            "next_commands": list(dict.fromkeys(next_commands))}
