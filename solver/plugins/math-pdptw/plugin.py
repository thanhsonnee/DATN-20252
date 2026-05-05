"""
math-pdptw plugin — wraps the compiled AGES+LNS binary.

Converts any loaded Instance to Li&Lim format (temp file),
calls the binary, parses the semicolon-delimited table output,
and returns a result dict compatible with solver_service.py.
"""
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from solver.models import Instance


BINARY = Path(__file__).parent / "code" / "math-pdptw.exe"


def get_name() -> str:
    return "math-pdptw"


def get_description() -> str:
    return "Matheuristic AGES+LNS for PDPTW (Sartori & Buriol)"


def _write_umovme(instance: "Instance", path: Path) -> None:
    """Write instance in uMov.me format (Li&Lim with float coords) for the binary.

    The binary uses node IDs as array indices, so nodes must be renumbered:
      0          = depot
      1 .. n     = pickups  (in request order)
      n+1 .. 2n  = deliveries
    """
    nodes = instance.nodes
    depot = nodes[instance.depot_id]
    n = instance.num_requests()
    vcap = instance.capacity

    lines = [f"{n} {vcap} 1.0"]

    # Depot at index 0
    lines.append(
        f"0 {depot.lat} {depot.lon} 0 {depot.tw_early} {depot.tw_late} "
        f"{depot.service_duration} 0 0"
    )

    # All pickups first: indices 1..n
    for idx, req in enumerate(instance.requests, start=1):
        pu = nodes[req.pickup_node]
        de_id = idx + n
        lines.append(
            f"{idx} {pu.lat} {pu.lon} {req.demand} {pu.tw_early} {pu.tw_late} "
            f"{pu.service_duration} 0 {de_id}"
        )

    # All deliveries next: indices n+1..2n
    for idx, req in enumerate(instance.requests, start=1):
        de = nodes[req.delivery_node]
        pu_id = idx
        de_id = idx + n
        lines.append(
            f"{de_id} {de.lat} {de.lon} {-req.demand} {de.tw_early} {de.tw_late} "
            f"{de.service_duration} {pu_id} 0"
        )

    path.write_text("\n".join(lines), encoding="utf-8")


def _parse_table_output(stdout: str):
    """
    Table format (semicolon-separated):
      si_nv ; si_dist ; si_cost ; si_valid ; init_time ;
      sb_nv ; sb_dist ; sb_cost ; sb_valid ; total_time ;
      iter  ; nimp ; ges_reduced ; ges_time ; lns_time ;
      spp_improve ; spp_pool ; spp_time
    """
    for line in stdout.splitlines():
        line = line.strip()
        parts = line.split(";")
        if len(parts) >= 10:
            try:
                return {
                    "init_nv":    int(parts[0]),
                    "init_cost":  float(parts[2]),   # full cost (with vehicle cost)
                    "init_dist":  float(parts[1]),   # dist without vehicle cost
                    "nv":         int(parts[5]),
                    "cost":       float(parts[7]),   # full cost
                    "dist":       float(parts[6]),   # dist without vehicle cost
                    "valid":      int(parts[8]) == 1,
                    "elapsed":    float(parts[9]),
                    "iterations": int(parts[10]),
                }
            except (ValueError, IndexError):
                continue
    return None


class RunResult:
    """Mimics the ALNSResult interface expected by solver_service.py."""
    def __init__(self, solution, iterations: int, elapsed_sec: float):
        self.solution = solution
        self.iterations = iterations
        self.elapsed_sec = elapsed_sec


def run(instance: "Instance", time_limit_sec: float, seed: int, method: str = "greedy", **kwargs):
    """
    Run math-pdptw binary on the given instance.
    Returns a RunResult with .solution, .iterations, .elapsed_sec.
    """
    from solver.models import Solution  # type: ignore

    if not BINARY.exists():
        raise FileNotFoundError(
            f"math-pdptw binary not found at {BINARY}. "
            "Compile it first: cd solver/plugins/math-pdptw/code && make -f Makefile_mingw"
        )

    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w") as tmp:
        tmp_path = Path(tmp.name)

    try:
        _write_umovme(instance, tmp_path)

        cmd = [
            str(BINARY),
            "-i", str(tmp_path),
            "-f", "um",
            "-t", str(float(time_limit_sec)),
            "-s", str(int(seed)),
            "--print", "table",
        ]
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=time_limit_sec + 30,
        )

        if proc.returncode != 0:
            raise RuntimeError(
                f"math-pdptw exited with code {proc.returncode}.\n"
                f"stderr: {proc.stderr[:500]}"
            )

        parsed = _parse_table_output(proc.stdout)
        if parsed is None:
            raise RuntimeError(
                f"Could not parse binary output.\nstdout: {proc.stdout[:500]}"
            )

        # Build a minimal Solution object
        solution = Solution(total_cost=parsed["dist"])

        return RunResult(
            solution=solution,
            iterations=parsed["iterations"],
            elapsed_sec=parsed["elapsed"],
        ), parsed

    finally:
        tmp_path.unlink(missing_ok=True)
