"""Inspect review gaps and next steps without fetching sources or changing evidence."""

import argparse
import json
import os
from pathlib import Path
import shlex
import shutil
import sys
import textwrap

import yaml

from .check import (add_context_arguments, audit_scope, check_contract, context_options,
                    discover, integrity_checks, requested_context, scope_message, source_audit)
from .integrity import resolve_root
from .provenance import trace_provenance
from .schema_v02 import ContractV02
from .validator import load_contract
from ._display import (add_language_argument, check_message, detail, language_command,
                       translate, wrap)


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
        "Compare the equations, tables or code at the source locations below. Check values, units, definitions and the materials and conditions covered.",
        "After inspecting both sources, record where you compared them, what agrees and what differs."),
    "comparison_discrepancy": action(
        "The comparison found differences. Check whether units, definitions, conditions or transcription explain them before changing a claim.",
        "Record how each difference was explained, or which differences still need investigation."),
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
    by_id = {e.id: e for e in contract.evidence}
    evidence = by_id[evidence_id]
    trace = trace_provenance(contract, evidence_id)
    local = [i for i in trace["issues"] if i["evidence"] == evidence_id]
    issues = list(dict.fromkeys(i["issue"] for i in local))
    upstream = list(dict.fromkeys(i["evidence"] for i in trace["issues"] if i["evidence"] != evidence_id))
    links = evidence.provenance.derived_from if evidence.provenance else []
    steps = []
    for key in issues:
        step = dict(SOURCE_ACTIONS[key])
        targets = []
        for link in links:
            if key != f"comparison_{link.comparison}":
                continue
            source = by_id[link.evidence]
            provenance = source.provenance
            targets.append({"evidence": source.id, "summary": source.summary, "sources": source.sources,
                            "location": provenance.location if provenance else None,
                            "inspection": provenance.inspection if provenance else None, "note": link.note})
        if targets:
            step["comparison_targets"] = targets
        steps.append(step)
    pending_comparisons = [link.evidence for link in links if link.comparison != "consistent"]
    return {"id": evidence.id, "record": evidence.model_dump(exclude_none=True), "issues": issues,
            "recorded_follow_ups": recorded_follow_ups(contract, "evidence", evidence_id),
            "suggested_steps": steps,
            "comparisons": [link.model_dump() for link in links],
            "upstream_gaps": upstream,
            "next_commands": list(dict.fromkeys([command(path, "--evidence", key) for key in
                                                  [*upstream, *pending_comparisons]] +
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
    if name in {"selected_files", "artifact_hashes"} and "integrity" in entry:
        return [action("Inspect the listed file pins against the supplied root, including any unchecked sources.",
                       "Resolve path or access issues, or review new evidence for changed bytes. Missing pins and URI sources remain unchecked; matching hashes do not establish scientific support.")]
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


def completed_comparisons(contract, item, completed):
    """Find declared follow-up comparisons of the same recorded source.

    A completion must cite an inspected comparison, with an inspected upstream
    source identified by its ID or artifact hash. A shared URL alone is not enough.
    This routes readers to the follow-up; it never changes the original audit.
    """
    by_id = {e.id: e for e in contract.evidence}
    results = []
    for old in item.get("comparisons", []):
        if old["comparison"] != "not_checked":
            continue
        source = by_id[old["evidence"]]
        hashes = {a.sha256 for a in source.artifacts}
        for key in dict.fromkeys(key for r in completed for key in r["evidence"]):
            review = by_id[key]
            if not review.provenance:
                continue
            for link in review.provenance.derived_from:
                upstream = by_id[link.evidence]
                # Schema validation already requires both sides of a checked link
                # to be inspected.
                if link.comparison == "not_checked":
                    continue
                if source.id == upstream.id or hashes & {a.sha256 for a in upstream.artifacts}:
                    results.append({"upstream": source.id, "evidence": review.id,
                                    "source": upstream.id, "comparison": link.comparison,
                                    "summary": review.summary})
    return results


def apply_resolutions(contract, path, item):
    """Separate completed authored work from suggestions without rewriting source gaps."""
    if not isinstance(contract, ContractV02):
        return
    resolutions = {r.follow_up: r for r in contract.follow_up_resolutions}
    instructions = item.get("recorded_follow_ups", [])
    completed = [{**resolutions[f["id"]].model_dump(), "instruction": f}
                 for f in instructions if f["id"] in resolutions]
    if not completed:
        return
    item["recorded_follow_ups"] = [f for f in instructions if f["id"] not in resolutions]
    item["resolved_follow_ups"] = completed
    reviewed_sources = set()
    if not item["recorded_follow_ups"]:
        comparisons = completed_comparisons(contract, item, completed)
        if comparisons:
            item["completed_comparisons"] = comparisons
        reviewed_sources = {c["upstream"] for c in comparisons}
        pending, historical = [], []
        for step in item.get("suggested_steps", []):
            if step == SOURCE_ACTIONS["source_not_fully_inspected"]:
                historical.append(step)
            elif step["action"] == SOURCE_ACTIONS["comparison_not_checked"]["action"]:
                targets = step.get("comparison_targets", [])
                old = [t for t in targets if t["evidence"] in reviewed_sources]
                remaining = [t for t in targets if t["evidence"] not in reviewed_sources]
                if old:
                    historical.append({**step, "comparison_targets": old})
                if remaining or not old:
                    pending.append({**step, "comparison_targets": remaining})
            else:
                pending.append(step)
        item["suggested_steps"] = pending
        if historical:
            item["historical_steps"] = historical
    evidence_ids = {key for r in completed for key in r["evidence"]}
    # Offer explicitly linked assessments, without guessing a latest version from IDs.
    assessments = [a.id for a in contract.assessments if evidence_ids.intersection(a.evidence)]
    historical_commands = {command(path, "--evidence", key) for key in reviewed_sources
                           if key not in item.get("upstream_gaps", [])}
    item["next_commands"] = list(dict.fromkeys([
        *(command(path, "--assessment", key) for key in assessments),
        *(command(path, "--evidence", key) for r in completed for key in r["evidence"]),
        *(c for c in item.get("next_commands", []) if c not in historical_commands),
    ]))


def explain_contract(path, context, evidence_id=None, claim_id=None, assessment_id=None, *, root=None):
    root = resolve_root(root, assessment_id)
    if root is not None and (evidence_id is not None or claim_id is not None):
        raise ValueError("--root requires an Assessment view")
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
        selected = next((a for a in getattr(contract, "assessments", []) if a.id == assessment_id), None)
        report.update(view="assessment", items=[])
        if selected is not None:
            audit, traces = source_audit(contract, selected.evidence)
            gaps = {}
            for trace in traces:
                for issue in trace["issues"]:
                    gaps.setdefault(issue["evidence"], set()).add(issue["issue"])
            report.update(audit_scope=audit_scope(selected),
                          audited_evidence=[trace["evidence"] for trace in traces],
                          evidence_gaps={key: sorted(value) for key, value in gaps.items()},
                          items=[assessment_detail(contract, path, selected),
                                 {**audit, "suggested_steps": check_steps("source_audit", {})
                                  if audit["status"] != "PASS" else []}])
            if root is not None:
                checks, report["integrity"] = integrity_checks(contract, selected, report["audited_evidence"], root)
                report["items"].extend({**check, "suggested_steps": check_steps(check["name"], report)
                                        if check["status"] != "PASS" else []} for check in checks)
    else:
        entry = check_contract(path, context)
        report["audit_scope"] = entry["audit_scope"]
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
    for item in report["items"]:
        apply_resolutions(contract, path, item)
    return report


def display(report, lang="en", plain=False):
    terminal = not plain and sys.stdout.isatty()
    width = max(40 if terminal else 60, shutil.get_terminal_size().columns)
    color = terminal and not os.environ.get("NO_COLOR") and os.environ.get("TERM") != "dumb"
    symbols = {"PASS": "✓", "FAIL": "✗", "UNKNOWN": "?", "inspect": "→"}
    try:
        "✓✗→".encode(sys.stdout.encoding or "ascii")
    except UnicodeEncodeError:
        symbols.update(PASS="+", FAIL="x", inspect=">")
    colors = {"PASS": "32", "FAIL": "31", "UNKNOWN": "33"}

    def t(message):
        return translate(message, lang)

    def paint(text, code):
        return f"\033[{code}m{text}\033[0m" if color and code else text

    def inspect(next_command, indent="    "):
        label = (symbols["inspect"] + " " if terminal else "") + t("Inspect") + ": "
        # Keep commands on one physical line so paths and options remain copyable.
        print(indent + paint(label, "1;36") + language_command(next_command, lang))

    def write(text, indent="    ", code=None):
        print(paint(wrap(indent + text, width, indent, lang), code))

    def terminal_record(value, indent="    ", labels=True):
        for key, content in value.items():
            if content is None or content == [] or content == {}:
                continue
            label = t(key.replace("_", " ").capitalize()) if labels else key
            if key in {"selected_files", "artifacts", "samples"} and labels:
                write(f"{label}: {len(content)}", indent, "2")
                if key == "selected_files":
                    for path, digest in content.items():
                        if digest is None:
                            write(t("Missing file") + ": " + path, indent + "  ", "33")
                continue
            if isinstance(content, dict):
                write(label, indent, "1")
                terminal_record(content, indent + "  ", key not in {"settings", "quantities"})
            elif isinstance(content, list):
                write(label, indent, "1")
                for entry in content:
                    if isinstance(entry, dict):
                        terminal_record(entry, indent + "  ")
                    else:
                        write("- " + str(entry), indent + "  ")
            else:
                # Values are original scientific text, including status and result tokens.
                write(f"{label}: {content}", indent)

    def record(value):
        if terminal:
            terminal_record(value)
            return
        value = dict(value)
        if "samples" in value and len(value["samples"]) > 2:
            samples = value.pop("samples")
            value.update(sample_count=len(samples), sample_preview=samples[:2],
                         remaining_samples=t("Use --json to inspect all joint samples."))
        print(textwrap.indent(yaml.safe_dump(value, sort_keys=False, allow_unicode=True).rstrip(), "    "))

    heading = t("MCEG next steps: recorded gaps and suggested work; no evidence is changed.")
    if terminal:
        write(heading, "", "1")
    else:
        print(heading)
    if lang == "ja":
        note = t("Contract text, authored instructions and IDs are shown in their original language.")
        if terminal:
            write(note, "", "2")
        else:
            print(note)
    if any(c["view"] == "overview" and c["model"] == "exogibbs.curated_gas.v1" and c["schema_version"] == "0.1"
           for c in report["contracts"]):
        print(paint(t("Requested curated context (not an inspection of the installed environment):"), "1"))
        if terminal:
            terminal_record(report["context"], labels=False)
        else:
            print(yaml.safe_dump(report["context"], sort_keys=False).rstrip())
    for contract in report["contracts"]:
        path = Path(contract["path"])
        print()
        if terminal:
            print(paint("-" * min(width, 72), "2"))
        print(paint(f"{path} [{contract['model']}; v{contract['schema_version']}]", "1;36"))
        if "audit_scope" in contract:
            write(t("Scope") + ": " + scope_message(contract["audit_scope"]))
        if "integrity" in contract:
            write("File root: " + contract["integrity"]["root"])
        for item in contract["items"]:
            label = item.get("id", item.get("name"))
            if "id" not in item and (lang == "ja" or terminal):
                label = t(item["name"].replace("_", " ").capitalize())
            status = item.get("status")
            print()
            if terminal and status:
                write(f"{symbols[status]} {status}  {label}", "  ", "1;" + colors[status])
            elif terminal:
                write(t(contract["view"].capitalize()) + ": " + label, "  ", "1;36")
            else:
                print(f"  {label}")
            if item.get("resolved_follow_ups"):
                write(t("Review progress"), code="1;36")
                write(t("Follow-up work has a completion record. Its results are listed below."))
                if item.get("completed_comparisons"):
                    write(t("The sources below have follow-up comparison results. Their old 'not_checked' entries are kept as history."))
                    for comparison in item["completed_comparisons"]:
                        outcome = ("The compared parts agree." if comparison["comparison"] == "consistent"
                                   else "Compared; differences remain to be explained.")
                        write(t(outcome) + " " + comparison["evidence"], "      ")
                        write(comparison["summary"], "        ")
                elif item.get("historical_steps"):
                    write(t("The source-reading task has a completion record. The old inspection state is kept as history."))
                write(t("Task completion does not establish model accuracy. Use the linked assessments to see what the evidence supports."))
            if "record" in item:
                if item.get("resolved_follow_ups"):
                    write(t("Original record (history retained)"), code="1")
                record(item["record"])
                for key in ("subject", "context", "claim", "condition"):
                    if key in item:
                        print(paint(f"  {t(key)}:", "1;36"))
                        record(item[key])
            else:
                message = check_message(item, lang)
                write(message if terminal else f"{item['status']}: {message}")
                # Source gaps already have their own navigation list below.
                if not terminal or item["name"] != "source_audit":
                    for message in item["details"]:
                        if terminal:
                            write(detail(message, lang), "    ", "2")
                        else:
                            print(f"    {detail(message, lang)}")
            number = 0
            for resolution in item.get("resolved_follow_ups", []):
                write(t("Completed follow-up") + ": " + resolution["follow_up"], code="1;36")
                write(resolution["note"], "      ")
                write(t("Recorded task completion only; historical source fields and support judgments are unchanged."),
                      "      ", "2")
            for field, label in (("recorded_follow_ups", "Recorded next step"), ("suggested_steps", "Suggested next step")):
                # Authored follow-ups are scientific record content, not UI messages.
                step_text = t if field == "suggested_steps" else str
                for step in item.get(field, []):
                    number += 1
                    if terminal:
                        print()
                        write(f"{number}. {t(label)}", code="1;36")
                        write(step_text(step["action"]), "      ")
                    else:
                        write(f"{t(label)}: {step_text(step['action'])}")
                    for target in step.get("comparison_targets", []):
                        write(t("Comparison target") + ": " + target["evidence"], "      ", "1")
                        for key, title in (("summary", "Summary"), ("inspection", "Inspection"),
                                           ("location", "Location"), ("note", "Comparison note")):
                            if target.get(key):
                                write(f"{t(title)}: {target[key]}", "        ")
                        for source in target["sources"]:
                            print(f"        {t('Source')}: {source}")
                    requirements = step.get("requires", [])
                    if terminal and requirements:
                        write(t("Needed"), "      ", "1")
                    for requirement in requirements:
                        if terminal:
                            write("- " + step_text(requirement), "        ")
                        else:
                            write(f"{t('Needed')}: {step_text(requirement)}", "      ")
                    for source in step.get("sources", []):
                        print(f"      {t('Source')}: {source}")
                    if terminal:
                        write(t("Completion"), "      ", "1")
                        write(step_text(step["completion"]), "        ")
                    else:
                        write(f"{t('Completion')}: {step_text(step['completion'])}", "      ")
            for next_command in item.get("next_commands", []):
                inspect(next_command)
        if contract.get("evidence_gaps"):
            print("\n" + paint("  " + t("Evidence gaps (IDs for --evidence)") + ":", "1;33"))
            for key, issues in contract["evidence_gaps"].items():
                message = f"{key}: {', '.join(t(issue) for issue in issues)}"
                if terminal:
                    write("? " + message)
                else:
                    print("    " + message)
            first = next(iter(contract["evidence_gaps"]))
            inspect(command(path, "--evidence", first), "  ")
        if contract.get("unknown_claims"):
            print("  " + t("Unknown Claim IDs") + ": " + ", ".join(contract["unknown_claims"]))
            inspect(command(path, "--claim", contract["unknown_claims"][0]), "  ")
        for assessment in contract.get("assessments", []):
            print(f"  Assessment {assessment['id']}: {assessment['result']}; context={assessment['context']}")
            inspect(command(path, "--assessment", assessment["id"]), "  ")
    if terminal:
        print()
        write(t("Use --plain for the original text layout or --json for complete records."), "", "2")


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="mceg explain", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  mceg explain -k curated --temperature 1750\n"
            "  mceg explain -k curated --evidence source_choices --lang ja\n"
            "  mceg explain contract.yaml --claim physical_accuracy\n"
            "  mceg explain contract.yaml --assessment imported:physical_accuracy\n"
            "  mceg explain --package exogibbs --model exogibbs.curated_gas.v1 --species HCN\n"
            "  mceg explain -k curated --plain\n"
            "  mceg explain -k curated --json\n\n"
            "Terminals use highlighted output; pipes and --plain use the original text layout."
        ),
    )
    parser.add_argument("paths", type=Path, nargs="*", help="Contract files/directories; default: current directory")
    catalog_source = parser.add_mutually_exclusive_group()
    catalog_source.add_argument("--package", help="Read an installed distribution's packaged evidence catalog without importing it")
    catalog_source.add_argument("--catalog", type=Path, help="Read an explicit evidence index.json (including editable checkouts)")
    parser.add_argument("--model", help="Select an exact model ID in a package/catalog")
    parser.add_argument("--species", help="Select an exact species ID or declared alias in a package/catalog")
    parser.add_argument("-k", default="", metavar="NAME", help="Filter contract paths, as in mceg check")
    select = parser.add_mutually_exclusive_group()
    select.add_argument("--evidence", help="Inspect one Evidence ID and its source/review gaps")
    select.add_argument("--claim", help="Inspect a Claim ID, including all its recorded revisions")
    select.add_argument("--assessment", help="Inspect a v0.2 Assessment ID and its context")
    parser.add_argument("--root", type=Path, metavar="DIR",
                        help="Verify local file hashes relative to DIR; requires --assessment ID")
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--plain", action="store_true", help="Use the original text layout without color or markers")
    output.add_argument("--json", action="store_true", help="Write the complete machine-readable report")
    add_context_arguments(parser)
    add_language_argument(parser)
    args = parser.parse_args(argv)
    try:
        if args.package or args.catalog:
            if (args.paths or args.k or args.root or args.evidence or args.claim or args.assessment
                    or context_options(args)):
                raise ValueError("Package/catalog lookup cannot be combined with contract selectors or context options; "
                                 "inspect the reported contract separately for those views")
            from .catalog import display_catalog, explain_catalog
            report = explain_catalog(package=args.package, catalog=args.catalog,
                                     model=args.model, species=args.species)
            if args.json:
                print(json.dumps(report, indent=2, allow_nan=False))
            else:
                display_catalog(report, args.lang)
            return 0 if any(m["records"] for m in report["models"]) else 5
        if args.model or args.species:
            raise ValueError("--model and --species require --package or --catalog")
        root = resolve_root(args.root, args.assessment)
        context = requested_context(args)
        paths = [p for p in discover(args.paths or [Path.cwd()]) if args.k.casefold() in str(p).casefold()]
        contracts = [explain_contract(p, context, args.evidence, args.claim, args.assessment, root=root) for p in paths]
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
        display(report, args.lang, args.plain)
        if not contracts:
            print(translate("No contracts selected.", args.lang))
    return 0 if contracts else 5
