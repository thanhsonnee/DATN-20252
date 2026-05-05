from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class Node:
    id: int
    lat: float
    lon: float
    demand: int
    tw_early: int
    tw_late: int
    service_duration: int


@dataclass
class Request:
    id: int
    pickup_node: int
    delivery_node: int
    demand: int


@dataclass
class Route:
    stops: List[int] = field(default_factory=list)
    arrival_times: List[int] = field(default_factory=list)
    start_service_times: List[int] = field(default_factory=list)
    loads: List[int] = field(default_factory=list)

    total_travel_time: int = 0
    total_waiting_time: int = 0

    def copy(self) -> "Route":
        return Route(
            stops=list(self.stops),
            arrival_times=list(self.arrival_times),
            start_service_times=list(self.start_service_times),
            loads=list(self.loads),
            total_travel_time=self.total_travel_time,
            total_waiting_time=self.total_waiting_time,
        )


@dataclass
class Solution:
    routes: List[Route] = field(default_factory=list)
    total_cost: int = 0

    def copy(self) -> "Solution":
        return Solution(routes=[route.copy() for route in self.routes], total_cost=self.total_cost)


@dataclass
class Instance:
    name: str
    dataset_type: str
    nodes: Dict[int, Node]
    requests: List[Request]
    depot_id: int
    capacity: int
    horizon: int
    travel_time: List[List[float]]

    def num_nodes(self) -> int:
        return len(self.nodes)

    def num_requests(self) -> int:
        return len(self.requests)


class InstanceValidationError(ValueError):
    """Raised when an instance fails semantic validation."""

    def __init__(self, errors: List[str]) -> None:
        self.errors = errors
        bullet = "\n  - ".join(errors)
        super().__init__(f"Instance validation failed:\n  - {bullet}")


def validate_instance(instance: Instance) -> List[str]:
    """
    Check semantic correctness of a parsed Instance.
    Returns a list of human-readable error strings (empty = valid).
    """
    errors: List[str] = []

    # 1. Depot must exist
    if instance.depot_id not in instance.nodes:
        errors.append(f"Depot node (id={instance.depot_id}) not found in nodes.")

    # 2. Must have at least one request
    if not instance.requests:
        errors.append("Instance has no requests (no pickup-delivery pairs).")

    # 3. capacity and horizon must be positive
    if instance.capacity <= 0:
        errors.append(f"capacity = {instance.capacity} is invalid (must be > 0).")
    if instance.horizon <= 0:
        errors.append(f"horizon (ROUTE-TIME) = {instance.horizon} is invalid (must be > 0).")

    # 4. Each node: tw_early <= tw_late
    for nid, node in instance.nodes.items():
        if node.tw_early > node.tw_late:
            errors.append(
                f"Node {nid}: tw_early ({node.tw_early}) > tw_late ({node.tw_late})."
            )

    # 5. Each request: pickup and delivery nodes must exist, demand > 0
    node_ids = set(instance.nodes.keys())
    for req in instance.requests:
        if req.pickup_node not in node_ids:
            errors.append(
                f"Request {req.id}: pickup node {req.pickup_node} not found in nodes."
            )
        if req.delivery_node not in node_ids:
            errors.append(
                f"Request {req.id}: delivery node {req.delivery_node} not found in nodes."
            )
        if req.demand <= 0:
            errors.append(
                f"Request {req.id}: demand = {req.demand} is invalid (must be > 0)."
            )

    # 6. travel_time matrix must cover all node ids
    n = len(instance.travel_time)
    for nid in node_ids:
        if nid >= n:
            errors.append(
                f"travel_time matrix size {n}x{n} does not cover node id={nid}."
            )
            break  # one message is enough

    return errors

