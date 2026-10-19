"""Discover contracts and report scoped, offline checks for human inspection."""

import argparse
from collections import Counter
import json
import math
import os
from pathlib import Path
import shlex
import shutil
import sys
import textwrap

import yaml

from . import _curated
from .provenance import trace_provenance
from .validator import load_contract
from .schema_v02 import ContractV02
from .assessment import compare_condition
from ._display import (add_language_argument, check_message, detail, language_command,
                       translate, wrap)


def discover(paths):
    """Prefer conventional contract directories; never import provider code."""
    found = set()
    for path in paths:
        path = path.resolve()
        if not path.exists():
            raise ValueError(f"Path does not exist: {path}")
        if path.is_file():
            found.add(path)
            continue
        roots = [p for p in (path / "mceg/contracts", path / "contracts") if p.is_dir()]
        for root in roots or [path]:
            found.update(p.resolve() for p in root.rglob("*")
                         if p.is_file() and p.suffix in {".yaml", ".yml"}
                         and not any(part.startswith(".") for part in p.relative_to(root).parts))
    return sorted(found)


def result(name, status, message, details=()):
    return {"name": name, "status": status, "message": message, "details": list(details)}


def curated_checks(path, context):
    relative = Path("mceg/contracts/curated_gas.yaml")
    provider = next((p for p in path.parents if (p / relative).resolve() == path), None)
    if provider is None:
        return [result("evidence_reuse", "UNKNOWN", "Use the provider-owned mceg/contracts/curated_gas.yaml")], None
    try:
        report = _curated.run(provider, context)
    except ValueError as exc:
        return [result("evidence_reuse", "UNKNOWN", str(exc))], None
    except (OSError, KeyError, StopIteration, yaml.YAMLError) as exc:
        return [result("evidence_reuse", "FAIL", "Cannot read the reviewed evidence", [str(exc)])], None

    interval, sample, support = report["assessments"]
    files = report["integrity"]["files"]
    changed = [f["path"] for f in files if not f["matches"]]
    temperature = context.get("temperature_K")
    bounds = interval["interval"]
    checks = [result("selected_files", "FAIL" if changed else "PASS",
                     f"{len(files) - len(changed)}/{len(files)} recorded input/output hashes match", changed)]
    classification = interval["classification"]
    state = {"within_reported_range": "PASS", "outside_reported_range": "FAIL", "unknown": "UNKNOWN"}[classification]
    location = {"within_reported_range": "within", "outside_reported_range": "outside", "unknown": "not compared with"}[classification]
    checks.append(result("temperature_range", state,
                         f"{temperature if temperature is not None else 'Missing temperature'} K; "
                         f"{location} numerical interval {bounds['lower']:g}--{bounds['upper']:g} K"))
    sampled = sample["classification"] == "at_recorded_sample"
    checks.append(result("sample_coverage", "PASS" if sampled else "UNKNOWN",
                         "Requested T/P/network is an archived sample" if sampled else
                         "No archived sample established for the requested T/P/network"))
    messages = {
        "selected_files_changed_or_missing": "Recorded files changed or are missing",
        "recorded_support_incomplete": "The recorded numerical comparison is incomplete",
        "missing_context": "Missing context: " + ", ".join(support["missing_context"]),
        "unreviewed_context": "Different context: " + ", ".join(support["different_context"]),
        "no_recorded_sample": "Requested condition is not covered by an archived sample",
        "outside_evaluation_domain": "Temperature is outside the numerical evaluation interval",
        "reviewed_declaration_reused": "Reviewed evidence supports this context",
    }
    reasons = [messages[key] for key in support["reasons"]]
    checks.append(result("evidence_reuse", "PASS" if support["status"] == "supported" else "UNKNOWN",
                         "; ".join(reasons),
                         [f"Historical numerical result: {report['evidence']['result']}",
                          "Support is limited to the explicitly reviewed equilibrium_verification claim."]))
    checks.append(result("physical_validation", "UNKNOWN", "Whole-mixture physical accuracy is unestablished"))
    return checks, report


def check_contract(path, context):
    entry = {"path": str(path), "model": None, "checks": [], "declarations": []}
    try:
        contract = load_contract(path)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        entry["checks"] = [result("structure", "FAIL", "Invalid contract", [str(exc)])]
        return entry
    entry["model"] = contract.model.id
    entry["schema_version"] = contract.schema_version
    if contract.schema_version == "0.1":
        entry["declarations"] = [claim.model_dump() for claim in contract.claims]
    entry["checks"].append(result("structure", "PASS", f"v{contract.schema_version} structure and local references are consistent"))
    traces = [trace_provenance(contract, item.id) for item in contract.evidence]
    complete = sum(trace["recorded_audit_complete"] for trace in traces)
    issues = sorted({f"{issue['evidence']}: {issue['issue']}" for trace in traces for issue in trace["issues"]})
    entry["checks"].append(result("source_audit", "UNKNOWN" if issues else "PASS",
                                  f"{complete}/{len(traces)} evidence records have complete declared source traces", issues))
    if isinstance(contract, ContractV02):
        entry["assessments"] = [a.model_dump() for a in contract.assessments]
        contexts = {c.id: c for c in contract.contexts}
        conditions = {(c.id, c.revision): c for c in contract.conditions}
        for assessment in contract.assessments:
            if assessment.kind == "evidence_support":
                continue
            classification, reasons = compare_condition(
                conditions[assessment.condition, assessment.condition_revision], contexts[assessment.context])
            status = {"within_reported_range": "PASS", "outside_reported_range": "FAIL",
                      "at_recorded_sample": "PASS", "not_sampled": "UNKNOWN", "unknown": "UNKNOWN"}[classification]
            if classification != assessment.classification:
                status = "FAIL"
                reasons.append("Recorded classification differs from the current Condition/Context; review the changed record.")
            entry["checks"].append(result(assessment.condition, status,
                f"context={assessment.context}; {classification}", [f"Assessment: {assessment.id}", *reasons]))
        entry["checks"].append(result("evidence_reuse", "UNKNOWN",
            "Stored support assessments are scoped records; inspect a specific assessment with mceg explain"))
    elif contract.model.id == "exogibbs.curated_gas.v1":
        checks, assessment = curated_checks(path, context)
        entry["checks"].extend(checks)
        entry["assessment"] = assessment
    else:
        entry["checks"].append(result("evidence_reuse", "UNKNOWN", "No automatic evidence-reuse rule for this model"))
    return entry


def display(report, verbose, plain=False, lang="en"):
    terminal = not plain and sys.stdout.isatty()
    color = terminal and not os.environ.get("NO_COLOR") and os.environ.get("TERM") != "dumb"
    width = max(40, shutil.get_terminal_size().columns)
    symbols = {"PASS": "✓", "FAIL": "✗", "UNKNOWN": "?"}
    try:
        "✓✗".encode(sys.stdout.encoding or "ascii")
    except UnicodeEncodeError:
        symbols.update(PASS="+", FAIL="x")
    colors = {"PASS": "32", "FAIL": "31", "UNKNOWN": "33"}

    def t(message):
        return translate(message, lang)

    def paint(text, code):
        return f"\033[{code}m{text}\033[0m" if color else text

    def write(text, code=None, indent="  "):
        if terminal:
            text = wrap(text, width, indent, lang)
        print(paint(text, code) if code else text)

    write(t("MCEG checks: recorded structure, source audits and scoped evidence reuse"), "1")
    write(t(f"Collected {report['collected']} contracts; selected {len(report['contracts'])}"))
    if any(c["model"] == "exogibbs.curated_gas.v1" and c.get("schema_version") == "0.1"
           for c in report["contracts"]):
        context = report["context"]
        source = report["context_source"]
        if source == "archived example defaults with CLI overrides":
            source = t(source)
        write(f"{t('Curated context')} ({source}): "
              f"T={context.get('temperature_K', '?')} K, P={context.get('pressure_bar', '?')} bar, "
              f"network={context.get('network', '?')}")
        write(f"  composition={context.get('composition', '?')}; "
              f"Python={context.get('python', '?')}, JAX={context.get('jax', '?')}, "
              f"{context.get('backend', '?')}/{context.get('dtype', '?')}, "
              f"epsilon={context.get('epsilon_crit', '?')}")
        write(t("  Context describes the requested target; the installed numerical environment is not inspected."))
    for contract in report["contracts"]:
        path = Path(contract["path"])
        try:
            label = str(path.relative_to(Path.cwd()))
        except ValueError:
            label = str(path)
        print()
        write(label, "1;36")
        for check in contract["checks"]:
            message = check_message(check, lang)
            name = t(check["name"].replace("_", " ").capitalize())
            if terminal:
                status = check["status"]
                badge = f"{symbols[status]} {status:<7}"
                prefix = f"  {badge} {name:<22} "
                if width < 80 or lang == "ja":
                    print(f"  {paint(badge, '1;' + colors[status])} {name}")
                    write("      " + message, indent="      ")
                else:
                    line = textwrap.fill(prefix + message, width=width,
                                         subsequent_indent=" " * len(prefix))
                    print(line.replace(badge, paint(badge, '1;' + colors[status]), 1))
            else:
                label = name if lang == "ja" else check["name"]
                print(f"  {check['status']:<7} {label:<22} {message}")
            if verbose or check["status"] == "FAIL":
                for item in check["details"]:
                    write("          " + detail(item, lang), indent="          ")
        if verbose and contract["declarations"]:
            write(t("  Recorded v0.1 declarations (not reassessed by structure/source checks):"))
            for claim in contract["declarations"]:
                write(f"    {claim['id']}: {claim['status']} [{claim['kind']}]")
        if verbose and contract.get("assessments"):
            write(t("  Recorded v0.2 assessments (each bound to its own subject and context):"))
            for assessment in contract["assessments"]:
                outcome = assessment.get("status", assessment.get("classification"))
                write(f"    {assessment['id']}: {outcome}; context={assessment['context']}")
    counts = report["summary"]
    print()
    if terminal:
        write("-" * min(width, 72), "2")
        print(", ".join(paint(f"{counts[status]} {t(label)}", "1;" + colors[status] if counts[status] else "2")
                        for status, label in (("PASS", "passed"), ("FAIL", "failed"), ("UNKNOWN", "unknown"))))
    else:
        print(t(f"{counts['PASS']} passed, {counts['FAIL']} failed, {counts['UNKNOWN']} unknown"))
    write(t("UNKNOWN identifies missing support or review gaps. These checks do not run numerical solvers."))
    if report.get("explain_command") and (counts["UNKNOWN"] or counts["FAIL"]):
        # Keep the command copyable even when terminal prose wraps at a narrow width.
        print(paint(t("Next steps") + ": " + language_command(report["explain_command"], lang), "36"))


def positive(value):
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("Use a finite positive value")
    return number


def add_context_arguments(parser):
    parser.add_argument("--context", type=Path, help="Curated v0.1 context JSON; for v0.2 use mceg assess")
    parser.add_argument("--temperature", type=positive, metavar="K", help="Override curated temperature in kelvin")
    parser.add_argument("--pressure", type=positive, metavar="BAR", help="Override curated pressure in bar")
    parser.add_argument("--network", choices=["ions", "neutral"], help="Override curated network")
    parser.add_argument("--jax", help="Override the requested JAX version; does not inspect installed JAX")


def requested_context(args):
    context = json.loads((args.context or _curated.HERE / "context.json").read_text())
    if not isinstance(context, dict):
        raise ValueError("Context must be a JSON object")
    overrides = {"temperature_K": args.temperature, "pressure_bar": args.pressure,
                 "network": args.network, "jax": args.jax}
    context.update({k: v for k, v in overrides.items() if v is not None})
    return _curated.Context.model_validate(context).model_dump(exclude_none=True)


def context_options(args):
    return [value for key in ("context", "temperature", "pressure", "network", "jax")
            if getattr(args, key) is not None for value in ("--" + key, str(getattr(args, key)))]


def main(argv=None):
    parser = argparse.ArgumentParser(prog="mceg check", description=__doc__)
    parser.add_argument("paths", nargs="*", type=Path, help="Files or directories; default: current directory")
    parser.add_argument("-k", default="", metavar="NAME", help="Case-insensitive substring of contract paths")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show audit gaps and recorded Claim declarations")
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--plain", action="store_true", help="Use the original text format without color or symbols")
    output.add_argument("--json", action="store_true", help="Write the full check report as JSON to stdout")
    add_context_arguments(parser)
    add_language_argument(parser)
    args = parser.parse_args(argv)
    try:
        context = requested_context(args)
        paths = discover(args.paths or [Path.cwd()])
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    selected = [p for p in paths if args.k.casefold() in str(p).casefold()]
    contracts = [check_contract(p, context) for p in selected]
    if context_options(args) and any(c.get("schema_version") == "0.2" for c in contracts):
        parser.error("For v0.2 contexts, use mceg assess CONTRACT --context FILE --subject ID --output NEW_FILE")
    counts = Counter(check["status"] for entry in contracts for check in entry["checks"])
    curated_context = any(c["model"] == "exogibbs.curated_gas.v1" and c.get("schema_version") == "0.1"
                          for c in contracts)
    report = {"format": "mceg_check_report_v1", "collected": len(paths), "contracts": contracts,
              "context": context if curated_context else None,
              "context_source": (str(args.context) if args.context else "archived example defaults with CLI overrides")
                                if curated_context else None,
              "summary": {s: counts[s] for s in ("PASS", "FAIL", "UNKNOWN")},
              "explain_command": shlex.join(["mceg", "explain", *map(str, args.paths),
                                             *(["-k", args.k] if args.k else []), *context_options(args)])}
    if args.json:
        print(json.dumps(report, indent=2, allow_nan=False))
    else:
        display(report, args.verbose, args.plain, args.lang)
        if not selected:
            print(translate("No contracts selected. Use a contract file or a directory containing YAML contracts.", args.lang))
    return 5 if not selected else 1 if counts["FAIL"] else 0
