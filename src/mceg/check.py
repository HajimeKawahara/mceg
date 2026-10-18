"""Discover contracts and report scoped, offline checks for human inspection."""

import argparse
from collections import Counter
import json
import math
from pathlib import Path

import yaml

from . import _curated
from .provenance import trace_provenance
from .validator import load_contract


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
    entry["declarations"] = [claim.model_dump() for claim in contract.claims]
    entry["checks"].append(result("structure", "PASS", "v0.1 structure and local references are consistent"))
    traces = [trace_provenance(contract, item.id) for item in contract.evidence]
    complete = sum(trace["recorded_audit_complete"] for trace in traces)
    issues = sorted({f"{issue['evidence']}: {issue['issue']}" for trace in traces for issue in trace["issues"]})
    entry["checks"].append(result("source_audit", "UNKNOWN" if issues else "PASS",
                                  f"{complete}/{len(traces)} evidence records have complete declared source traces", issues))
    if contract.model.id == "exogibbs.curated_gas.v1":
        checks, assessment = curated_checks(path, context)
        entry["checks"].extend(checks)
        entry["assessment"] = assessment
    else:
        entry["checks"].append(result("evidence_reuse", "UNKNOWN", "No automatic evidence-reuse rule for this model"))
    return entry


def display(report, verbose):
    print("MCEG checks: recorded structure, source audits and scoped evidence reuse")
    print(f"Collected {report['collected']} contracts; selected {len(report['contracts'])}")
    if any(c["model"] == "exogibbs.curated_gas.v1" for c in report["contracts"]):
        context = report["context"]
        print(f"Curated context ({report['context_source']}): "
              f"T={context.get('temperature_K', '?')} K, P={context.get('pressure_bar', '?')} bar, "
              f"network={context.get('network', '?')}")
        print(f"  composition={context.get('composition', '?')}; "
              f"Python={context.get('python', '?')}, JAX={context.get('jax', '?')}, "
              f"{context.get('backend', '?')}/{context.get('dtype', '?')}, "
              f"epsilon={context.get('epsilon_crit', '?')}")
        print("  Context describes the requested target; the installed numerical environment is not inspected.")
    for contract in report["contracts"]:
        path = Path(contract["path"])
        try:
            label = str(path.relative_to(Path.cwd()))
        except ValueError:
            label = str(path)
        print(f"\n{label}")
        for check in contract["checks"]:
            print(f"  {check['status']:<7} {check['name']:<22} {check['message']}")
            if verbose or check["status"] == "FAIL":
                for detail in check["details"]:
                    print(f"          {detail}")
        if verbose and contract["declarations"]:
            print("  Recorded v0.1 declarations (not reassessed by structure/source checks):")
            for claim in contract["declarations"]:
                print(f"    {claim['id']}: {claim['status']} [{claim['kind']}]")
    counts = report["summary"]
    print(f"\n{counts['PASS']} passed, {counts['FAIL']} failed, {counts['UNKNOWN']} unknown")
    print("UNKNOWN identifies missing support or review gaps. These checks do not run numerical solvers.")


def positive(value):
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("Use a finite positive value")
    return number


def main(argv=None):
    parser = argparse.ArgumentParser(prog="mceg check", description=__doc__)
    parser.add_argument("paths", nargs="*", type=Path, help="Files or directories; default: current directory")
    parser.add_argument("-k", default="", metavar="NAME", help="Case-insensitive substring of contract paths")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show audit gaps and recorded Claim declarations")
    parser.add_argument("--json", action="store_true", help="Write the full check report as JSON to stdout")
    parser.add_argument("--context", type=Path, help="Curated context JSON; otherwise use the bundled archived example")
    parser.add_argument("--temperature", type=positive, metavar="K", help="Override curated temperature in kelvin")
    parser.add_argument("--pressure", type=positive, metavar="BAR", help="Override curated pressure in bar")
    parser.add_argument("--network", choices=["ions", "neutral"], help="Override curated network")
    parser.add_argument("--jax", help="Override the requested JAX version; does not inspect installed JAX")
    args = parser.parse_args(argv)
    try:
        context = json.loads((args.context or _curated.HERE / "context.json").read_text())
        if not isinstance(context, dict):
            raise ValueError("Context must be a JSON object")
        overrides = {"temperature_K": args.temperature, "pressure_bar": args.pressure,
                     "network": args.network, "jax": args.jax}
        context.update({k: v for k, v in overrides.items() if v is not None})
        context = _curated.Context.model_validate(context).model_dump(exclude_none=True)
        paths = discover(args.paths or [Path.cwd()])
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    selected = [p for p in paths if args.k.casefold() in str(p).casefold()]
    contracts = [check_contract(p, context) for p in selected]
    counts = Counter(check["status"] for entry in contracts for check in entry["checks"])
    report = {"format": "mceg_check_report_v1", "collected": len(paths), "contracts": contracts,
              "context": context,
              "context_source": str(args.context) if args.context else "archived example defaults with CLI overrides",
              "summary": {s: counts[s] for s in ("PASS", "FAIL", "UNKNOWN")}}
    if args.json:
        print(json.dumps(report, indent=2, allow_nan=False))
    else:
        display(report, args.verbose)
        if not selected:
            print("No contracts selected. Use a contract file or a directory containing YAML contracts.")
    return 5 if not selected else 1 if counts["FAIL"] else 0
