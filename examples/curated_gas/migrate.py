"""Losslessly split v0.1 declarations; an experiment, not a v0.2 reader."""

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from mceg import load_contract


def migrate(path):
    path = Path(path)
    original = load_contract(path).model_dump()
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    result = deepcopy(original)
    del result["schema_version"]
    result.update(format="assessment_migration_draft_v1",
                  original={"schema_version": "0.1", "contract_sha256": digest},
                  assessments=[])
    for claim in result["claims"]:
        target = {"model": original["model"]["id"], "claim": claim["id"],
                  "claim_revision": digest,
                  "implementation": deepcopy(original["model"]["implementation"])}
        result["assessments"].append({
            "id": f"{digest}#{claim['id']}:imported",
            "kind": "evidence_support", "target": target,
            "method": "import_v0.1_declaration", "origin": "imported_v0.1_declaration",
            "context": {"scope": claim["scope"], "structured_conditions": None},
            "status": claim.pop("status"), "evidence": claim.pop("evidence"),
            "rationale": "Preserve the original declaration; no new evaluation or text revision.",
        })
        claim["revision"] = digest
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("contract", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(migrate(args.contract), indent=2) + "\n")
