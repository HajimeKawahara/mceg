"""Lossless declaration migration into the v0.2 schema; no new scientific review."""

import argparse
import hashlib
import json
from pathlib import Path

import yaml

from .schema import Contract, Evidence
from .schema_v02 import ContractV02
from .validator import load_contract


def content_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def write_document(value, path):
    """Write a new artifact only; never replace a source or an earlier result."""
    text = (json.dumps(value, indent=2, allow_nan=False) + "\n" if Path(path).suffix == ".json" else
            yaml.safe_dump(value, sort_keys=False, allow_unicode=True))
    with Path(path).open("x", encoding="utf-8") as stream:
        stream.write(text)


def migrate_contract(path: str | Path) -> ContractV02:
    original = load_contract(path)
    if not isinstance(original, Contract):
        raise ValueError("Migration requires a v0.1 contract")
    digest = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    data = original.model_dump()
    data.update(schema_version="0.2", migration={"from_schema": "0.1", "source_sha256": digest,
                                               "content_sha256": content_hash(original.model_dump()),
                                               "evidence_ids": [e.id for e in original.evidence]},
                subjects=[{"id": "imported", "implementation": data["model"]["implementation"]}],
                contexts=[], assessments=[])
    for claim in data["claims"]:
        context_id = "imported:" + claim["id"]
        data["contexts"].append({"id": context_id, "scope": claim["scope"]})
        data["assessments"].append({
            "id": "imported:" + claim["id"], "kind": "evidence_support",
            "subject": "imported", "context": context_id, "claim": claim["id"],
            "claim_revision": "sha256:" + digest, "status": claim.pop("status"),
            "evidence": claim.pop("evidence"), "origin": "imported_v0.1_declaration",
            "method": {"id": "import_v0.1_declaration", "revision": "1",
                       "description": "Preserve the original declaration; no new assessment."},
            "reasons": ["Imported declaration for the original implementation and prose scope; "
                        "structured calculation conditions were not supplied."],
        })
        claim["revision"] = "sha256:" + digest
    return ContractV02.model_validate(data)


def restore_v01(contract: ContractV02) -> Contract:
    """Reconstruct the original validated data, rejecting changes to that content."""
    if contract.migration is None:
        raise ValueError("No v0.1 migration record")
    declarations = {(a.claim, a.claim_revision): a for a in contract.assessments
                    if a.kind == "evidence_support" and a.origin == "imported_v0.1_declaration"}
    data = contract.model_dump(include={"model", "assumptions", "domains", "limitations"})
    evidence = {e.id: e for e in contract.evidence}
    data.update(schema_version="0.1", claims=[], evidence=[
        evidence[key].model_dump(include=set(Evidence.model_fields)) for key in contract.migration.evidence_ids
    ])
    for claim in contract.claims:
        assessment = declarations.get((claim.id, claim.revision))
        if assessment is not None:
            data["claims"].append({**claim.model_dump(exclude={"revision"}), "status": assessment.status,
                                   "evidence": assessment.evidence})
    restored = Contract.model_validate(data)
    if content_hash(restored.model_dump()) != contract.migration.content_sha256:
        raise ValueError("Imported v0.1 content changed; cannot reconstruct the original declaration")
    return restored


def main(argv=None):
    parser = argparse.ArgumentParser(prog="mceg migrate", description=__doc__)
    parser.add_argument("contract", type=Path)
    parser.add_argument("--output", type=Path, required=True, help="New v0.2 YAML/JSON file; must not already exist")
    args = parser.parse_args(argv)
    try:
        migrated = migrate_contract(args.contract)
        write_document(migrated.model_dump(exclude_none=True), args.output)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        parser.error(str(exc))
    print(f"Wrote {args.output}; imported declarations only, no new scientific assessment")
    return 0
