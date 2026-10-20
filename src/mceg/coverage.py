"""Check an authored model inventory against source files and provider contracts.

This is registration and review coverage, not scientific or test coverage.
Provider code is parsed, never imported. Model boundaries remain human decisions.
"""

import argparse
import ast
import hashlib
import json
from pathlib import Path, PurePosixPath
import sys
from typing import Annotated, Literal

from pydantic import AfterValidator, Field, model_validator
import yaml

from .schema import Text
from .schema_v02 import Digest, Record
from .validator import load_contract, read_document


def _relative(value: str) -> str:
    path = PurePosixPath(value)
    if (path.is_absolute() or path.as_posix() != value or value == "."
            or ".." in path.parts or "\\" in value or ":" in value):
        raise ValueError("Use a normalized relative POSIX path without '..' or a URI")
    return value


LocalPath = Annotated[Text, AfterValidator(_relative)]


class FileReview(Record):
    sha256: Digest
    role: Literal["model", "support"]
    note: Text


class Binding(Record):
    path: LocalPath
    symbol: Text | None = None
    settings: dict[Text, Text | int | float | bool] = Field(default_factory=dict)


class ContractLink(Record):
    path: LocalPath
    model_id: Text


class InventoryModel(Record):
    id: Text
    description: Text
    bindings: list[Binding] = Field(min_length=1)
    contracts: list[ContractLink] = Field(default_factory=list)


class Inventory(Record):
    inventory_version: Literal["0.1"]
    scope: Text
    source_roots: list[LocalPath] = Field(min_length=1)
    contract_roots: list[LocalPath] = Field(min_length=1)
    files: dict[LocalPath, FileReview]
    models: list[InventoryModel]

    @model_validator(mode="after")
    def unique_ids(self):
        ids = [model.id for model in self.models]
        if len(ids) != len(set(ids)):
            raise ValueError("Inventory model IDs must be unique")
        return self


def _local(root: Path, relative: str) -> Path:
    """Reject symlinks, including intermediate directories, without reading targets."""
    path = root
    for part in PurePosixPath(relative).parts:
        path = path / part
        if path.is_symlink():
            raise ValueError("Symlinks are not inspected; use a local regular file")
    return path


def _in_scope(path: str, roots: list[str]) -> bool:
    return any(path == base or path.startswith(base + "/") for base in roots)


def _symbols(source: bytes, filename: str) -> set[str]:
    names = set()

    def visit(node, parents=()):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                qualified = (*parents, child.name)
                names.add(".".join(qualified))
                visit(child, qualified)
            else:
                visit(child, parents)

    visit(ast.parse(source, filename=filename))
    return names


def check_coverage(root: str | Path, inventory: Inventory) -> dict:
    """Return deterministic gaps within explicit scan roots; never refresh pins."""
    root = Path(root).resolve()
    if not root.is_dir():
        raise ValueError(f"Provider root is not a directory: {root}")
    issues = []

    def issue(kind, path, message, model=None):
        issues.append({"kind": kind, "path": path, "model": model, "message": message})

    def scan(roots, kind):
        found = set()
        visited = set()

        def visit(relative):
            if relative in visited:
                return
            visited.add(relative)
            try:
                path = _local(root, relative)
                if path.is_dir():
                    for child in sorted(path.iterdir()):
                        if child.name == "__pycache__" or child.suffix in {".pyc", ".pyo"}:
                            continue
                        visit(child.relative_to(root).as_posix())
                elif path.is_file():
                    found.add(relative)
                else:
                    raise ValueError("Missing path or not a regular file/directory")
            except (OSError, ValueError) as exc:
                issue(kind, relative, str(exc))

        for relative in sorted(roots):
            visit(relative)
        return found

    sources = scan(inventory.source_roots, "source_scan_error")
    contracts = {path for path in scan(inventory.contract_roots, "contract_scan_error")
                 if Path(path).suffix.lower() in {".yaml", ".yml", ".json"}}
    file_results = {}
    symbols = {}
    for path in sorted(sources | inventory.files.keys()):
        review = inventory.files.get(path)
        result = {"path": path, "status": "current", "role": review.role if review else None,
                  "expected": review.sha256 if review else None, "actual": None}
        before = len(issues)
        if not _in_scope(path, inventory.source_roots):
            issue("file_outside_scope", path, "Reviewed file is outside source_roots")
        elif path not in sources:
            issue("missing_source", path, "Reviewed file was not found as a regular source file")
        else:
            try:
                data = _local(root, path).read_bytes()
                result["actual"] = hashlib.sha256(data).hexdigest()
                if review is None:
                    issue("unreviewed_file", path, "Classify this file and review its model bindings")
                elif result["actual"] != review.sha256:
                    issue("changed_file", path, "Review changed code/data and affected model boundaries")
                if path.endswith(".py"):
                    symbols[path] = _symbols(data, path)
            except (OSError, ValueError, SyntaxError) as exc:
                issue("unreadable_source", path, str(exc))
        if len(issues) != before:
            result["status"] = "needs_review"
        file_results[path] = result

    # Validate even unlisted contracts so removing a mapping cannot hide a record.
    links = {link.path for model in inventory.models for link in model.contracts}
    contract_ids = {}
    for path in sorted(contracts | links):
        try:
            if not _in_scope(path, inventory.contract_roots):
                raise ValueError("Contract link is outside contract_roots")
            contract_ids[path] = load_contract(_local(root, path)).model.id
        except (OSError, ValueError, yaml.YAMLError) as exc:
            issue("invalid_contract", path, str(exc))
        if path in contracts and path not in links:
            issue("unlisted_contract", path, "Add this contract to the model inventory")

    models = []
    bound_files = set()
    for model in inventory.models:
        source_status = "current"
        for binding in model.bindings:
            bound_files.add(binding.path)
            review = inventory.files.get(binding.path)
            if review is None or review.role != "model":
                issue("unreviewed_binding", binding.path,
                      "Model binding needs a file review with role 'model'", model.id)
                source_status = "needs_review"
            if file_results.get(binding.path, {}).get("status") != "current":
                source_status = "needs_review"
            if binding.symbol and binding.symbol not in symbols.get(binding.path, set()):
                issue("missing_symbol", binding.path,
                      f"No local Python definition for {binding.symbol}", model.id)
                source_status = "needs_review"
        registration = "registered" if model.contracts else "uncontracted"
        if not model.contracts:
            issue("uncontracted_model", None, "No contract is linked to this model", model.id)
        for link in model.contracts:
            actual = contract_ids.get(link.path)
            if actual != link.model_id:
                registration = "invalid"
                issue("contract_mismatch", link.path,
                      f"Expected model.id {link.model_id!r}; found {actual!r}", model.id)
        models.append({"id": model.id, "registration": registration,
                       "source_status": source_status,
                       "bindings": [binding.model_dump(exclude_none=True) for binding in model.bindings],
                       "contracts": [link.model_dump() for link in model.contracts]})

    for path, review in sorted(inventory.files.items()):
        if review.role == "model" and path not in bound_files:
            issue("unbound_model_file", path, "No inventory model refers to this model file")
    issues.sort(key=lambda item: (item["kind"], item["path"] or "", item["model"] or ""))
    return {
        "status": "gaps" if issues else "complete",
        "scope": inventory.scope,
        "source_roots": inventory.source_roots,
        "contract_roots": inventory.contract_roots,
        "summary": {
            "source_files": len(sources),
            "current_files": sum(item["status"] == "current" for item in file_results.values()),
            "files_needing_review": sum(item["status"] != "current" for item in file_results.values()),
            "models": len(models),
            "registered_models": sum(item["registration"] == "registered" for item in models),
            "uncontracted_models": sum(item["registration"] == "uncontracted" for item in models),
            "invalid_models": sum(item["registration"] == "invalid" for item in models),
            "discovered_contracts": len(contracts),
            "issues": len(issues),
        },
        "files": list(file_results.values()),
        "models": models,
        "issues": issues,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="mceg coverage",
        description="Check model registration and source-review coverage without importing providers.",
        epilog="Exit codes: 0 complete within declared scope, 1 gaps, 2 invalid input. "
               "Coverage does not establish scientific validity or infer every implicit model.",
    )
    parser.add_argument("root", nargs="?", type=Path, default=Path.cwd(), help="Provider root (default: cwd)")
    parser.add_argument("--inventory", default="mceg/models.yaml", help="Inventory path relative to root")
    parser.add_argument("--json", action="store_true", help="Emit the full JSON report")
    args = parser.parse_args(argv)
    try:
        path = _local(args.root.resolve(), _relative(args.inventory))
        inventory = Inventory.model_validate(read_document(path))
        report = check_coverage(args.root, inventory)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        print(f"INVALID inventory: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        summary = report["summary"]
        print(f"Coverage: {report['status'].upper()} (registration and review only)")
        print(f"Scope: {inventory.scope}")
        print(f"Sources: {summary['current_files']} current, "
              f"{summary['files_needing_review']} need review")
        print(f"Models: {summary['registered_models']} registered, "
              f"{summary['uncontracted_models']} uncontracted, {summary['invalid_models']} invalid")
        for item in report["issues"]:
            location = ": ".join(filter(None, [item["model"], item["path"]]))
            print(f"  {item['kind']} {location}: {item['message']}")
    return int(report["status"] != "complete")
