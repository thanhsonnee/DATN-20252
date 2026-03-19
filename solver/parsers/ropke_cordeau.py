from __future__ import annotations

import math
from typing import Dict, List

from solver.models import Instance, Node, Request


class RopkeCordeauParser:
    """
    Parser for Ropke & Cordeau PDPTW instances (DD, DE, etc.).

    Format summary:
    - Header with fields such as:
        NAME, TYPE, DIMENSION, VEHICLES, CAPACITY, EDGE_WEIGHT_TYPE
    - NODE_COORD_SECTION with DIMENSION lines:
        <id> <x> <y>
    - PICKUP_AND_DELIVERY_SECTION with DIMENSION lines:
        <id> <demand> <e> <l> <service> <pickup> <delivery>
      where positive demand rows (with non-zero 'delivery') are pickups.

    Distances / travel times:
    - EDGE_WEIGHT_TYPE EXACT_2D: Euclidean distance between coordinates.
    """

    def parse(self, path: str) -> Instance:
        with open(path, "r", encoding="utf-8") as handle:
            raw_lines = [line.rstrip("\n") for line in handle]

        lines = [line.strip() for line in raw_lines if line.strip()]

        header: Dict[str, str] = {}
        idx = 0

        # Read header up to NODE_COORD_SECTION
        while idx < len(lines) and not lines[idx].upper().startswith("NODE_COORD_SECTION"):
            line = lines[idx]
            if ":" in line:
                key, value = line.split(":", 1)
                header[key.strip().upper()] = value.strip()
            idx += 1

        if idx >= len(lines) or not lines[idx].upper().startswith("NODE_COORD_SECTION"):
            raise ValueError("NODE_COORD_SECTION not found in Ropke-Cordeau instance.")

        name = header.get("NAME", path)
        capacity = int(header.get("CAPACITY", "0"))
        dimension = int(header.get("DIMENSION", "0"))

        idx += 1  # skip NODE_COORD_SECTION

        # Coordinates
        coords: Dict[int, tuple[float, float]] = {}

        for _ in range(dimension):
            if idx >= len(lines):
                raise ValueError("Unexpected end of file in NODE_COORD_SECTION.")
            parts = lines[idx].split()
            idx += 1
            if len(parts) != 3:
                raise ValueError("Expected 3 fields in NODE_COORD_SECTION line.")
            node_id = int(parts[0])
            x = float(parts[1])
            y = float(parts[2])
            coords[node_id] = (x, y)

        # Move to PICKUP_AND_DELIVERY_SECTION
        while idx < len(lines) and not lines[idx].upper().startswith("PICKUP_AND_DELIVERY_SECTION"):
            idx += 1

        if idx >= len(lines):
            raise ValueError("PICKUP_AND_DELIVERY_SECTION not found in instance.")

        idx += 1  # skip header line

        nodes: Dict[int, Node] = {}
        pickup_to_delivery: Dict[int, int] = {}

        for _ in range(dimension):
            if idx >= len(lines):
                raise ValueError("Unexpected end of file in PICKUP_AND_DELIVERY_SECTION.")

            parts = lines[idx].split()
            idx += 1

            if len(parts) != 7:
                raise ValueError("Expected 7 fields in PICKUP_AND_DELIVERY_SECTION line.")

            node_id = int(parts[0])
            demand = int(parts[1])
            e = int(parts[2])
            l = int(parts[3])
            service = int(parts[4])
            pickup = int(parts[5])
            delivery = int(parts[6])

            if node_id not in coords:
                raise ValueError(f"Coordinates for node {node_id} not found.")

            x, y = coords[node_id]

            nodes[node_id] = Node(
                id=node_id,
                lat=x,
                lon=y,
                demand=demand,
                tw_early=e,
                tw_late=l,
                service_duration=service,
            )

            if delivery != 0 and demand > 0:
                pickup_to_delivery[node_id] = delivery

        # Depot is node 1 in these instances (demand 0)
        depot_id = 1
        if depot_id not in nodes:
            raise ValueError("Depot node (1) not found in Ropke-Cordeau instance.")

        horizon = nodes[depot_id].tw_late

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
                    xi, yi = nodes[i].lat, nodes[i].lon
                    xj, yj = nodes[j].lat, nodes[j].lon
                    travel_time[i][j] = math.hypot(xi - xj, yi - yj)

        requests: List[Request] = []
        for pickup_id, delivery_id in sorted(pickup_to_delivery.items()):
            if pickup_id == depot_id or delivery_id == depot_id:
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

        return Instance(
            name=name,
            dataset_type="ropke_cordeau",
            nodes=nodes,
            requests=requests,
            depot_id=depot_id,
            capacity=capacity,
            horizon=horizon,
            travel_time=travel_time,
        )

