"""Compare explicit file pins within a supplied root; never infer scientific support."""

import hashlib
from pathlib import Path
from urllib.parse import urlsplit


def resolve_root(root, assessment_id):
    if root is None:
        return None
    if not assessment_id:
        raise ValueError("--root requires --assessment ID to select the evaluated Subject")
    try:
        root = Path(root).resolve()
    except RuntimeError as exc:
        raise ValueError(str(exc)) from exc
    if not root.is_dir():
        raise ValueError(f"Hash root is not a directory: {root}")
    return root


def check_file(root, source, expected):
    record = {"source": source, "expected_sha256": expected, "actual_sha256": None}

    def outcome(status, message):
        return {**record, "status": status, "message": message}

    try:
        if urlsplit(source).scheme:
            return outcome("UNKNOWN", "URI source is not checked; no source is downloaded")
        if Path(source).is_absolute():
            return outcome("FAIL", "File path must be relative to the supplied root")
        path = (root / source).resolve()
        if not path.is_relative_to(root):
            return outcome("FAIL", "File path resolves outside the supplied root")
        if expected is None:
            return outcome("UNKNOWN", "No SHA-256 recorded; file bytes are not checked")
        if not path.is_file():
            return outcome("FAIL", "File is missing or is not a regular file")
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        record["actual_sha256"] = digest.hexdigest()
    except (OSError, ValueError, RuntimeError) as exc:
        return outcome("FAIL", f"Cannot read file: {exc}")
    if record["actual_sha256"] != expected:
        return outcome("FAIL", "SHA-256 mismatch")
    return outcome("PASS", "SHA-256 matches")


def file_integrity(contract, assessment, evidence_ids, root):
    """Check one Subject and the artifacts in the selected Evidence closure."""
    subject = next(s for s in contract.subjects if s.id == assessment.subject)
    return {
        "root": str(root),
        "subject": subject.id,
        "selected_files": [check_file(root, source, expected)
                           for source, expected in subject.selected_files.items()],
        "artifact_hashes": [
            {"evidence": evidence.id, **check_file(root, artifact.source, artifact.sha256)}
            for evidence in contract.evidence if evidence.id in evidence_ids
            for artifact in evidence.artifacts
        ],
    }
