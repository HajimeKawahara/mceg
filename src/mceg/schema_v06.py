"""Version 0.6 equations with an optional authoritative SymPy definition."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_serializer, model_validator

from .schema import Text
from .schema_v03 import Equation as EquationV03
from .schema_v05 import ContractV05
from .symbolic import SympySource, symbolic_names, to_sympy


class Equation(EquationV03):
    """SymPy is authoritative when supplied; otherwise LaTeX remains authoritative."""

    latex: Text | None = None
    sympy: SympySource | None = None

    @model_validator(mode="after")
    def check_definition(self):
        if self.sympy is None:
            if self.latex is None:
                raise ValueError("An Equation needs a SymPy definition or LaTeX")
            return self
        expression = to_sympy(self.sympy)
        undeclared = symbolic_names(expression) - self.symbols.keys()
        if undeclared:
            raise ValueError("Undeclared SymPy symbols or functions: " + ", ".join(sorted(undeclared)))
        return self

    @model_serializer(mode="wrap")
    def serialize_authoritative_definition(self, handler):
        data = handler(self)
        if self.sympy is None:
            data.pop("sympy", None)
        else:
            # A supplied legacy display string is not another source of truth.
            # Both canonical hashes and serialized contracts use the chosen source.
            data.pop("latex", None)
        return data


class ContractV06(ContractV05):
    schema_version: Literal["0.6"]
    equations: list[Equation] = Field(default_factory=list)
