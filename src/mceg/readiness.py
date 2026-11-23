"""Check explicit requirements for one intended use without running a provider."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Literal

from pydantic import Field, TypeAdapter, model_validator
import yaml

from .check import source_audit
from .decisions import decision_basis_checks
from .equation_checks import _binding_source, equation_checks
from .integrity import file_integrity, resolve_root
from .schema import Text
from .schema_v02 import Digest, Record
from .schema_v03 import Key, PythonSymbol
from .schema_v04 import Decision, decision_basis_digest
from .validator import load_contract


class UseTarget(Record):
    contract: Text
    subject: Text
    context: Text
    entry_point: Text

    @model_validator(mode="after")
    def local_entry_point(self):
        source, separator, symbol = self.entry_point.partition(":")
        if (not separator or not source.endswith(".py") or Path(source).is_absolute()
                or ".." in Path(source).parts):
            raise ValueError("entry_point must be a relative Python file and symbol: src/model.py:forward")
        # Use the same lexical-symbol syntax as EquationBinding.
        TypeAdapter(PythonSymbol).validate_python(symbol)
        return self


class ExplorationDecision(Record):
    id: Key
    revision: Key
    selected: Key
    sha256: Digest


class UseRequirement(Record):
    assessment: Text
    role: Literal["implementation", "physical_support"]
    sha256: Digest
    exploration_decision: ExplorationDecision | None = None


class UseManifest(Record):
    """An external selection policy, not a new scientific support record."""

    schema_version: Literal["0.1"]
    id: Key
    purpose: Text
    mode: Literal["scientific", "exploration"]
    target: UseTarget
    requirements: list[UseRequirement] = Field(min_length=1)

    @model_validator(mode="after")
    def explicit_selection(self):
        identifiers = [r.assessment for r in self.requirements]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("Requirement Assessment IDs must be unique")
        if any(r.exploration_decision is not None
               and (self.mode != "exploration" or r.role != "physical_support")
               for r in self.requirements):
            raise ValueError("Exploration Decisions apply only to physical_support requirements in exploration mode")
        return self


def decision_digest(decision: Decision) -> str:
    """Pin the full declared choice; its basis has separate dependency pins."""
    data = json.dumps(decision.model_dump(mode="json"), sort_keys=True,
                      separators=(",", ":"), ensure_ascii=True, allow_nan=False)
    return sha256(data.encode("utf-8")).hexdigest()


def _check(name, status, message):
    return {"name": name, "status": status, "message": message}


def _decision_check(contract, requirement, target):
    pin = requirement.exploration_decision
    decision = next((d for d in getattr(contract, "decisions", [])
                     if (d.id, d.revision) == (pin.id, pin.revision)), None)
    if decision is None:
        return _check("exploration_decision", "FAIL", "Selected Decision revision is missing")
    active = not any(d.supersedes and (d.supersedes.id, d.supersedes.revision)
                     == (decision.id, decision.revision)
                     for d in contract.decisions)
    valid = (active and decision.selected == pin.selected
             and decision.subject == target.subject and decision.context == target.context
             and decision.limitations and decision.reconsider_when
             and decision_digest(decision) == pin.sha256
             and any(b.kind == "assessment" and b.id == requirement.assessment
                     for b in decision.basis)
             and all(c["status"] == "PASS" for c in decision_basis_checks(contract, decision)))
    return {**_check("exploration_decision", "PASS" if valid else "FAIL",
                     "Scoped exploratory choice matches its pins" if valid else
                     "Decision is stale, superseded, unscoped, or does not select the requested option"),
            "id": decision.id, "revision": decision.revision, "selected": decision.selected,
            "limitations": decision.limitations, "reconsider_when": decision.reconsider_when}


def check_readiness(path, *, root=None):
    """Require every explicit requirement; UNKNOWN is not readiness.

    Hashes pin declarations and local bytes. Neither the requirement list nor
    a static entry-point declaration proves a complete physical model.
    """
    path = Path(path).resolve()
    manifest = UseManifest.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
    target = manifest.target
    root = resolve_root(root, target.subject)
    contract_path = (path.parent / target.contract).resolve()
    contract = load_contract(contract_path)
    report = {"use": manifest.id, "purpose": manifest.purpose, "mode": manifest.mode,
              "manifest": str(path), "target": target.model_dump(), "root": str(root) if root else None,
              "ready": False, "requirements": [], "checks": [],
              "limits": ["Readiness covers the authored requirements only; their completeness requires review.",
                         "Entry-point declarations do not prove a call graph or runtime model coupling.",
                         "No scientific solver or provider code is imported or executed."]}
    subjects = {s.id: s for s in getattr(contract, "subjects", [])}
    contexts = {c.id: c for c in getattr(contract, "contexts", [])}
    subject = subjects.get(target.subject)
    declared = (subject is not None and target.context in contexts
                and target.entry_point in subject.implementation.entry_points)
    report["checks"].append(_check("target", "PASS" if declared else "FAIL",
                                   "Subject, Context and entry point match the declaration" if declared else
                                   "Requested Subject, Context or declared entry point is missing"))
    source, _, symbol = target.entry_point.partition(":")
    pinned = subject is not None and subject.selected_files.get(source) is not None
    report["checks"].append(_check("entry_point_pin", "PASS" if pinned else "FAIL",
                                   "Entry-point source has a selected-file pin" if pinned else
                                   "Entry-point source needs a selected-file SHA-256"))
    status, message = _binding_source(SimpleNamespace(
        id="use_entry_point", source=source, symbol=symbol, arguments={}), root,
        allow_decorators=True)
    report["checks"].append(_check("entry_point_source", status, message))
    assessments = {a.id: a for a in getattr(contract, "assessments", [])}
    for requirement in manifest.requirements:
        row = {"assessment": requirement.assessment, "role": requirement.role,
               "recorded_support": None, "ready": False, "accepted_by": None, "checks": []}
        report["requirements"].append(row)
        assessment = assessments.get(requirement.assessment)
        if assessment is None or assessment.kind != "evidence_support":
            row["checks"].append(_check("assessment", "FAIL", "Required support Assessment is missing"))
            continue
        row["recorded_support"] = assessment.status
        row["checks"].append(_check(
            "scope", "PASS" if (assessment.subject, assessment.context)
            == (target.subject, target.context) else "FAIL",
            f"Assessment subject={assessment.subject}; context={assessment.context}"))
        matches = decision_basis_digest(contract, "assessment", assessment.id) == requirement.sha256
        row["checks"].append(_check("assessment_pin", "PASS" if matches else "FAIL",
                                     "Assessment dependency snapshot matches" if matches else
                                     "Assessment or a declared dependency changed; review the requirement"))
        audit, traces = source_audit(contract, assessment.evidence)
        row["checks"].append(audit)
        row["checks"].extend(equation_checks(contract, assessment, root))
        if root is None:
            row["checks"].append(_check("file_integrity", "UNKNOWN", "Supply --root to check current source and artifacts"))
        else:
            integrity = file_integrity(contract, assessment, [t["evidence"] for t in traces], root)
            row["integrity"] = integrity
            files = integrity["selected_files"]
            outcomes = files + integrity["artifact_hashes"]
            state = ("FAIL" if any(f["status"] == "FAIL" for f in outcomes) else
                     "UNKNOWN" if not files or any(f["status"] == "UNKNOWN" for f in outcomes) else "PASS")
            row["checks"].append({**_check("file_integrity", state,
                                          "Selected source and all declared artifacts checked; undeclared files are outside scope"),
                                  "details": [f"{f['source']}: {f['message']}" for f in outcomes
                                              if f["status"] != "PASS"]})
        support = _check("recorded_support", {"supported": "PASS", "unknown": "UNKNOWN",
                                               "contradicted": "FAIL"}[assessment.status],
                         f"Stored support remains {assessment.status}")
        row["checks"].append(support)
        accepted = assessment.status == "supported"
        if requirement.exploration_decision is not None:
            decision = _decision_check(contract, requirement, target)
            row["checks"].append(decision)
            accepted = decision["status"] == "PASS"
            row["accepted_by"] = "exploration_decision" if accepted else None
        elif accepted:
            row["accepted_by"] = "supported_assessment"
        row["ready"] = bool(accepted and all(c["status"] == "PASS" for c in row["checks"]
                                             if c["name"] != "recorded_support"))
    report["ready"] = (all(c["status"] == "PASS" for c in report["checks"])
                       and all(r["ready"] for r in report["requirements"]))
    report["outcome"] = ("exploration_permitted" if manifest.mode == "exploration" else
                         "requirements_met") if report["ready"] else "not_ready"
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(prog="mceg readiness",
                                     description="Check pinned requirements for one declared use; UNKNOWN is not ready.")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--root", type=Path, help="Provider root for source and artifact integrity; required for readiness")
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--json", action="store_true")
    output.add_argument("--plain", action="store_true", help="Plain output (the default)")
    args = parser.parse_args(argv)
    try:
        report = check_readiness(args.manifest, root=args.root)
    except (OSError, ValueError, RuntimeError, yaml.YAMLError) as exc:
        parser.error(str(exc))
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"{report['outcome'].upper()} {report['use']}: {report['purpose']}")
        print(f"Mode: {report['mode']}; subject={report['target']['subject']}; context={report['target']['context']}")
        for check in report["checks"]:
            print(f"  {check['status']} {check['name']}: {check['message']}")
        for row in report["requirements"]:
            print(f"  {'READY' if row['ready'] else 'NOT READY'} {row['assessment']} ({row['role']}); "
                  f"stored support={row['recorded_support']}; accepted by={row['accepted_by']}")
            for check in row["checks"]:
                if check["status"] != "PASS" or check["name"] == "exploration_decision":
                    print(f"    {check['status']} {check['name']}: {check['message']}")
                    for detail in check.get("details", []):
                        print(f"      {detail}")
                    for limitation in check.get("limitations", []):
                        print(f"      Limitation: {limitation}")
        for limit in report["limits"]:
            print(f"  Scope: {limit}")
    return int(not report["ready"])
