from __future__ import annotations

import math
from typing import Dict, List

from solver.models import Instance, Node, Request


class LiLimParser:
    """
    Parser for Li & Lim PDPTW instances (e.g., pdptw800).

    Format summary:
    - First line: <num_vehicles> <capacity> <speed>
    - Then one line per node:
      <id> <x> <y> <demand> <e> <l> <service> <pickup> <delivery>

    Distances / travel times:
    - Travel time between i and j is the Euclidean distance between coordinates.
    """

    def parse(self, path: str) -> Instance:
        with open(path, "r", encoding="utf-8") as handle:
            lines = [line.strip() for line in handle if line.strip()]

        if not lines:
            raise ValueError("Empty Li & Lim instance file.")

        # Header line
        header_parts = lines[0].split()
        if len(header_parts) < 2:
            raise ValueError("Invalid header in Li & Lim instance file.")

        # num_vehicles is header_parts[0], which we do not need here
        capacity = int(header_parts[1])

        nodes: Dict[int, Node] = {}
        pickup_to_delivery: Dict[int, int] = {}

        # Node lines
        for line in lines[1:]:
            parts = line.split()
            if len(parts) != 9:
                raise ValueError(f"Expected 9 fields in node line, got {len(parts)}.")

            node_id = int(parts[0])
            x = float(parts[1])
            y = float(parts[2])
            demand = int(parts[3])
            e = int(parts[4])
            l = int(parts[5])
            service = int(parts[6])
            p = int(parts[7])
            d = int(parts[8])

            nodes[node_id] = Node(
                id=node_id,
                lat=x,
                lon=y,
                demand=demand,
                tw_early=e,
                tw_late=l,
                service_duration=service,
            )

            if d != 0:
                pickup_to_delivery[node_id] = d

        if 0 not in nodes:
            raise ValueError("Depot (node 0) not found in Li & Lim instance.")

        # Horizon: use depot latest time window as an upper bound
        horizon = nodes[0].tw_late

        # Build Euclidean travel time matrix
        max_id = max(nodes.keys())
        size = max_id + 1

        travel_time: List[List[float]] = [[0.0] * size for _ in range(size)]

        for i in range(size):
            if i not in nodes:
                continue
            for j in range(size):
                if j not in nodes:
                    continue
                if i == j:
                    travel_time[i][j] = 0.0
                else:
                    dx = nodes[i].lat - nodes[j].lat
                    dy = nodes[i].lon - nodes[j].lon
                    travel_time[i][j] = math.hypot(dx, dy)

        requests: List[Request] = []
        for pickup_id, delivery_id in sorted(pickup_to_delivery.items()):
            if pickup_id == 0 or delivery_id == 0:
                continue

            request_id = len(requests)
            demand = abs(nodes[pickup_id].demand)

            requests.append(
                Request(
                    id=request_id,
                    pickup_node=pickup_id,
                    delivery_node=delivery_id,
                    demand=demand,
                )
            )

        name = path.split("/")[-1].split("\\")[-1]

        return Instance(
            name=name,
            dataset_type="lilim",
            nodes=nodes,
            requests=requests,
            depot_id=0,
            capacity=capacity,
            horizon=horizon,
            travel_time=travel_time,
        )

