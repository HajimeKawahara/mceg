"""Command-line structural validation."""

import argparse
import json
import sys
from pathlib import Path

import yaml
from .validator import load_contract
from .provenance import trace_provenance


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate MCEG v0.1 contract structure.")
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
