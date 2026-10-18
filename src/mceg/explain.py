"""Inspect review gaps and next steps without fetching sources or changing evidence."""

import argparse
import json
from pathlib import Path
import shlex
import shutil
import textwrap

import yaml

from .check import (add_context_arguments, check_contract, context_options, discover,
                    requested_context)
from .provenance import trace_provenance
from .schema_v02 import ContractV02
from .validator import load_contract


def action(text, completion, requires=()):
    return {"action": text, "requires": list(requires), "completion": completion}


SOURCE_ACTIONS = {
    "missing_provenance": action(
        "Review the listed source for this precise scope and record its role, location and inspection state.",
        "Add the inspected passage or code location and any upstream evidence/comparison; a source locator alone is insufficient."),
    "source_not_fully_inspected": action(
        "Obtain and inspect the relevant full text or data. If access is restricted, a human may need an institutional library or an authorized author copy.",
        "Record the exact equation/table/page, relevant values, units and material scope; mark only the content actually inspected.",
        ["The listed source content, not only its abstract or citation."]),
    "unknown_source_role": action(
        "Determine whether this is an original source or a later account, and identify the original work.",
        "Record the verified source role and link the inspected original evidence."),
    "primary_source_not_identified": action(
        "Trace the scoped statement to its original theoretical, experimental or observational source.",
        "Add a primary evidence record and the inspected derivation/comparison links."),
    "comparison_not_checked": action(
        "Compare the scoped statement with the upstream passage, including values, units, conventions and experimental subset.",
        "Record the compared locations and a consistent/discrepancy result only after both scoped sources are inspected."),
    "comparison_discrepancy": action(
        "Investigate the recorded discrepancy; compare material scope, units and transcription before revising a claim.",
        "Document the resolution or preserve the discrepancy with its unresolved scope."),
}

VALIDATION_ACTION = action(
    "Define the physical observable, accuracy criterion and calculation conditions, then obtain relevant independent measurements or observations.",
    "Record the comparison as new physical Evidence and a scoped Assessment; numerical solver agreement alone does not establish physical accuracy.")


def command(path, *options):
    return shlex.join(["mceg", "explain", str(path), *map(str, options)])


def recorded_follow_ups(contract, kind, target, revision=None):
    if not isinstance(contract, ContractV02):
        return []
    return [f.model_dump(exclude_none=True) for f in contract.follow_ups
            if (f.target_kind, f.target, f.revision) == (kind, target, revision)]


def linked_contracts(path, sources):
    """Offer local navigation only; locators do not propagate scientific support."""
    roots = [p for p in path.parents if (p / "mceg/contracts").is_dir()]
    roots += [path.parent, *[p for p in path.parents if (p / "contracts").is_dir()]]
    found = set()
    for source in sources:
        if "://" in source:
            continue
        name = Path(source.split("#", 1)[0])
        if name.suffix not in {".yaml", ".yml"}:
            continue
        match = next(((root / name).resolve() for root in roots if (root / name).is_file()), None)
        if match is not None and match != path:
            found.add(command(match))
    return sorted(found)


def evidence_detail(contract, path, evidence_id):
    evidence = next(e for e in contract.evidence if e.id == evidence_id)
    trace = trace_provenance(contract, evidence_id)
    local = [i for i in trace["issues"] if i["evidence"] == evidence_id]
    issues = list(dict.fromkeys(i["issue"] for i in local))
    upstream = list(dict.fromkeys(i["evidence"] for i in trace["issues"] if i["evidence"] != evidence_id))
    links = evidence.provenance.derived_from if evidence.provenance else []
    return {"id": evidence.id, "record": evidence.model_dump(exclude_none=True), "issues": issues,
            "recorded_follow_ups": recorded_follow_ups(contract, "evidence", evidence_id),
            "suggested_steps": [SOURCE_ACTIONS[key] for key in issues],
            "comparisons": [link.model_dump() for link in links],
            "upstream_gaps": upstream,
            "next_commands": list(dict.fromkeys([command(path, "--evidence", key) for key in upstream] +
                                                  linked_contracts(path, evidence.sources)))}


def claim_detail(contract, path, claim):
    if isinstance(contract, ContractV02):
        assessments = [a for a in contract.assessments if a.kind == "evidence_support"
                       and (a.claim, a.claim_revision) == (claim.id, claim.revision)]
        evidence = sorted({key for a in assessments for key in a.evidence})
        next_commands = [command(path, "--assessment", a.id) for a in assessments]
        follow_ups = recorded_follow_ups(contract, "claim", claim.id, claim.revision)
    else:
        assessments, evidence = [], claim.evidence
        next_commands, follow_ups = [], []
    return {"id": claim.id, "record": claim.model_dump(),
            "assessments": [a.model_dump() for a in assessments],
            "recorded_follow_ups": follow_ups,
            "suggested_steps": [VALIDATION_ACTION] if claim.kind == "physical_validation" else [action(
                "Review the claim's scope and evidence for the intended implementation and conditions.",
                "Record a separate scoped support Assessment; preserve the earlier declaration and execution results.")],
            "next_commands": next_commands + [command(path, "--evidence", key) for key in evidence]}


def assessment_detail(contract, path, assessment):
    context = next(c for c in contract.contexts if c.id == assessment.context)
    subject = next(s for s in contract.subjects if s.id == assessment.subject)
    steps = []
    if assessment.kind == "evidence_support":
        claim = next(c for c in contract.claims if (c.id, c.revision) == (assessment.claim, assessment.claim_revision))
        if assessment.origin == "imported_v0.1_declaration":
            steps.append(action("Review the imported declaration before using it for a new context.",
                                "Keep the imported Assessment attached to its original Claim revision; add a separate reviewed Assessment for the new target."))
        if assessment.status == "unknown":
            steps += claim_detail(contract, path, claim)["suggested_steps"]
            missing = [r.removeprefix("Missing context: ") for r in assessment.reasons if r.startswith("Missing context: ")]
            if missing:
                steps.append(action("Supply the actual context fields: " + ", ".join(missing),
                                    "Create a new context and run mceg assess with a new output file; preserve this assessment."))
            if {"unreviewed_context", "no_recorded_sample"} & set(assessment.reasons):
                steps.append(action("Run the provider verification for the requested conditions and environment, retaining a new execution receipt and outputs.",
                                    "Review the new run's coverage and Claim criteria before adding its support Assessment."))
            if "selected_files_changed_or_missing" in assessment.reasons:
                steps += check_steps("selected_files", {})
        target = {"claim": claim.model_dump()}
        follow_ups = recorded_follow_ups(contract, "claim", claim.id, claim.revision)
    else:
        condition = next(c for c in contract.conditions
                         if (c.id, c.revision) == (assessment.condition, assessment.condition_revision))
        target = {"condition": condition.model_dump()}
        follow_ups = recorded_follow_ups(contract, "condition", condition.id, condition.revision)
        if assessment.classification == "unknown":
            steps.append(action("Supply the missing quantities or settings identified in the reasons, using a new Context ID.",
                                "Run mceg assess with the new context and a new output file; retain the old assessment."))
        elif assessment.classification == "not_sampled":
            steps.append(action("Obtain numerical evidence at the requested joint conditions, or review an explicit interpolation method.",
                                "Record actual new samples and their evidence; range inclusion alone is insufficient."))
        elif assessment.classification == "outside_reported_range":
            steps.append(action("Review whether the intended calculation requires evidence beyond this source's reported interval.",
                                "Use an evidenced condition or obtain new scoped evidence; do not widen an interval merely to clear this result."))
    return {"id": assessment.id, "record": assessment.model_dump(), "subject": subject.model_dump(),
            "context": context.model_dump(), **target,
            "recorded_follow_ups": recorded_follow_ups(contract, "assessment", assessment.id) + follow_ups,
            "suggested_steps": steps,
            "next_commands": [command(path, "--evidence", key) for key in assessment.evidence]}


def check_steps(name, entry):
    if name == "structure":
        return [action("Correct the field or local reference identified in the validation error.",
                       "Run mceg check again; valid structure permits inspection but does not establish scientific support.")]
    if name == "physical_validation":
        return [VALIDATION_ACTION]
    if name == "source_audit":
        return [action("Select an evidence ID below to see the source, recorded access/inspection notes and upstream comparisons.",
                       "Complete the scoped inspection and comparisons; obtaining a document alone does not complete the audit.")]
    if name == "selected_files":
        return [action("Inspect the changed or missing paths listed below.",
                       "Restore the archived files for a replay, or produce and review new evidence for the changed implementation; do not replace hashes to manufacture a pass.")]
    if name in {"temperature_range", "sample_coverage"}:
        return [action("Review the requested temperature, pressure and network against the archived scope.",
                       "For a new condition, obtain actual new numerical evidence and a scoped review; no interpolation support is inferred.")]
    if name == "evidence_reuse":
        assessment = entry.get("assessment")
        if assessment:
            support = assessment["assessments"][2]
            steps = []
            if support["missing_context"]:
                steps.append(action("Supply context fields: " + ", ".join(support["missing_context"]),
                                    "Use --context with the actual intended quantities, composition, environment and tolerance."))
            if support["different_context"] or "no_recorded_sample" in support["reasons"]:
                steps.append(action("Run the provider verification for the requested conditions and environment, retaining a new execution receipt and outputs.",
                                    "Review the new run's coverage and Claim criteria before adding its support Assessment.",
                                    ["A provider environment and the relevant numerical comparator; mceg explain does not execute them."]))
            if "selected_files_changed_or_missing" in support["reasons"]:
                steps += check_steps("selected_files", entry)
            if steps:
                return steps
        return [action("Inspect the recorded Claim/Assessment scope and any changed contract or receipt.",
                       "Define or review a scoped reuse policy with evidence for the intended target; imported support is not a new evaluation.")]
    return [action("Inspect the recorded assessment and its context using --assessment ID.",
                   "Address the stated reason and append a separately identified assessment; preserve the old record.")]


def explain_contract(path, context, evidence_id=None, claim_id=None, assessment_id=None):
    try:
        contract = load_contract(path)
    except (OSError, ValueError, yaml.YAMLError):
        if evidence_id or claim_id or assessment_id:
            raise
        entry = check_contract(path, context)
        return {"path": str(path), "model": None, "schema_version": None, "view": "overview",
                "items": [{**check, "suggested_steps": check_steps("structure", entry)} for check in entry["checks"]]}
    report = {"path": str(path), "model": contract.model.id, "schema_version": contract.schema_version}
    if evidence_id:
        report.update(view="evidence", items=[evidence_detail(contract, path, evidence_id)]
                      if any(e.id == evidence_id for e in contract.evidence) else [])
    elif claim_id:
        report.update(view="claim", items=[claim_detail(contract, path, c) for c in contract.claims if c.id == claim_id])
    elif assessment_id:
        report.update(view="assessment", items=[assessment_detail(contract, path, a) for a in
                      getattr(contract, "assessments", []) if a.id == assessment_id])
    else:
        entry = check_contract(path, context)
        gaps = {}
        for evidence in contract.evidence:
            for issue in trace_provenance(contract, evidence.id)["issues"]:
                gaps.setdefault(issue["evidence"], set()).add(issue["issue"])
        report.update(view="overview", items=[{**check, "suggested_steps": check_steps(check["name"], entry)}
                      for check in entry["checks"] if check["status"] != "PASS"],
                      evidence_gaps={key: sorted(value) for key, value in gaps.items()},
                      unknown_claims=[c.id for c in contract.claims if getattr(c, "status", None) == "unknown"],
                      assessments=[{"id": a.id, "context": a.context,
                                    "result": getattr(a, "status", getattr(a, "classification", None))}
                                   for a in getattr(contract, "assessments", [])])
    return report


def display(report):
    width = max(60, shutil.get_terminal_size().columns)

    def write(text, indent="    "):
        print(textwrap.fill(indent + text, width=width, subsequent_indent=indent))

    def record(value):
        value = dict(value)
        if "samples" in value and len(value["samples"]) > 2:
            samples = value.pop("samples")
            value.update(sample_count=len(samples), sample_preview=samples[:2],
                         remaining_samples="Use --json to inspect all joint samples.")
        print(textwrap.indent(yaml.safe_dump(value, sort_keys=False, allow_unicode=True).rstrip(), "    "))

    print("MCEG next steps: recorded gaps and suggested work; no evidence is changed.")
    if any(c["view"] == "overview" and c["model"] == "exogibbs.curated_gas.v1" and c["schema_version"] == "0.1"
           for c in report["contracts"]):
        print("Requested curated context (not an inspection of the installed environment):")
        print(yaml.safe_dump(report["context"], sort_keys=False).rstrip())
    for contract in report["contracts"]:
        path = Path(contract["path"])
        print(f"\n{path} [{contract['model']}; v{contract['schema_version']}]")
        for item in contract["items"]:
            print(f"\n  {item.get('id', item.get('name'))}")
            if "record" in item:
                record(item["record"])
                for key in ("subject", "context", "claim", "condition"):
                    if key in item:
                        print(f"  {key}:")
                        record(item[key])
            else:
                write(f"{item['status']}: {item['message']}")
                for detail in item["details"]:
                    print(f"    {detail}")
            for field, label in (("recorded_follow_ups", "Recorded next step"), ("suggested_steps", "Suggested next step")):
                for step in item.get(field, []):
                    write(f"{label}: {step['action']}")
                    for requirement in step.get("requires", []):
                        write(f"Needed: {requirement}", "      ")
                    for source in step.get("sources", []):
                        print(f"      Source: {source}")
                    write(f"Completion: {step['completion']}", "      ")
            for next_command in item.get("next_commands", []):
                print(f"    Inspect: {next_command}")
        if contract.get("evidence_gaps"):
            print("\n  Evidence gaps (IDs for --evidence):")
            for key, issues in contract["evidence_gaps"].items():
                print(f"    {key}: {', '.join(issues)}")
            first = next(iter(contract["evidence_gaps"]))
            print("  Inspect: " + command(path, "--evidence", first))
        if contract.get("unknown_claims"):
            print("  Unknown Claim IDs: " + ", ".join(contract["unknown_claims"]))
            print("  Inspect: " + command(path, "--claim", contract["unknown_claims"][0]))
        for assessment in contract.get("assessments", []):
            print(f"  Assessment {assessment['id']}: {assessment['result']}; context={assessment['context']}")
            print("  Inspect: " + command(path, "--assessment", assessment["id"]))


def main(argv=None):
    parser = argparse.ArgumentParser(prog="mceg explain", description=__doc__)
    parser.add_argument("paths", type=Path, nargs="*", help="Contract files/directories; default: current directory")
    parser.add_argument("-k", default="", metavar="NAME", help="Filter contract paths, as in mceg check")
    select = parser.add_mutually_exclusive_group()
    select.add_argument("--evidence", help="Inspect one Evidence ID and its source/review gaps")
    select.add_argument("--claim", help="Inspect a Claim ID, including all its recorded revisions")
    select.add_argument("--assessment", help="Inspect a v0.2 Assessment ID and its context")
    parser.add_argument("--json", action="store_true")
    add_context_arguments(parser)
    args = parser.parse_args(argv)
    try:
        context = requested_context(args)
        paths = [p for p in discover(args.paths or [Path.cwd()]) if args.k.casefold() in str(p).casefold()]
        contracts = [explain_contract(p, context, args.evidence, args.claim, args.assessment) for p in paths]
        if context_options(args) and any(c["schema_version"] == "0.2" for c in contracts):
            raise ValueError("v0.2 contexts belong to recorded assessments; use --assessment ID or mceg assess")
        if args.evidence or args.claim or args.assessment:
            contracts = [c for c in contracts if c["items"]]
            if paths and not contracts:
                raise ValueError("Requested ID not found in the selected contracts")
    except (OSError, ValueError, yaml.YAMLError) as exc:
        parser.error(str(exc))
    uses_context = any(c["view"] == "overview" and c["model"] == "exogibbs.curated_gas.v1" and c["schema_version"] == "0.1"
                       for c in contracts)
    report = {"format": "mceg_explanation_v1", "context": context if uses_context else None, "contracts": contracts}
    if args.json:
        print(json.dumps(report, indent=2, allow_nan=False))
    else:
        display(report)
        if not contracts:
            print("No contracts selected.")
    return 0 if contracts else 5
