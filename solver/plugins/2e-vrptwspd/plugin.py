"""
2E-VRPTWSPD plugin — wraps the compiled Java Tabu Search binary.

Converts an Instance2EVRP to the Set2 format expected by the Java solver,
runs the JVM, parses the SUMMARY line, and returns a result dict compatible
with solver_service.py.

Set2 format (readInstanceFileType4):
  Set5_<name>.dat  — coordinates and capacities
  <name>.txt       — per-customer time windows and pickup demands
"""
from __future__ import annotations

import shutil
import subprocess
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from solver.models_2evrp import Instance2EVRP

HERE = Path(__file__).parent


def get_name() -> str:
    return "2E-VRPTWSPD"


def get_description() -> str:
    return "Tabu Search for 2E-VRPTWSPD (Zhou et al. 2022)"


# ---------------------------------------------------------------------------
# Instance conversion helpers
# ---------------------------------------------------------------------------

def _build_customers(instance: "Instance2EVRP") -> list[tuple]:
    """
    Return list of (x, y, del_demand, pu_demand, start_tw, end_tw) tuples.
    Paired requests supply both delivery and pickup demand.
    Unpaired deliveries get pickup_demand=0.
    """
    rows = []
    for req in instance.requests:
        d = req.delivery
        p = req.pickup
        rows.append((
            round(d.x),
            round(d.y),
            max(1, round(d.demand)),        # delivery demand (>= 1)
            max(0, round(p.demand)),         # pickup demand
            round(d.tw_early) if d.tw_early is not None else 0,
            round(d.tw_late)  if d.tw_late  is not None else 10000,
        ))
    for d in instance.unpaired_deliveries:
        rows.append((
            round(d.x),
            round(d.y),
            max(1, round(d.demand)),
            0,
            round(d.tw_early) if d.tw_early is not None else 0,
            round(d.tw_late)  if d.tw_late  is not None else 10000,
        ))
    return rows


def _write_set2_dat(path: Path, cap1e: int, cap2e: int,
                    depot_x: int, depot_y: int,
                    satellites: list, customers: list) -> None:
    """
    Write Set5_<name>.dat in the format expected by readInstanceFileType4.

    Line layout (1-indexed):
      1-2:  skip
      3:    x,<cap1e>,x
      4-5:  skip
      6:    x,x,<cap2e>,x
      7-8:  skip
      9:    depot_x,depot_y  sat_x,sat_y ...   (space-separated groups)
      10-11: skip
      12:   cx,cy,del_demand ...               (space-separated groups)
    """
    sat_line = " ".join(f"{round(s.x)},{round(s.y)}" for s in satellites)
    cust_line = " ".join(f"{c[0]},{c[1]},{c[2]}" for c in customers)
    lines = [
        "skip",
        "skip",
        f"x,{cap1e},x",
        "skip",
        "skip",
        f"x,x,{cap2e},x",
        "skip",
        "skip",
        f"{depot_x},{depot_y} {sat_line}",
        "skip",
        "skip",
        cust_line,
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_set2_txt(path: Path, customers: list) -> None:
    """
    Write <name>.txt: one line per customer — startTW endTW pickup_demand.
    """
    lines = [f"{c[4]} {c[5]} {c[3]}" for c in customers]
    path.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# Output parsing
# ---------------------------------------------------------------------------

def _parse_summary(stdout: str | None):
    if not stdout:
        return None

    for line in stdout.splitlines():
        line = line.strip()
        if not line.startswith("SUMMARY "):
            continue
        try:
            kv = dict(tok.split("=") for tok in line[len("SUMMARY "):].split())
            return {
                "dist":       float(kv["best_dist"]),
                "cost":       float(kv["best_cost"]),
                "nv":         int(kv["best_2e_nv"]),
                "iterations": int(kv["best_iter"]),
                "elapsed":    float(kv["elapsed"]),
                "init_cost":  float(kv["init_cost"]),
                "init_nv":    int(kv["init_2e_nv"]),
            }
        except (KeyError, ValueError):
            continue
    return None


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run(instance, time_limit_sec: float, seed: int, **kwargs):
    from solver.models_2evrp import Instance2EVRP  # type: ignore

    if not isinstance(instance, Instance2EVRP):
        raise TypeError(
            f"2E-VRPTWSPD requires a 2E-VRP instance (Instance2EVRP), "
            f"got {type(instance).__name__}. Select a 2E-VRP dataset."
        )

    customers = _build_customers(instance)
    n_cust = len(customers)
    n_sat = len(instance.satellites)

    if n_cust == 0:
        raise ValueError("Instance has no customers.")
    if n_sat == 0:
        raise ValueError("Instance has no satellites.")

    # Temp instance name: <nCust>-<nSat>-<uid>
    # The first two dash-parts must be integers (readInstanceFileType4 parses them).
    uid = uuid.uuid4().hex[:6]
    temp_name = f"{n_cust}-{n_sat}-{uid}"

    temp_dir = HERE / "input" / "Set2" / temp_name
    out_dir = HERE / "output" / "heuristic" / temp_name
    temp_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        cap1e = int(instance.depot.fe_capacity)
        cap2e = int(instance.depot.se_capacity)
        dep_x = round(instance.depot.x)
        dep_y = round(instance.depot.y)

        _write_set2_dat(
            temp_dir / f"Set5_{temp_name}.dat",
            cap1e, cap2e, dep_x, dep_y,
            instance.satellites, customers,
        )
        _write_set2_txt(temp_dir / f"{temp_name}.txt", customers)

        time_limit_int = max(1, int(time_limit_sec))
        cmd = [
            "java", "-cp", "out",
            "com.zll.Main.Runner",
            temp_name,
            str(seed),
            str(time_limit_int),
        ]
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(HERE),
            timeout=float(time_limit_sec) + 120,
        )

        if proc.returncode != 0:
            stderr = proc.stderr or ""
            stdout = proc.stdout or ""
            raise RuntimeError(
                f"2E-VRPTWSPD Java exited with code {proc.returncode}.\n"
                f"stderr: {stderr[:800]}\n"
                f"stdout: {stdout[:400]}"
            )

        parsed = _parse_summary(proc.stdout)
        if parsed is None:
            stdout = proc.stdout or ""
            raise RuntimeError(
                f"Could not parse SUMMARY line from output.\n"
                f"stdout: {stdout[:1000]}"
            )

        return None, parsed

    finally:
        shutil.rmtree(str(temp_dir), ignore_errors=True)
        shutil.rmtree(str(out_dir), ignore_errors=True)
