"""Assemble recorded investigation context without interpreting scientific support."""

from .schema_v02 import ContractV02


def build_investigation(contract, path, *, evidence_id=None, claim_id=None, assessment_id=None):
    """Follow explicit local evidence and completion links for one selection.

    Assessment lookup runs backwards only from the selected Evidence or explicit
    completion Evidence. Shared upstream sources do not pull unrelated claims
    into the investigation. Completion links may form cycles; sets bound the walk.
    """
    from .explain import (apply_resolutions, assessment_detail, claim_detail,
                          command, evidence_detail)

    selectors = [("evidence", evidence_id), ("claim", claim_id), ("assessment", assessment_id)]
    selected = [(kind, key) for kind, key in selectors if key is not None]
    if len(selected) != 1:
        raise ValueError("An investigation requires exactly one Evidence, Claim or Assessment selector")
    kind, key = selected[0]
    records = {"evidence": contract.evidence, "claim": contract.claims,
               "assessment": getattr(contract, "assessments", [])}
    chosen = [r for r in records[kind] if r.id == key]
    if not chosen:
        raise ValueError("Requested ID not found in the selected contract")

    def target(record_kind, record):
        return record_kind, record.id, getattr(record, "revision", None)

    def selection(record):
        entry = {"kind": kind, "id": record.id, "record": record.model_dump(exclude_none=True)}
        if kind == "claim" and hasattr(record, "revision"):
            entry["revision"] = record.revision
        return entry

    evidence_ids = {key} if kind == "evidence" else set()
    anchors = set(evidence_ids)
    assessment_ids = {key} if kind == "assessment" else set()
    targets = {target(kind, r) for r in chosen}
    modern = isinstance(contract, ContractV02)
    assessments = contract.assessments if modern else []
    tasks = contract.follow_ups if modern else []
    resolutions = {r.follow_up: r for r in contract.follow_up_resolutions} if modern else {}
    if kind == "claim":
        if modern:
            assessment_ids.update(a.id for a in assessments if a.kind == "evidence_support"
                                  and ("claim", a.claim, a.claim_revision) in targets)
        else:
            evidence_ids.update(e for r in chosen for e in r.evidence)

    previous = None
    while previous != (evidence_ids, assessment_ids, targets, anchors):
        previous = tuple(set(values) for values in (evidence_ids, assessment_ids, targets, anchors))
        assessment_ids.update(a.id for a in assessments if anchors.intersection(a.evidence))
        for assessment in assessments:
            if assessment.id not in assessment_ids:
                continue
            targets.add(("assessment", assessment.id, None))
            if assessment.kind == "evidence_support":
                targets.add(("claim", assessment.claim, assessment.claim_revision))
            else:
                targets.add(("condition", assessment.condition, assessment.condition_revision))
            evidence_ids.update(assessment.evidence)
        for evidence in contract.evidence:
            if evidence.id not in evidence_ids:
                continue
            targets.add(("evidence", evidence.id, None))
            if evidence.provenance:
                evidence_ids.update(link.evidence for link in evidence.provenance.derived_from)
        for task in tasks:
            if (task.target_kind, task.target, task.revision) not in targets:
                continue
            resolution = resolutions.get(task.id)
            if resolution:
                evidence_ids.update(resolution.evidence)
                anchors.update(resolution.evidence)

    relevant_tasks = [task for task in tasks
                      if (task.target_kind, task.target, task.revision) in targets]
    completed = [{**resolutions[task.id].model_dump(), "instruction": task.model_dump(exclude_none=True)}
                 for task in relevant_tasks if task.id in resolutions]
    pending = [task.model_dump(exclude_none=True) for task in relevant_tasks if task.id not in resolutions]
    details = []
    for evidence in contract.evidence:
        if evidence.id in evidence_ids:
            item = evidence_detail(contract, path, evidence.id)
            apply_resolutions(contract, path, item)
            details.append(item)
    assessment_details = []
    for assessment in assessments:
        if assessment.id in assessment_ids:
            item = assessment_detail(contract, path, assessment)
            apply_resolutions(contract, path, item)
            assessment_details.append(item)

    subject_ids = {a.subject for a in assessments if a.id in assessment_ids}
    context_ids = {a.context for a in assessments if a.id in assessment_ids}
    if modern:
        subject_ids.update(e.subject for e in contract.evidence if e.id in evidence_ids and e.subject)
        context_ids.update(e.context for e in contract.evidence if e.id in evidence_ids and e.context)

    suggestions = []
    next_commands = [command(path, "--" + kind, key)]
    for record_kind, items in (("evidence", details), ("assessment", assessment_details)):
        for item in items:
            suggestions.extend({"target_kind": record_kind, "target": item["id"], **step}
                               for step in item["suggested_steps"])
            next_commands.append(command(path, "--" + record_kind, item["id"]))
            next_commands.extend(item["next_commands"])
    if kind == "claim":
        for claim in chosen:
            item = claim_detail(contract, path, claim)
            apply_resolutions(contract, path, item)
            identity = {"target_kind": "claim", "target": claim.id}
            if hasattr(claim, "revision"):
                identity["revision"] = claim.revision
            suggestions.extend({**identity, **step} for step in item["suggested_steps"])
            next_commands.extend(item["next_commands"])

    return {
        "selection": [selection(record) for record in chosen],
        "scope": ("Selected records, their upstream evidence and explicit task completions in this contract. "
                  "Assessments citing selected or completion evidence are included; shared upstream sources "
                  "alone do not include other assessments. External locators are not read, and no preferred "
                  "decision, current support or blocking status is inferred. Related records do not broaden "
                  "an explicitly selected Assessment's audit or hash-check scope."),
        "completed_follow_ups": completed,
        "pending_follow_ups": pending,
        "evidence": details,
        "assessments": assessment_details,
        "subjects": [s.model_dump(exclude_none=True) for s in getattr(contract, "subjects", [])
                     if s.id in subject_ids],
        "contexts": [c.model_dump(exclude_none=True) for c in getattr(contract, "contexts", [])
                     if c.id in context_ids],
        "suggested_steps": suggestions,
        "excluded_evidence": [e.id for e in contract.evidence if e.id not in evidence_ids],
        "next_commands": list(dict.fromkeys(next_commands)),
    }
