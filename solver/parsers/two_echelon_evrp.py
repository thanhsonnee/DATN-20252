"""
Parser for 2E-EVRP (Two-Echelon Electric Vehicle Routing Problem) instances.

Space-separated format with header row:
  StringID  Type  x  y  demand  DeliveryDemand  PickupDemand  DivisionRate  ReadyTime  DueDate  ServiceTime

Type values:
  d → depot (exactly 1)
  s → satellite (intermediate depot)
  f → fuel/charging station
  c → customer

Capacity parameters at end of file (format: "key Description /value/"):
  L → large vehicle (first-echelon) loading capacity
  C → electric vehicle (second-echelon) loading capacity
  Q → electric vehicle battery capacity
  r → fuel consumption rate
  g → inverse refueling rate
  v → average velocity
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class EVRPNode:
    string_id: str
    node_type: str          # 'd', 's', 'f', 'c'
    x: float
    y: float
    demand: float = 0.0
    delivery_demand: float = 0.0
    pickup_demand: float = 0.0
    division_rate: float = 0.0
    ready_time: float = 0.0
    due_date: float = 0.0
    service_time: float = 0.0


@dataclass
class Instance2EEVRP:
    name: str
    depot: Optional[EVRPNode]
    satellites: List[EVRPNode]
    fuel_stations: List[EVRPNode]
    customers: List[EVRPNode]
    # Capacity parameters
    large_vehicle_cap: Optional[float] = None   # L
    ev_load_cap: Optional[float] = None         # C
    ev_battery_cap: Optional[float] = None      # Q
    fuel_consumption_rate: Optional[float] = None   # r
    inverse_refueling_rate: Optional[float] = None  # g
    velocity: Optional[float] = None            # v

    def num_customers(self) -> int:
        return len(self.customers)

    def num_satellites(self) -> int:
        return len(self.satellites)

    def num_fuel_stations(self) -> int:
        return len(self.fuel_stations)

    def total_nodes(self) -> int:
        return 1 + self.num_satellites() + self.num_fuel_stations() + self.num_customers()


_CAP_PATTERN = re.compile(r"/\s*([\d.]+)\s*/")


class TwoEchelonEVRPParser:
    """Parse a 2E-EVRP .txt instance file into an Instance2EEVRP object."""

    def parse(self, path: str) -> Instance2EEVRP:
        with open(path, encoding="utf-8") as fh:
            raw_lines = fh.readlines()

        lines = [ln.rstrip("\n") for ln in raw_lines]
        stripped = [ln.strip() for ln in lines]

        if not stripped:
            raise ValueError("Empty 2E-EVRP file.")

        # Verify header
        header_parts = stripped[0].split()
        if not header_parts or header_parts[0].upper() != "STRINGID":
            raise ValueError(
                f"Expected header starting with 'StringID', got: {stripped[0][:60]}"
            )

        depot: Optional[EVRPNode] = None
        satellites: List[EVRPNode] = []
        fuel_stations: List[EVRPNode] = []
        customers: List[EVRPNode] = []

        # Capacity params
        large_cap: Optional[float] = None
        ev_cap: Optional[float] = None
        ev_bat: Optional[float] = None
        fuel_rate: Optional[float] = None
        refuel_rate: Optional[float] = None
        velocity: Optional[float] = None

        for ln in stripped[1:]:
            if not ln:
                continue
            parts = ln.split()
            if not parts:
                continue

            # Capacity parameter lines (first token is a single letter key)
            if len(parts) >= 1 and len(parts[0]) == 1 and parts[0].isalpha():
                m = _CAP_PATTERN.search(ln)
                if m:
                    val = float(m.group(1))
                    key = parts[0]
                    if key == "L":
                        large_cap = val
                    elif key == "C":
                        ev_cap = val
                    elif key == "Q":
                        ev_bat = val
                    elif key == "r":
                        fuel_rate = val
                    elif key == "g":
                        refuel_rate = val
                    elif key == "v":
                        velocity = val
                    continue

            # Node data lines: need at least StringID + Type + x + y
            if len(parts) < 4:
                continue

            try:
                string_id = parts[0]
                node_type = parts[1].lower()
                x = float(parts[2])
                y = float(parts[3])
            except (ValueError, IndexError):
                continue

            if node_type not in ("d", "s", "f", "c"):
                continue

            node = EVRPNode(
                string_id=string_id,
                node_type=node_type,
                x=x, y=y,
                demand=float(parts[4]) if len(parts) > 4 else 0.0,
                delivery_demand=float(parts[5]) if len(parts) > 5 else 0.0,
                pickup_demand=float(parts[6]) if len(parts) > 6 else 0.0,
                division_rate=float(parts[7]) if len(parts) > 7 else 0.0,
                ready_time=float(parts[8]) if len(parts) > 8 else 0.0,
                due_date=float(parts[9]) if len(parts) > 9 else 0.0,
                service_time=float(parts[10]) if len(parts) > 10 else 0.0,
            )

            if node_type == "d":
                depot = node
            elif node_type == "s":
                satellites.append(node)
            elif node_type == "f":
                fuel_stations.append(node)
            elif node_type == "c":
                customers.append(node)

        if depot is None:
            raise ValueError("No depot node (Type='d') found in 2E-EVRP file.")

        name = path.replace("\\", "/").split("/")[-1]
        if name.lower().endswith(".txt"):
            name = name[:-4]

        return Instance2EEVRP(
            name=name,
            depot=depot,
            satellites=satellites,
            fuel_stations=fuel_stations,
            customers=customers,
            large_vehicle_cap=large_cap,
            ev_load_cap=ev_cap,
            ev_battery_cap=ev_bat,
            fuel_consumption_rate=fuel_rate,
            inverse_refueling_rate=refuel_rate,
            velocity=velocity,
        )


def parse_report_2eevrp(instance: Instance2EEVRP) -> dict:
    """
    Return a structured field-mapping report dict for use in the web UI.
    Same schema as _build_parse_report() in instances.py.
    """
    F = dict

    def _fmt(v: Optional[float]) -> str:
        return str(v) if v is not None else "—"

    sample_cust = instance.customers[0] if instance.customers else None

    fields = [
        # Depot
        F(category="Depot", field="x, y",
          status="ok",      source="Type=d, col 3-4",
          value=f"({instance.depot.x}, {instance.depot.y})" if instance.depot else "",
          note="Tọa độ depot chính (first-echelon)"),
        F(category="Depot", field="large_vehicle_cap (L)",
          status="ok",      source="Dòng 'L ... /value/'",
          value=_fmt(instance.large_vehicle_cap),
          note="Tải trọng xe tầng 1 (xe tải lớn)"),
        F(category="Depot", field="ev_load_cap (C)",
          status="ok",      source="Dòng 'C ... /value/'",
          value=_fmt(instance.ev_load_cap),
          note="Tải trọng xe điện tầng 2"),
        F(category="Depot", field="ev_battery_cap (Q)",
          status="ok",      source="Dòng 'Q ... /value/'",
          value=_fmt(instance.ev_battery_cap),
          note="Dung lượng pin xe điện"),
        # Satellite
        F(category="Satellite", field="x, y",
          status="ok",      source="Type=s, col 3-4",
          value="",         note="Tọa độ trạm trung chuyển (satellite)"),
        F(category="Satellite", field="service_time",
          status="ok",      source="Type=s, col 11",
          value="",         note="Thời gian phục vụ tại satellite"),
        # Fuel station
        F(category="Fuel Station", field="x, y",
          status="ok",      source="Type=f, col 3-4",
          value="",         note="Tọa độ trạm sạc/nạp nhiên liệu"),
        F(category="Fuel Station", field="fuel_rate (r)",
          status="ok",      source="Dòng 'r ... /value/'",
          value=_fmt(instance.fuel_consumption_rate),
          note="Tỷ lệ tiêu hao nhiên liệu"),
        F(category="Fuel Station", field="refuel_rate (g)",
          status="ok",      source="Dòng 'g ... /value/'",
          value=_fmt(instance.inverse_refueling_rate),
          note="Tốc độ nạp nhiên liệu nghịch đảo"),
        # Customer
        F(category="Customer", field="x, y",
          status="ok",      source="Type=c, col 3-4",
          value=f"({sample_cust.x}, {sample_cust.y})" if sample_cust else "",
          note="Tọa độ khách hàng"),
        F(category="Customer", field="demand",
          status="ok",      source="Type=c, col 5",
          value=str(sample_cust.demand) if sample_cust else "",
          note="Tổng nhu cầu (delivery + pickup)"),
        F(category="Customer", field="delivery_demand",
          status="ok",      source="Type=c, col 6",
          value=str(sample_cust.delivery_demand) if sample_cust else "",
          note="Phần nhu cầu giao hàng"),
        F(category="Customer", field="pickup_demand",
          status="ok",      source="Type=c, col 7",
          value=str(sample_cust.pickup_demand) if sample_cust else "",
          note="Phần nhu cầu thu hàng"),
        F(category="Customer", field="division_rate",
          status="ok",      source="Type=c, col 8",
          value=str(sample_cust.division_rate) if sample_cust else "",
          note="Tỷ lệ chia nhỏ nhu cầu (%)"),
        F(category="Customer", field="ready_time",
          status="ok",      source="Type=c, col 9",
          value=str(sample_cust.ready_time) if sample_cust else "",
          note="Thời điểm sớm nhất phục vụ"),
        F(category="Customer", field="due_date",
          status="ok",      source="Type=c, col 10",
          value=str(sample_cust.due_date) if sample_cust else "",
          note="Thời điểm trễ nhất phục vụ"),
        F(category="Customer", field="service_time",
          status="ok",      source="Type=c, col 11",
          value=str(sample_cust.service_time) if sample_cust else "",
          note="Thời gian phục vụ tại node"),
        # Ignored
        F(category="Bỏ qua", field="velocity (v)",
          status="ignored", source="Dòng 'v ... /value/'",
          value=_fmt(instance.velocity),
          note="Không dùng trong solver hiện tại"),
    ]

    warnings = [
        "Dataset 2E-EVRP sử dụng xe điện (EV) — không phải PDPTW thông thường. "
        "Thuật toán ALNS hiện tại chưa hỗ trợ mô hình này.",
        "Mỗi khách hàng có cả DeliveryDemand và PickupDemand (không phải cặp pickup-delivery như PDPTW).",
    ]

    return {
        "instance_name": instance.name,
        "dataset_type": "2e_evrp",
        "dataset_type_label": "2E-EVRP",
        "stats": {
            "num_nodes": instance.total_nodes(),
            "num_requests": instance.num_customers(),
            "num_satellites": instance.num_satellites(),
            "num_fuel_stations": instance.num_fuel_stations(),
            "large_vehicle_cap": instance.large_vehicle_cap,
            "ev_load_cap": instance.ev_load_cap,
        },
        "errors": [],
        "warnings": warnings,
        "fields": fields,
    }
