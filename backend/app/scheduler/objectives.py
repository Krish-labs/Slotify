from typing import Any

from ortools.sat.python import cp_model


class ObjectiveBuilder:
    def __init__(self, model: cp_model.CpModel):
        self.model = model
        self.terms: list[Any] = []

    def add_term(self, expr, weight: int = 1):
        self.terms.append(expr * weight)

    def build(self):
        if self.terms:
            self.model.Minimize(sum(self.terms))
