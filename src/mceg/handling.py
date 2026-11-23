"""Report recorded handling of scoped unresolved judgments, without resolving them."""

from .decisions import decision_basis_checks, select_decisions


def assessment_handling(contract, assessments):
    """Require exact Assessment targets; shared Claims or sources do not imply handling.

    A Decision is a recorded disposition only when it pins the judgment, matches
    its Subject/Context, and records limitations and reconsideration conditions.
    This checks those records, not whether their scientific reasoning is sound.
    """
    resolutions = {r.follow_up for r in getattr(contract, "follow_up_resolutions", [])}
    tasks = getattr(contract, "follow_ups", [])
    decisions = select_decisions(contract)
    superseded = {(d.supersedes.id, d.supersedes.revision) for d in decisions if d.supersedes}
    rows = []
    for assessment in assessments:
        if assessment.kind != "evidence_support" or assessment.status == "supported":
            continue
        pending = [f.id for f in tasks if f.target_kind == "assessment"
                   and f.target == assessment.id and f.id not in resolutions]
        dispositions = []
        for decision in decisions:
            if ((decision.id, decision.revision) in superseded
                    or decision.subject != assessment.subject
                    or decision.context != assessment.context
                    or not decision.limitations or not decision.reconsider_when
                    or not any(b.kind == "assessment" and b.id == assessment.id for b in decision.basis)):
                continue
            if all(c["status"] == "PASS" for c in decision_basis_checks(contract, decision)):
                dispositions.append({"id": decision.id, "revision": decision.revision})
        rows.append({"assessment": assessment.id, "claim": assessment.claim,
                     "claim_revision": assessment.claim_revision,
                     "subject": assessment.subject, "context": assessment.context,
                     "recorded_support": assessment.status, "open_follow_ups": pending,
                     "decisions": dispositions, "handling_recorded": bool(pending or dispositions)})
    return rows


def handling_check(rows, *, required=False):
    """A passing coverage check means a response is recorded, not that it succeeds."""
    missing = [r["assessment"] for r in rows if not r["handling_recorded"]]
    return {
        "name": "handling_coverage",
        "status": ("FAIL" if required else "UNKNOWN") if missing else "PASS",
        "message": ("No recorded handling for: " + ", ".join(missing) if missing else
                    f"{len(rows)}/{len(rows)} unresolved assessments have recorded handling" if rows else
                    "No unresolved support assessments in this selection"),
        "details": [
            "Handling records do not establish scientific support or resolve an Assessment.",
            "Use an open Assessment-targeted FollowUp, or a matching, pinned Decision with limitations and reconsideration conditions.",
            *(f"{r['assessment']}: {r['recorded_support']}; subject={r['subject']}; context={r['context']}; "
              f"follow_ups={','.join(r['open_follow_ups']) or 'none'}; "
              f"decisions={','.join(d['id'] + '@' + d['revision'] for d in r['decisions']) or 'none'}"
              for r in rows),
        ],
    }
