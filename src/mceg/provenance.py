"""Trace declared source ancestry; never certify source content or applicability."""

from .schema import Contract


def trace_provenance(contract: Contract, evidence_id: str) -> dict:
    """Report every recorded branch and audit gap, using local evidence IDs."""
    evidence = {item.id: item for item in contract.evidence}
    if evidence_id not in evidence:
        raise ValueError(f"Unknown evidence ID: {evidence_id!r}")
    nodes, links, issues, primary_sources = [], [], [], []
    pending, visited = [evidence_id], set()
    while pending:
        key = pending.pop()
        if key in visited:
            continue
        visited.add(key)
        item = evidence[key]
        nodes.append(item.model_dump(exclude_none=True))
        provenance = item.provenance
        if provenance is None:
            issues.append({"evidence": key, "issue": "missing_provenance"})
            continue
        if provenance.role == "primary":
            primary_sources.append(key)
        elif provenance.role == "unknown":
            issues.append({"evidence": key, "issue": "unknown_source_role"})
        if provenance.inspection != "inspected":
            issues.append({"evidence": key, "issue": "source_not_fully_inspected"})
        if not provenance.derived_from and provenance.role != "primary":
            issues.append({"evidence": key, "issue": "primary_source_not_identified"})
        for link in provenance.derived_from:
            links.append({"from": key, "to": link.evidence,
                          "comparison": link.comparison, "note": link.note})
            if link.comparison != "consistent":
                issues.append({"evidence": key, "upstream": link.evidence,
                               "issue": f"comparison_{link.comparison}"})
        pending.extend(link.evidence for link in reversed(provenance.derived_from))
    return {
        "evidence": evidence_id,
        "recorded_audit_complete": not issues,
        "meaning": "Declared source tracing only; not a scientific validity judgment.",
        "primary_sources": primary_sources,
        "nodes": nodes, "links": links, "issues": issues,
    }
