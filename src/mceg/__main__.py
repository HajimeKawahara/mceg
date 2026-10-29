"""Command-line structural validation."""

import argparse
import json
import sys
from pathlib import Path

import yaml
from .validator import load_contract
from .provenance import trace_provenance


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and not Path(argv[0]).is_file():
        if argv[0] == "init":
            from .initialization import main as command
            return command(argv[1:])
        if argv[0] == "check":
            from .check import main as command
            return command(argv[1:])
        if argv[0] == "coverage":
            from .coverage import main as command
            return command(argv[1:])
        if argv[0] == "docs":
            from .documentation import main as command
            return command(argv[1:])
        if argv[0] == "graph":
            from .graph import main as command
            return command(argv[1:])
        if argv[0] == "migrate":
            from .migration import main as command
            return command(argv[1:])
        if argv[0] == "assess":
            from .assessment import main as command
            return command(argv[1:])
        if argv[0] == "explain":
            from .explain import main as command
            return command(argv[1:])
    parser = argparse.ArgumentParser(
        prog="mceg",
        usage="%(prog)s COMMAND [OPTIONS]\n       %(prog)s [--trace EVIDENCE_ID] FILE [FILE ...]",
        description="Inspect scientific model contracts, evidence and review gaps.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Commands:\n"
            "  init      Start a model contract and register it for review.\n"
            "  check     Discover contracts and summarize available checks.\n"
            "  coverage  Find model registration and source-review gaps.\n"
            "  docs      Generate RST sources for a repository's Sphinx docs.\n"
            "  graph     Export recorded relationships as Graph JSON.\n"
            "  explain   Inspect gaps, evidence and concrete next steps.\n"
            "  migrate   Preserve a v0.1 contract in the v0.2 format.\n"
            "  assess    Evaluate explicit conditions and save scoped assessments.\n\n"
            "Examples:\n"
            "  mceg init mypkg.water --source src/mypkg/water.py --symbol concentration\n"
            "  mceg check -k curated\n"
            "  mceg explain -k curated --temperature 1750 --lang ja\n"
            "  mceg explain -k curated --plain\n"
            "  mceg contracts/h2_solubility.yaml\n\n"
            "Use mceg COMMAND -h for that command's options and usage."
        ),
    )
    parser.add_argument("paths", nargs="+", type=Path, help="YAML contract files")
    parser.add_argument("--trace", metavar="EVIDENCE_ID", help="Report recorded source ancestry as JSON")
    args = parser.parse_args(argv)
    failed = False
    for path in args.paths:
        try:
            contract = load_contract(path)
            report = trace_provenance(contract, args.trace) if args.trace else None
        except (OSError, ValueError, yaml.YAMLError) as exc:
            print(f"INVALID {path}: {exc}", file=sys.stderr)
            failed = True
        else:
            if report is None:
                print(f"VALID {path} (structure only)")
            else:
                print(json.dumps({"path": str(path), **report}, indent=2))
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
