"""Load one YAML contract without executing tags or silently replacing keys."""

from pathlib import Path

import yaml
from yaml.constructor import ConstructorError

from .schema import Contract


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


def load_contract(path: str | Path) -> Contract:
    """Validate structure and local links; do not evaluate scientific conditions."""
    with Path(path).open(encoding="utf-8") as stream:
        data = yaml.load(stream, Loader=_UniqueKeyLoader)
    return Contract.model_validate(data)
