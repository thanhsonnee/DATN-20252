"""
Parser for the Two-Echelon VRP with Pickup-Delivery and Deadlines (2E-VRP-PDD).

CSV format (one row per node):
  Type, X, Y, Service Time, Early, Latest, Demand, Origin/Dest, Deadline, FE Cap, SE Cap

Type meanings:
  0 → Depot  (exactly 1 row; FE Cap and SE Cap are set here)
  1 → Satellite
  2 → Pickup customer node
  3 → Delivery customer node

Pairing strategy:
  Type=2 and Type=3 nodes at identical (X, Y) coordinates are treated as a
  matched pickup-delivery pair.  Nodes with no coordinate match are reported
  as unpaired.
"""
from __future__ import annotations

import csv
import math
from typing import Dict, List, Optional, Tuple

from solver.models_2evrp import (
    CustomerNode,
    DepotNode,
    Instance2EVRP,
    Request2E,
    SatelliteNode,
)


_LARGE_DEADLINE = 9998.0   # values ≥ this are treated as "no deadline"


def _parse_float(val: str) -> Optional[float]:
    v = val.strip()
    if not v:
        return None
    try:
        f = float(v)
        return None if f >= _LARGE_DEADLINE else f
    except ValueError:
        return None


class TwoEchelonParser:
    """Parse a 2E-VRP-PDD CSV instance file into an Instance2EVRP object."""

    def parse(self, path: str) -> Instance2EVRP:
        with open(path, newline="", encoding="utf-8") as fh:
            reader = csv.reader(fh)
            rows = [row for row in reader if any(c.strip() for c in row)]

        if not rows:
            raise ValueError("Empty CSV file.")

        header = [c.strip().lower() for c in rows[0]]
        if "type" not in header:
            raise ValueError(
                "CSV header must contain a 'Type' column. "
                f"Found: {rows[0]}"
            )

        data_rows = rows[1:]

        depot: Optional[DepotNode] = None
        satellites: List[SatelliteNode] = []
        pickups: List[CustomerNode] = []
        deliveries: List[CustomerNode] = []

        sat_counter = 0
        cust_counter = 0

        for row in data_rows:
            if len(row) < 4:
                continue
            try:
                node_type = int(row[0].strip())
            except ValueError:
                continue  # skip malformed lines

            x = float(row[1].strip())
            y = float(row[2].strip())
            svc = int(float(row[3].strip())) if row[3].strip() else 0

            if node_type == 0:
                # Depot — FE Cap at col 9, SE Cap at col 10
                fe_cap = float(row[9].strip()) if len(row) > 9 and row[9].strip() else 0.0
                se_cap = float(row[10].strip()) if len(row) > 10 and row[10].strip() else 0.0
                depot = DepotNode(x=x, y=y, service_duration=svc,
                                  fe_capacity=fe_cap, se_capacity=se_cap)

            elif node_type == 1:
                sat_counter += 1
                satellites.append(SatelliteNode(id=sat_counter, x=x, y=y,
                                                 service_duration=svc))

            elif node_type in (2, 3):
                early = _parse_float(row[4]) if len(row) > 4 else None
                late = _parse_float(row[5]) if len(row) > 5 else None
                demand = float(row[6].strip()) if len(row) > 6 and row[6].strip() else 0.0
                deadline = _parse_float(row[8]) if len(row) > 8 else None

                cust_counter += 1
                node = CustomerNode(
                    id=cust_counter,
                    node_type="pickup" if node_type == 2 else "delivery",
                    x=x, y=y,
                    service_duration=svc,
                    tw_early=early,
                    tw_late=late,
                    demand=demand,
                    deadline=deadline,
                )
                if node_type == 2:
                    pickups.append(node)
                else:
                    deliveries.append(node)

        if depot is None:
            raise ValueError("No depot row (Type=0) found in CSV file.")

        # ── Pair pickups with deliveries by matching (X, Y) coordinates ──
        # Build a dict from coord → delivery node (use first match)
        delivery_by_coord: Dict[Tuple[float, float], CustomerNode] = {}
        for d in deliveries:
            key = (d.x, d.y)
            if key not in delivery_by_coord:
                delivery_by_coord[key] = d

        requests: List[Request2E] = []
        unpaired_pickups: List[CustomerNode] = []
        used_delivery_ids: set[int] = set()

        req_counter = 0
        for p in pickups:
            key = (p.x, p.y)
            d = delivery_by_coord.get(key)
            if d is not None and d.id not in used_delivery_ids:
                p.pair_id = d.id
                d.pair_id = p.id
                used_delivery_ids.add(d.id)
                requests.append(Request2E(id=req_counter, pickup=p, delivery=d))
                req_counter += 1
            else:
                unpaired_pickups.append(p)

        unpaired_deliveries = [d for d in deliveries if d.id not in used_delivery_ids]

        all_customers = pickups + deliveries

        name = path.replace("\\", "/").split("/")[-1]
        if name.lower().endswith(".csv"):
            name = name[:-4]

        return Instance2EVRP(
            name=name,
            dataset_type="2e_vrp_pdd",
            depot=depot,
            satellites=satellites,
            customers=all_customers,
            requests=requests,
            unpaired_pickups=unpaired_pickups,
            unpaired_deliveries=unpaired_deliveries,
        )


def parse_report_2evrp(instance: Instance2EVRP) -> dict:
    """
    Return a human-readable field mapping report dict for use in the web UI.
    Same schema as _build_parse_report() in instances.py.
    """
    F = dict
    fields = [
        # Depot
        F(category="Depot", field="x, y",        status="ok",      source="Type=0, col 1-2", value=f"({instance.depot.x}, {instance.depot.y})", note="Tọa độ depot chính"),
        F(category="Depot", field="service_dur",  status="ok",      source="Type=0, col 3",   value=str(instance.depot.service_duration), note="Thời gian phục vụ tại depot"),
        F(category="Depot", field="fe_capacity",  status="ok",      source="Type=0, col 9",   value=str(instance.depot.fe_capacity), note="Tải trọng xe tầng 1 (FE)"),
        F(category="Depot", field="se_capacity",  status="ok",      source="Type=0, col 10",  value=str(instance.depot.se_capacity), note="Tải trọng xe tầng 2 (SE)"),
        # Satellites
        F(category="Satellite", field="id",       status="derived", source="(đánh số thứ tự)", value="", note="Không có trong file, đánh số theo thứ tự xuất hiện"),
        F(category="Satellite", field="x, y",     status="ok",      source="Type=1, col 1-2", value="", note="Tọa độ trạm trung chuyển"),
        F(category="Satellite", field="service_dur", status="ok",   source="Type=1, col 3",   value="", note="Thời gian dừng tại satellite"),
        # Customer nodes
        F(category="Customer", field="node_type", status="derived", source="col 0 (2→pickup, 3→delivery)", value="", note="Phân loại pickup/delivery theo cột Type"),
        F(category="Customer", field="x, y",      status="ok",      source="col 1-2",         value="", note="Tọa độ khách hàng"),
        F(category="Customer", field="demand",     status="ok",      source="col 6",           value="", note="Khối lượng hàng"),
        F(category="Customer", field="tw_early",   status="ok",      source="col 4",           value="", note="Thời điểm sớm nhất phục vụ (None nếu bỏ trống)"),
        F(category="Customer", field="tw_late",    status="ok",      source="col 5",           value="", note="Thời điểm trễ nhất phục vụ (None nếu bỏ trống)"),
        F(category="Customer", field="deadline",   status="ok",      source="col 8",           value="", note="Deadline giao hàng (bỏ qua nếu ≥ 9999)"),
        F(category="Customer", field="service_dur",status="ok",      source="col 3",           value="", note="Thời gian phục vụ tại node"),
        F(category="Customer", field="pair_id",    status="derived", source="(ghép cặp theo X,Y)", value="", note="Ghép pickup↔delivery theo tọa độ trùng nhau"),
        # Ignored
        F(category="Bỏ qua",  field="Origin/Dest",status="ignored", source="col 7",           value="1.0", note="Luôn là 1.0 trong dataset này, không mã hóa thêm thông tin"),
    ]

    warnings = []
    if instance.unpaired_pickups:
        ids = [str(n.id) for n in instance.unpaired_pickups[:5]]
        s = ", ".join(ids) + ("..." if len(instance.unpaired_pickups) > 5 else "")
        warnings.append(
            f"{len(instance.unpaired_pickups)} pickup node không ghép được cặp delivery "
            f"(không tìm thấy Type=3 cùng tọa độ): node {s}"
        )
    if instance.unpaired_deliveries:
        ids = [str(n.id) for n in instance.unpaired_deliveries[:5]]
        s = ", ".join(ids) + ("..." if len(instance.unpaired_deliveries) > 5 else "")
        warnings.append(
            f"{len(instance.unpaired_deliveries)} delivery node không ghép được cặp pickup "
            f"(không tìm thấy Type=2 cùng tọa độ): node {s}"
        )
    warnings.append(
        "Thuật toán ALNS hiện tại được thiết kế cho PDPTW (1 tầng xe). "
        "Dataset 2E-VRP-PDD có 2 tầng xe — cần thuật toán riêng để giải."
    )

    return {
        "instance_name": instance.name,
        "dataset_type": "2e_vrp_pdd",
        "dataset_type_label": "2E-VRP-PDD",
        "stats": {
            "num_nodes": 1 + instance.num_satellites() + instance.num_customers(),
            "num_satellites": instance.num_satellites(),
            "num_requests": instance.num_requests(),
            "num_unpaired_pickups": len(instance.unpaired_pickups),
            "num_unpaired_deliveries": len(instance.unpaired_deliveries),
            "fe_capacity": instance.depot.fe_capacity,
            "se_capacity": instance.depot.se_capacity,
        },
        "errors": [],
        "warnings": warnings,
        "fields": fields,
    }
