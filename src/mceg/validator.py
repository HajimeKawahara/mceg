"""Load one YAML contract without executing tags or silently replacing keys."""

from pathlib import Path
import json

import yaml
from yaml.constructor import ConstructorError

from .schema import Contract
from .schema_v02 import ContractV02


class _UniqueKeyLoader(yaml.SafeLoader):
    def construct_mapping(self, node, deep=False):
        self.flatten_mapping(node)
        keys = set()
        for key_node, _ in node.value:
            key = self.construct_object(key_node, deep=deep)
            try:
                duplicate = key in keys
                keys.add(key)
            except TypeError as exc:
                raise ConstructorError(
                    None, None, "Mapping keys must be hashable", key_node.start_mark
                ) from exc
            if duplicate:
                raise ConstructorError(
                    None, None, f"Duplicate mapping key: {key!r}", key_node.start_mark
                )
        return super().construct_mapping(node, deep=deep)


def read_document(path: str | Path):
    """Read YAML or JSON with the same safe duplicate-key policy."""
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate mapping key: {key!r}")
            result[key] = value
        return result

    text = Path(path).read_text(encoding="utf-8")
    if Path(path).suffix == ".json" or text.lstrip().startswith(("{", "[")):
        try:
            return json.loads(text, object_pairs_hook=unique_object)
        except json.JSONDecodeError:
            if Path(path).suffix == ".json":
                raise
    return yaml.load(text, Loader=_UniqueKeyLoader)


def load_contract(path: str | Path) -> Contract | ContractV02:
    """Dispatch explicitly by version; validate structure, not scientific truth."""
    data = read_document(path)
    if isinstance(data, dict) and data.get("schema_version") == "0.2":
        return ContractV02.model_validate(data)
    return Contract.model_validate(data)
