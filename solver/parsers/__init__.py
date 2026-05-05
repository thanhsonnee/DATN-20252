from __future__ import annotations

from solver.models import Instance
from .sartori import SartoriParser
from .lilim import LiLimParser
from .ropke_cordeau import RopkeCordeauParser


def load_instance(path: str, dataset_type: str = "sartori") -> Instance:
    """
    Load an instance file and return a normalized Instance object.

    Currently only the Sartori/Buriol instances are supported. Additional
    dataset types (e.g., Li & Lim, Ropke & Cordeau) can be added later.
    """
    if dataset_type == "sartori":
        return SartoriParser().parse(path)
    if dataset_type == "lilim":
        return LiLimParser().parse(path)
    if dataset_type == "ropke_cordeau":
        return RopkeCordeauParser().parse(path)

    raise ValueError(f"Unsupported dataset type: {dataset_type}")

