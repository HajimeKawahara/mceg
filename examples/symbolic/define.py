"""Author the example's symbolic equations; --check never changes the contract."""

from __future__ import annotations

import argparse
from pathlib import Path

import sympy as sp
import yaml

from mceg.symbolic import from_sympy


def definitions() -> dict[str, sp.Basic]:
    """Construct fields and their relationships in trusted authoring code."""
    z, R, g = sp.symbols("z R g")
    P, rho, T = (sp.Function(name)(z) for name in ("P", "rho", "T"))
    return {
        "ideal_gas": sp.Eq(P, rho * R * T, evaluate=False),
        "hydrostatic_balance": sp.Eq(sp.Derivative(P, z), -rho * g, evaluate=False),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    path = Path(__file__).with_name("atmosphere.yaml")
    document = yaml.safe_load(path.read_text())
    records = {item["id"]: item for item in document["equations"]}
    changed = []
    for name, expression in definitions().items():
        source = from_sympy(expression).model_dump()
        record = records[name]
        if record.get("sympy") != source or "latex" in record:
            changed.append(name)
        record["sympy"] = source
        record.pop("latex", None)
    if args.check:
        if changed:
            raise SystemExit("Stale symbolic definitions: " + ", ".join(changed))
        print("Symbolic definitions match the authoring script.")
    else:
        path.write_text(yaml.safe_dump(document, sort_keys=False, width=100))
        print("Updated symbolic definitions in " + str(path))


if __name__ == "__main__":
    main()
