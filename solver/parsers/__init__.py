from __future__ import annotations

from solver.models import Instance, InstanceValidationError, validate_instance
from .sartori import SartoriParser
from .lilim import LiLimParser
from .ropke_cordeau import RopkeCordeauParser
from .two_echelon import TwoEchelonParser


def load_instance(path: str, dataset_type: str = "sartori") -> Instance:
    """
    Load an instance file, validate it, and return a normalized Instance object.
    Raises InstanceValidationError if the instance is semantically invalid.
    """
    if dataset_type == "2e_vrp_pdd":
        # Returns Instance2EVRP — not subject to PDPTW validation
        return TwoEchelonParser().parse(path)  # type: ignore[return-value]

    if dataset_type == "sartori":
        instance = SartoriParser().parse(path)
    elif dataset_type == "lilim":
        instance = LiLimParser().parse(path)
    elif dataset_type == "ropke_cordeau":
        instance = RopkeCordeauParser().parse(path)
    else:
        raise ValueError(f"Unsupported dataset type: {dataset_type}")

    errors = validate_instance(instance)
    if errors:
        raise InstanceValidationError(errors)

    return instance

