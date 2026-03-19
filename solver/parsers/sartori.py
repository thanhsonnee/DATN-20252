from __future__ import annotations

from typing import Dict, List

from solver.models import Instance, Node, Request


class SartoriParser:
    """
    Parser for Sartori & Buriol PDPTW instances.

    It reads the standard instance format:
    - Header with fields like NAME, SIZE, ROUTE-TIME, CAPACITY
    - NODES section with SIZE lines
    - EDGES section with a SIZE x SIZE travel-time matrix
    """

    def parse(self, path: str) -> Instance:
        with open(path, "r", encoding="utf-8") as handle:
            raw_lines = [line.rstrip("\n") for line in handle]

        # Drop empty lines, keep content as-is otherwise
        lines = [line.strip() for line in raw_lines if line.strip()]

        header: Dict[str, str] = {}
        idx = 0

        # Read header until the NODES marker
        while idx < len(lines) and not lines[idx].upper().startswith("NODES"):
            line = lines[idx]
            if ":" in line:
                key, value = line.split(":", 1)
                header[key.strip().upper()] = value.strip()
            idx += 1

        if idx >= len(lines) or not lines[idx].upper().startswith("NODES"):
            raise ValueError("NODES section not found in instance file.")

        idx += 1  # skip "NODES" line

        try:
            size = int(header["SIZE"])
        except KeyError as exc:
            raise ValueError("Missing SIZE field in instance header.") from exc

        capacity = int(header.get("CAPACITY", "0"))
        horizon = int(header.get("ROUTE-TIME", "0"))
        name = header.get("NAME", path)

        nodes: Dict[int, Node] = {}
        pickup_to_delivery: Dict[int, int] = {}

        # Read NODES section
        for _ in range(size):
            if idx >= len(lines):
                raise ValueError("Unexpected end of file while reading NODES section.")

            parts = lines[idx].split()
            idx += 1

            if len(parts) != 9:
                raise ValueError(f"Expected 9 fields in node line, got {len(parts)}.")

            node_id = int(parts[0])
            lat = float(parts[1])
            lon = float(parts[2])
            demand = int(parts[3])
            etw = int(parts[4])
            ltw = int(parts[5])
            service_duration = int(parts[6])
            p = int(parts[7])
            d = int(parts[8])

            nodes[node_id] = Node(
                id=node_id,
                lat=lat,
                lon=lon,
                demand=demand,
                tw_early=etw,
                tw_late=ltw,
                service_duration=service_duration,
            )

            # p and d encode the pickup-delivery pairing; we only need pickup->delivery
            if d != 0:
                pickup_to_delivery[node_id] = d

        # Advance to EDGES section
        while idx < len(lines) and not lines[idx].upper().startswith("EDGES"):
            idx += 1

        if idx >= len(lines):
            raise ValueError("EDGES section not found in instance file.")

        idx += 1  # skip "EDGES" line

        travel_time: List[List[int]] = []

        for row_idx in range(size):
            if idx >= len(lines):
                raise ValueError("Unexpected end of file while reading EDGES section.")

            parts = lines[idx].split()
            idx += 1

            if len(parts) != size:
                raise ValueError(
                    f"Expected {size} integers in EDGES row {row_idx}, got {len(parts)}."
                )

            travel_time.append([int(x) for x in parts])

        # Build requests based on the pickup->delivery mapping
        requests: List[Request] = []
        for pickup_id, delivery_id in sorted(pickup_to_delivery.items()):
            if pickup_id == 0 or delivery_id == 0:
                # node 0 is the depot; it should not appear in requests
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
            dataset_type="sartori",
            nodes=nodes,
            requests=requests,
            depot_id=0,
            capacity=capacity,
            horizon=horizon,
            travel_time=travel_time,
        )

