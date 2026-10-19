"""Rebuild the v0.2 H2 example from the pinned, previously reviewed v0.1 records."""

import hashlib
from pathlib import Path

from mceg import assess_conditions, migrate_contract
from mceg.migration import write_document
from mceg.schema_v02 import Context, ContractV02
from mceg.validator import read_document


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def build():
    source = ROOT / "contracts/h2_solubility.yaml"
    conditions_path = ROOT / "examples/h2_solubility/conditions.yaml"
    reviewed = read_document(conditions_path)
    if hashlib.sha256(source.read_bytes()).hexdigest() != reviewed["contract_sha256"]:
        raise ValueError("The H2 condition review must be updated before rebuilding this example")
    data = migrate_contract(source).model_dump()
    revision = "sha256:" + hashlib.sha256(conditions_path.read_bytes()).hexdigest()
    data["conditions"] = [{**c, "kind": "range", "revision": revision} for c in reviewed["conditions"]]
    doi = "https://doi.org/10.1016/j.epsl.2012.06.031"
    data["follow_ups"] = [
        {"id": "inspect-original-fit", "target_kind": "evidence", "target": "experimental_fit",
         "action": "Obtain Hirschmann et al. (2012) full text and inspect the fit underlying Seo Eq. 6.",
         "requires": ["Authorized full text and supporting equations/tables. The stored audit reports HTTP 403 and an authenticated full-text API; institutional library access or an author copy may be needed."],
         "completion": "Record the original fit, concentration basis, reference state and unit/temperature transformations leading to -11.403 and 0.76. Compare the inspected scope with Seo Eq. 6; preserve unknown if the derivation remains unresolved.",
         "sources": [doi]},
        {"id": "inspect-original-runs", "target_kind": "evidence", "target": "experimental_temperature",
         "action": "Inspect the original basalt and andesite run tables separately.",
         "requires": ["Hirschmann et al. (2012) full text and run tables, with material and buffer labels."],
         "completion": "Record the basalt-specific temperatures and compare the selected run inventory with Seo's interval. Do not combine material-specific upper bounds without supporting evidence.",
         "sources": [doi]},
        {"id": "define-physical-comparison", "target_kind": "claim", "target": "physical_accuracy",
         "revision": data["claims"][2]["revision"],
         "action": "Define a physical accuracy proposition for the intended melt and calculation conditions.",
         "requires": ["An observable and tolerance, melt composition, redox/fugacity conditions, and relevant independent measurement data."],
         "completion": "Create an explicit Claim revision with these criteria, record the measured comparison as Evidence, and assess that revision. Reading a paper or passing a range check alone does not establish physical accuracy.",
         "sources": []},
    ]
    return assess_conditions(ContractV02.model_validate(data),
                             Context.model_validate(read_document(HERE / "h2_context.json")), "imported")


if __name__ == "__main__":
    write_document(build().model_dump(exclude_none=True, exclude_defaults=True), HERE / "h2_solubility.yaml")
