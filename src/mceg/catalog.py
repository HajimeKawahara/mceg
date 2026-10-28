"""Read provider-owned evidence catalogs without importing provider packages."""

import hashlib
from importlib import metadata
import json
import os
from pathlib import Path
import re
import shutil
import sys
from typing import Literal

from pydantic import Field, model_validator

from ._display import wrap
from .integrity import check_file
from .schema import Text
from .schema_v02 import ContractV02, Digest, Record
from .validator import load_contract


class CatalogSpecies(Record):
    id: Text
    aliases: list[Text] = Field(default_factory=list)


class CatalogArtifact(Record):
    path: Text
    sha256: Digest


class CatalogRecord(CatalogArtifact):
    id: Text
    species: list[Text] = Field(min_length=1)
    assessments: list[Text] = Field(default_factory=list)
    summary: Text | None = None
    links: list[Text] = Field(default_factory=list)
    artifacts: list[CatalogArtifact] = Field(default_factory=list)


class CatalogModel(Record):
    id: Text
    label: Text
    dataset: Text | None = None
    identity: dict = Field(default_factory=dict)
    species: list[CatalogSpecies]
    records: list[CatalogRecord]

    @model_validator(mode="after")
    def check_references(self):
        identifiers = [s.id for s in self.species]
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("Duplicate species IDs")
        aliases = {}
        for species in self.species:
            for name in [species.id, *species.aliases]:
                if name in aliases and aliases[name] != species.id:
                    raise ValueError(f"Ambiguous species alias: {name}")
                aliases[name] = species.id
        if len({r.id for r in self.records}) != len(self.records):
            raise ValueError("Duplicate record IDs")
        for record in self.records:
            if set(record.species) - set(identifiers) - {"*"}:
                raise ValueError(f"Unknown species in record {record.id}")
        return self


class Catalog(Record):
    schema_version: Literal["1"]
    provider: Text
    record_version: Text
    models: list[CatalogModel] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_models(self):
        if len({m.id for m in self.models}) != len(self.models):
            raise ValueError("Duplicate model IDs")
        return self


def package_catalog(package: str) -> tuple[Path, dict]:
    """Locate an installed distribution's data, never import its modules."""
    try:
        distribution = metadata.distribution(package)
    except metadata.PackageNotFoundError as exc:
        raise ValueError(f"Package {package!r} is not installed; use --catalog PATH for a checkout") from exc
    paths = [p for p in distribution.files or []
             if str(p).replace("\\", "/").endswith("/mceg/index.json")]
    if len(paths) != 1:
        raise ValueError(f"Expected one packaged mceg/index.json in {package!r}, found {len(paths)}; "
                         "use --catalog PATH for a checkout or editable install")
    return Path(distribution.locate_file(paths[0])), {
        "name": distribution.metadata["Name"], "version": distribution.version,
    }


def _normalized_distribution(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _checked_path(root: Path, artifact: CatalogArtifact) -> tuple[Path, dict]:
    check = check_file(root, artifact.path, artifact.sha256)
    if check["status"] != "PASS":
        raise ValueError(f"Catalog artifact {artifact.path}: {check['message']}")
    return root / artifact.path, check


def record_report(root: Path, record: CatalogRecord) -> dict:
    """Expose recorded judgments in their original scope, not a new assessment."""
    # Reuse the existing explain readers so claim and follow-up semantics stay shared.
    from .explain import apply_resolutions, assessment_detail, claim_detail, command

    path, contract_check = _checked_path(root, record)
    artifact_checks = [_checked_path(root, artifact)[1] for artifact in record.artifacts]
    contract = load_contract(path)
    selected = []
    if isinstance(contract, ContractV02):
        by_id = {a.id: a for a in contract.assessments}
        for key in record.assessments:
            if key not in by_id:
                raise ValueError(f"Unknown assessment {key!r} in catalog record {record.id}")
            selected.append(by_id[key])
    elif record.assessments:
        raise ValueError(f"v0.1 catalog record {record.id} cannot select assessments")
    claims = []
    for claim in contract.claims:
        item = claim_detail(contract, path, claim)
        if isinstance(contract, ContractV02):
            item["assessments"] = [a.model_dump() for a in selected
                                   if a.kind == "evidence_support"
                                   and (a.claim, a.claim_revision) == (claim.id, claim.revision)]
            # Catalog navigation selects only authored assessments; it never picks a latest ID.
            item["next_commands"] = [command(path, "--assessment", a["id"])
                                     for a in item["assessments"]]
        apply_resolutions(contract, path, item)
        claims.append(item)
    assessments = []
    for assessment in selected:
        item = assessment_detail(contract, path, assessment)
        apply_resolutions(contract, path, item)
        assessments.append(item)
    resolutions = {r.follow_up: r.model_dump() for r in getattr(contract, "follow_up_resolutions", [])}
    follow_ups = [{"record": f.model_dump(), "resolution": resolutions.get(f.id)}
                  for f in getattr(contract, "follow_ups", [])]
    return {
        "id": record.id, "path": str(path), "contract_model": contract.model.id,
        "summary": record.summary or contract.model.description, "links": record.links,
        "relevance": record.species, "packaged_files": [contract_check, *artifact_checks],
        "scientific_files": "not_checked", "domains": [d.model_dump() for d in contract.domains],
        "claims": claims, "assessments": assessments,
        "evidence": [e.model_dump(exclude_none=True) for e in contract.evidence],
        "limitations": [s.model_dump() for s in contract.limitations], "follow_ups": follow_ups,
    }


def explain_catalog(*, package: str | None = None, catalog: Path | None = None,
                    model: str | None = None, species: str | None = None) -> dict:
    """Find relevant recorded evidence; no user's run is evaluated here."""
    distribution = None
    if package is not None:
        if catalog is not None:
            raise ValueError("Choose --package or --catalog")
        catalog, distribution = package_catalog(package)
    if catalog is None:
        raise ValueError("Provide --package or --catalog")
    catalog = Path(catalog).resolve()
    payload = catalog.read_bytes()
    # model_validate_json enforces strict records while accepting JSON objects/lists.
    index = Catalog.model_validate_json(payload)
    if distribution and _normalized_distribution(index.provider) != _normalized_distribution(distribution["name"]):
        raise ValueError("Catalog provider does not match the selected distribution")
    models = index.models if model is None else [m for m in index.models if m.id == model]
    if not models:
        raise ValueError(f"Unknown model {model!r}; available: " + ", ".join(m.id for m in index.models))
    selections = []
    for candidate in models:
        canonical = None
        if species is not None:
            canonical = next((s.id for s in candidate.species if species in [s.id, *s.aliases]), None)
        records = [r for r in candidate.records if species is None
                   or (canonical is not None and (canonical in r.species or "*" in r.species))]
        if canonical is not None:
            records.sort(key=lambda record: canonical not in record.species)
        specific = [r.id for r in records if canonical is not None and canonical in r.species]
        selections.append({
            "id": candidate.id, "label": candidate.label, "dataset": candidate.dataset,
            "declared_identity": candidate.identity, "identity_verification": "not_performed",
            "requested_species": species, "canonical_species": canonical,
            "species_specific_records": specific,
            "records": [record_report(catalog.parent, record) for record in records],
        })
    return {
        "format": "mceg_catalog_explanation_v1", "catalog": str(catalog),
        "catalog_sha256": hashlib.sha256(payload).hexdigest(), "provider": index.provider,
        "record_version": index.record_version, "distribution": distribution,
        "user_conditions": "not_evaluated", "models": selections,
        "interpretation": ("Recorded evidence only. Packaged file hashes do not establish model identity "
                           "for a user's run, physical accuracy or a calibrated uncertainty distribution. "
                           "Scientific input/output files are not checked or rerun. No relevant record "
                           "means missing assessment coverage, not absence of uncertainty."),
    }


def display_catalog(report: dict, lang: str = "en", plain: bool = False) -> None:
    """Present model selection, scoped judgments and unresolved work together."""
    from .explain import command

    terminal = not plain and sys.stdout.isatty()
    color = terminal and not os.environ.get("NO_COLOR") and os.environ.get("TERM") != "dumb"
    width = max(40, shutil.get_terminal_size().columns)

    def label(en, ja):
        return ja if lang == "ja" else en

    def write(text, indent="", code=None, literal=False):
        text = indent + text
        if terminal and not literal:
            text = wrap(text, width, indent, lang)
        if color and code:
            text = f"\033[{code}m{text}\033[0m"
        print(text)

    write(f"{report['provider']} — {label('evidence snapshot', '評価記録の版')}: {report['record_version']}", code="1")
    write(f"{label('Catalog SHA-256', '索引 SHA-256')}: {report['catalog_sha256']}", code="2")
    write(label("Your conditions: not evaluated; recorded findings retain their original scope.",
                "使用条件: 未評価。以下は記録された条件における評価です。"), code="33")
    for model in report["models"]:
        print()
        write(f"{model['id']}: {model['label']}", code="1;36")
        write(label("Declared model identity (your run not verified): ", "宣言されたモデル識別情報（実行との一致は未検証）: ")
              + json.dumps(model["declared_identity"], ensure_ascii=False, sort_keys=True), code="2")
        if model["requested_species"] is not None:
            write(f"{label('Species', '化学種')}: {model['requested_species']} -> {model['canonical_species'] or 'unknown'}")
            if not model["species_specific_records"]:
                write(label("No species-specific records; this does not establish absence of uncertainty.",
                            "分子固有の評価記録なし。不定性がないことを示すものではありません。"), code="33")
        if not model["records"]:
            write(label("No relevant records.", "関連する評価記録なし。"), code="33")
        for record in model["records"]:
            print()
            if terminal:
                write(record["id"], "  ", "1;36")
                write(record["summary"], "    ")
            else:
                write(f"{record['id']}: {record['summary']}", "  ")
            for claim in record["claims"]:
                value = claim["record"]
                statuses = [a.get("status", a.get("classification")) for a in claim["assessments"]]
                status = ", ".join(statuses) if statuses else value.get("status", "unknown (no selected assessment)")
                supported = all(s == "supported" for s in (statuses or [value.get("status")]))
                write(f"{value['kind']} / {claim['id']}: {status}", "    ", "1;32" if supported else "1;33")
                write(f"{label('Claim', '主張')}: {value['statement']}", "      ")
                write(f"{label('Scope', '評価範囲')}: {value['scope']}", "      ")
                commands = [command(record["path"], "--assessment", a["id"])
                            for a in claim["assessments"]]
                if not commands:
                    commands = [command(record["path"], "--claim", claim["id"])]
                for next_command in commands:
                    # Preserve a single physical line for copyable commands and links.
                    write(f"{label('Inspect', '詳細')}: {next_command}", "      ", "36", literal=True)
            for limitation in record["limitations"]:
                write(f"{label('Limitation', '制約')}: {limitation['statement']}", "    ", "33")
            for follow_up in record["follow_ups"]:
                status = "completed" if follow_up["resolution"] else "open"
                write(f"{label('Follow-up', '追跡事項')} [{status}]: {follow_up['record']['action']}",
                      "    ", "36" if follow_up["resolution"] else "33")
            for link in record["links"]:
                write(link, "    ", "36", literal=True)
    print()
    write(label(report["interpretation"],
                      "同梱ファイルのハッシュ一致は、実行モデルの一致、物理的精度、誤差分布を保証しません。"
                      "科学計算の入出力ファイルは検査・再実行していません。"), code="33")
