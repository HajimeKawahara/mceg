"""Replay the curated-gas example with MCEG's shared, provider-free evaluator."""

import argparse
import json
from pathlib import Path

from mceg._curated import (
    Context, FilePin, IMPLEMENTATION, METHOD, Review, checked_pin, local_path,
    run, sha256,
)


HERE = Path(__file__).resolve().parent


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exogibbs", type=Path, required=True)
    parser.add_argument("--context", type=Path, default=HERE / "context.json")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = run(args.exogibbs, json.loads(args.context.read_text()))
    except (OSError, ValueError, KeyError, StopIteration) as exc:
        parser.error(str(exc))
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(f"Wrote {args.output}; archived numerical evidence only; physical validation unknown")


if __name__ == "__main__":
    main()
