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

