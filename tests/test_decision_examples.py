"""Worked choices preserve uncertainty and the identity of their recorded basis."""

from pathlib import Path

import pytest

from mceg import load_contract
from mceg.schema_v04 import decision_basis_digest


EXAMPLES = Path(__file__).resolve().parents[1] / "examples" / "decisions"


@pytest.mark.parametrize("filename,choice", [
    ("c2h.yaml", "nasa_atct"),
    ("oxygen.yaml", "badro_code"),
])
def test_archived_choices_do_not_promote_unknown_support(filename, choice):
    contract = load_contract(EXAMPLES / filename)
    decision = contract.decisions[0]
    assert decision.selected == choice
    assert decision.limitations and decision.reconsider_when
    assert {assessment.status for assessment in contract.assessments} == {"unknown"}
    assert not any(evidence.kind == "numerical_test" for evidence in contract.evidence)
    for pin in decision.basis:
        assert pin.sha256 == decision_basis_digest(contract, pin.kind, pin.id)
