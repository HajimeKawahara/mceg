"""Exercise provider-local contracts and revision review in temporary copies.

Uses Git objects from the sibling checkouts; never writes to either checkout.
Only evidence file existence and hashes are checked. URL contents, fragments,
entry-point symbols and scientific applicability are not validated here.
This is an example script, not a new MCEG public API or source locator standard.
"""

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
from urllib.parse import urlsplit

import yaml

from mceg import Contract, load_contract, trace_provenance


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
SOURCE = "src/exogibbs/solubility/volatile.py"
OLD_EXPRESSION = "result = fugacity * jnp.exp(-11.403 - 0.76 * melt_pressure)"
NEW_EXPRESSION = "result = fugacity * jnp.exp(-11.303 - 0.76 * melt_pressure)"
FILE_PREFIXES = ("src/", "tests/", "documents/", "docs/", "examples/", "mceg/")


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def local_path(root, locator):
    """Resolve a repository-relative file, regardless of YAML location or cwd."""
    path = (root / locator.split("#", 1)[0]).resolve()
    path.relative_to(root.resolve())
    return path


def check_sources(contract_path, repository_root):
    contract = load_contract(contract_path)
    local, missing, external, opaque = {}, [], set(), set()
    for evidence in contract.evidence:
        for locator in evidence.sources:
            if urlsplit(locator).scheme:
                external.add(locator)
                continue
            if not locator.startswith(FILE_PREFIXES):
                opaque.add(locator)
                continue
            path = local_path(repository_root, locator)
            name = path.relative_to(repository_root.resolve()).as_posix()
            if path.is_file():
                local[name] = sha256(path)
            else:
                missing.append({"evidence": evidence.id, "locator": locator})
    return {
        "schema_valid": True, "local_files_complete": not missing,
        "local_file_sha256": local, "missing": missing,
        "external_not_checked": sorted(external), "fragments_checked": False,
        "opaque_not_checked": sorted(opaque),
        "entry_point_symbols_checked": False,
    }


def write_yaml(path, record):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(record, sort_keys=False, allow_unicode=True), encoding="utf-8")


def export_contract(source, checkout, destination):
    """Localize this baseline's own-source URLs and copy its MCEG audit files."""
    record = load_contract(source).model_dump(exclude_none=True)
    implementation = record["model"]["implementation"]
    prefix = implementation["repository"] + "/blob/" + implementation["revision"] + "/"
    for evidence in record["evidence"]:
        rewritten = []
        for locator in evidence["sources"]:
            if locator.startswith(prefix):
                locator = locator[len(prefix):]
                file_name = locator.split("#", 1)[0]
                data = subprocess.check_output([
                    "git", "-C", str(checkout), "show",
                    f"{implementation['revision']}:{file_name}",
                ])
                target = local_path(destination, file_name)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
            elif locator.startswith(FILE_PREFIXES):
                origin = local_path(ROOT, locator)
                locator = "mceg/evidence/" + locator
                target = local_path(destination, locator)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(origin, target)
            rewritten.append(locator)
        evidence["sources"] = rewritten
    target = destination / "mceg/contracts" / source.name
    write_yaml(target, record)
    return target


def revision_trial(provider_root, output_root):
    """Apply a predeclared synthetic change and manually authored review record."""
    parent = provider_root / "mceg/contracts/h2_solubility.yaml"
    parent_hash = sha256(parent)
    old = load_contract(parent)
    candidate_root = output_root / "candidate"
    shutil.copytree(provider_root, candidate_root)
    source = candidate_root / SOURCE
    before_hash = sha256(source)
    previous_sources = check_sources(parent, provider_root)["local_file_sha256"]
    original = source.read_text(encoding="utf-8")
    if original.count(OLD_EXPRESSION) != 1:
        raise ValueError("The manual revision exercise no longer matches the audited source")
    source.write_text(original.replace(OLD_EXPRESSION, NEW_EXPRESSION), encoding="utf-8")
    revision = "synthetic-sha256:" + sha256(source)

    # Negative control: the core accepts a revision-only edit with stale passes.
    stale = copy.deepcopy(old.model_dump(exclude_none=True))
    stale["model"]["implementation"]["revision"] = revision
    Contract.model_validate(stale)

    reviewed = load_contract(HERE / "candidate.yaml").model_dump(exclude_none=True)
    reviewed["model"]["implementation"]["revision"] = revision
    target = candidate_root / "mceg/contracts/h2_solubility.yaml"
    write_yaml(target, reviewed)
    # Preserve the parent primary-source audit as evidence for the known Eq. 6.
    audit = candidate_root / "mceg/evidence/docs/en/h2_primary_audit.md"
    audit.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / "docs/en/h2_primary_audit.md", audit)
    contract = load_contract(target)
    sources = check_sources(target, candidate_root)
    changed_files = [name for name, digest in previous_sources.items()
                     if sha256(candidate_root / name) != digest]
    if (not sources["local_files_complete"] or sha256(parent) != parent_hash
            or sha256(provider_root / SOURCE) != before_hash or changed_files != [SOURCE]):
        raise ValueError("Candidate references or parent preservation failed")
    previous_claims = {claim.id: claim for claim in old.claims}
    return {
        "synthetic": True,
        "change": {"path": SOURCE, "before": OLD_EXPRESSION, "after": NEW_EXPRESSION},
        "parent_revision": old.model.implementation.revision,
        "candidate_revision": revision,
        "source_sha256": {"before": before_hash, "after": sha256(source)},
        "changed_evidence_files": changed_files,
        "parent_contract_sha256": parent_hash, "parent_preserved": True,
        "candidate_contract_sha256": sha256(target),
        "negative_control": {
            "revision_only_edit_schema_valid": True,
            "stale_numerical_claim_still_supported": next(
                claim for claim in stale["claims"] if claim["id"] == "formula_evaluation"
            )["status"] == "supported",
        },
        "manual_review": [{"claim": claim.id, "before": previous_claims[claim.id].status,
                           "after": claim.status, "reason": claim.scope} for claim in contract.claims],
        "evidence_results": {e.id: e.result for e in contract.evidence if e.result is not None},
        "candidate_sources": sources,
        "candidate_trace": trace_provenance(contract, "implementation"),
        "candidate_executed": False,
    }


def run(output_root, checkouts):
    output_root = output_root.resolve()
    if any(output_root.is_relative_to(path.resolve()) for path in checkouts.values()):
        raise ValueError("Use an output directory outside the provider checkouts")
    output_root.mkdir(parents=True, exist_ok=False)
    # An unchanged YAML still validates when its repository-local audit is absent.
    negative_root = output_root / "naive-copy"
    negative = negative_root / "mceg/contracts/h2_solubility.yaml"
    negative.parent.mkdir(parents=True)
    shutil.copyfile(ROOT / "contracts/h2_solubility.yaml", negative)
    naive = check_sources(negative, negative_root)
    if naive["local_files_complete"]:
        raise ValueError("The expected broken-relative-reference control did not fail")

    exported = {}
    for source in sorted((ROOT / "contracts").glob("*.yaml")):
        contract = load_contract(source)
        owner = contract.model.implementation.repository.rsplit("/", 1)[-1]
        destination = output_root / "providers" / owner
        target = export_contract(source, checkouts[owner], destination)
        report = check_sources(target, destination)
        if not report["local_files_complete"]:
            raise ValueError(f"Missing localized evidence: {target}")
        exported[owner + "/mceg/contracts/" + source.name] = {
            "original_contract_sha256": sha256(source),
            "exported_contract_sha256": sha256(target), **report,
        }
    revision = revision_trial(output_root / "providers/exogibbs", output_root)
    result = {
        "record_format": "provider_workflow_trial_v0.1",
        "executed_at_utc": datetime.now(timezone.utc).isoformat(),
        "runner_sha256": sha256(Path(__file__)),
        "candidate_template_sha256": sha256(HERE / "candidate.yaml"),
        "naive_copy": naive, "relocated_contracts": exported, "revision_trial": revision,
        "limitations": [
            "Partial source snapshots only, not installable provider distributions.",
            "File existence and hashes do not check fragments, Python symbols or scientific truth.",
            "Remote URLs and links inside copied Markdown files are not traversed.",
            "Only the baseline's known file prefixes are resolved; free-text citations remain unchecked.",
            "The revision exercise applies a manual review; it does not infer affected claims.",
        ],
    }
    (output_root / "report.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True, help="A new directory outside both providers")
    parser.add_argument("--exoeos", type=Path, default=ROOT.parent / "exoeos")
    parser.add_argument("--exogibbs", type=Path, default=ROOT.parent / "exogibbs")
    args = parser.parse_args()
    checkouts = {"exoeos": args.exoeos.resolve(), "exogibbs": args.exogibbs.resolve()}
    if any(args.output_dir.resolve().is_relative_to(path) for path in checkouts.values()):
        parser.error("Use an output directory outside the provider checkouts")
    report = run(args.output_dir, checkouts)
    print(f"Wrote {args.output_dir}/report.json; five contracts relocated; synthetic review preserved the parent")
