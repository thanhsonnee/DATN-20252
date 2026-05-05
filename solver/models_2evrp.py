"""
Data models for the Two-Echelon Vehicle Routing Problem with
Pickup-Delivery and Deadlines (2E-VRP-PDD).

This is a fundamentally different problem from PDPTW:
- Two vehicle echelons (FE and SE)
- First Echelon (FE): large vehicles, depot → satellites → depot
- Second Echelon (SE): small vehicles, satellite → customers → satellite
- Customers have paired pickup (Type=2) and delivery (Type=3) nodes
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class DepotNode:
    x: float
    y: float
    service_duration: int
    fe_capacity: float   # First Echelon vehicle capacity
    se_capacity: float   # Second Echelon vehicle capacity


@dataclass
class SatelliteNode:
    id: int              # sequential, starting from 1
    x: float
    y: float
    service_duration: int


@dataclass
class CustomerNode:
    id: int              # sequential across all customers
    node_type: str       # "pickup" or "delivery"
    x: float
    y: float
    service_duration: int
    tw_early: Optional[float]   # None if not specified
    tw_late: Optional[float]    # None if not specified
    demand: float
    deadline: Optional[float]   # None if not specified (or 9999)
    pair_id: Optional[int] = None  # id of the paired pickup/delivery node


@dataclass
class Request2E:
    """A pickup-delivery pair in the second echelon."""
    id: int
    pickup: CustomerNode
    delivery: CustomerNode


@dataclass
class Instance2EVRP:
    name: str
    dataset_type: str          # always "2e_vrp_pdd"
    depot: DepotNode
    satellites: List[SatelliteNode]
    customers: List[CustomerNode]
    requests: List[Request2E]  # paired pickup-delivery requests (may be partial)
    unpaired_pickups: List[CustomerNode]   # Type=2 with no matching Type=3
    unpaired_deliveries: List[CustomerNode]  # Type=3 with no matching Type=2

    def num_satellites(self) -> int:
        return len(self.satellites)

    def num_customers(self) -> int:
        return len(self.customers)

    def num_requests(self) -> int:
        return len(self.requests)

    def fe_capacity(self) -> float:
        return self.depot.fe_capacity

    def se_capacity(self) -> float:
        return self.depot.se_capacity
