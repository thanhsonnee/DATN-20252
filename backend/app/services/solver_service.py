"""
Wraps the existing ALNS solver for use as a background task.
Reads benchmark instance file, runs construction + ALNS, persists solution to DB.
"""
from __future__ import annotations

import platform
import random
import sys
import os
from datetime import datetime
from pathlib import Path

import psutil
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Job, JobStatus, Route, RouteStop, Solution

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def _collect_env() -> dict:
    """Collect runtime environment info."""
    try:
        mem = psutil.virtual_memory()
        cpu_pct = psutil.cpu_percent(interval=0.2)
        return {
            "hostname": platform.node(),
            "os_info": f"{platform.system()} {platform.release()} ({platform.version()[:60]})",
            "cpu_info": platform.processor() or platform.machine(),
            "ram_gb": round(mem.total / (1024 ** 3), 2),
            "cpu_usage_pct": cpu_pct,
        }
    except Exception:
        return {}


def _detect_dataset_type(path: Path) -> str:
    try:
        lines = [l.strip() for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
        if not lines:
            return "sartori"
        first = lines[0].split()
        # 2E-EVRP: header starts with "StringID"
        if first and first[0].upper() == "STRINGID":
            return "2e_evrp"
        # CSV with TYPE header → 2E-VRP-PDD
        if "," in lines[0] and lines[0].split(",")[0].strip().upper() in ("TYPE", "ID", "NODE"):
            return "2e_vrp_pdd"
        # Li&Lim: first line is all numbers
        if len(first) >= 2 and all(x.lstrip("-").isdigit() for x in first[:2]):
            return "lilim"
        # Ropke-Cordeau
        for line in lines[:30]:
            if line.upper().startswith("NODE_COORD_SECTION"):
                return "ropke_cordeau"
    except Exception:
        pass
    return "sartori"


def _load_instance(instance_name: str):
    from solver.parsers import load_instance  # type: ignore

    instances_dir = Path(settings.INSTANCES_DIR)
    if not instances_dir.is_absolute():
        instances_dir = (_REPO_ROOT / instances_dir).resolve()

    candidates = list(instances_dir.rglob(f"{instance_name}"))
    if not candidates:
        candidates = list(instances_dir.rglob(f"{instance_name}.txt"))
    if not candidates:
        raise FileNotFoundError(f"Instance '{instance_name}' not found in {instances_dir}")
    file_path = candidates[0]
    dataset_type = _detect_dataset_type(file_path)
    return load_instance(str(file_path), dataset_type=dataset_type), dataset_type


def _num_routes(solution) -> int:
    return sum(1 for r in solution.routes if r.stops)


def _get_plugin(algorithm_name: str):
    """Return plugin module if a plugin with that name exists, else None."""
    plugins_dir = _REPO_ROOT / "solver" / "plugins"
    for plugin_dir in plugins_dir.iterdir():
        plugin_file = plugin_dir / "plugin.py"
        if not plugin_file.exists():
            continue
        import importlib.util
        spec = importlib.util.spec_from_file_location(f"plugin_{plugin_dir.name}", plugin_file)
        mod = importlib.util.module_from_spec(spec)  # type: ignore
        spec.loader.exec_module(mod)  # type: ignore
        if hasattr(mod, "get_name") and mod.get_name() == algorithm_name:
            return mod
    return None


def _run_alns(job, instance, dataset_type, env, db):
    from solver.construction import (  # type: ignore
        build_initial_solution_greedy,
        build_initial_solution_regret,
    )
    from solver.alns.runner import run_alns  # type: ignore

    rng = random.Random(job.seed)
    if job.method == "regret":
        initial = build_initial_solution_regret(instance, rng=rng)
    else:
        initial = build_initial_solution_greedy(instance, rng=rng)

    init_cost = initial.total_cost
    init_nv = _num_routes(initial)

    result = run_alns(instance, initial, time_limit_sec=job.time_limit_sec, seed=job.seed)
    solution = result.solution

    non_empty = [r for r in solution.routes if r.stops]
    is_lilim = dataset_type == "lilim"
    sol_row = Solution(
        job_id=job.id,
        num_vehicles=len(non_empty),
        total_distance=solution.total_cost,
        total_cost=None if is_lilim else round(solution.total_cost, 4),
        dataset_type=dataset_type,
        iterations=result.iterations,
        elapsed_sec=round(result.elapsed_sec, 3),
        init_cost=round(init_cost, 3),
        init_nv=init_nv,
        hostname=env.get("hostname"),
        os_info=env.get("os_info"),
        cpu_info=env.get("cpu_info"),
        ram_gb=env.get("ram_gb"),
        cpu_usage_pct=env.get("cpu_usage_pct"),
    )
    db.add(sol_row)
    db.flush()

    for idx, route in enumerate(non_empty, start=1):
        route_row = Route(solution_id=sol_row.id, route_index=idx)
        db.add(route_row)
        db.flush()
        for pos, node in enumerate(route.stops):
            db.add(RouteStop(route_id=route_row.id, position=pos, node_id=node))


def _run_plugin(job, instance, dataset_type, env, plugin, db):
    _result, parsed = plugin.run(
        instance,
        time_limit_sec=job.time_limit_sec,
        seed=job.seed,
        method=job.method,
    )

    is_lilim = dataset_type == "lilim"
    total_dist = round(parsed["dist"], 4)
    total_cost = None if is_lilim else round(parsed["cost"], 4)

    sol_row = Solution(
        job_id=job.id,
        num_vehicles=parsed["nv"],
        total_distance=total_dist,
        total_cost=total_cost,
        dataset_type=dataset_type,
        iterations=parsed["iterations"],
        elapsed_sec=round(parsed["elapsed"], 3),
        init_cost=round(parsed["init_cost"], 3),
        init_nv=parsed["init_nv"],
        hostname=env.get("hostname"),
        os_info=env.get("os_info"),
        cpu_info=env.get("cpu_info"),
        ram_gb=env.get("ram_gb"),
        cpu_usage_pct=env.get("cpu_usage_pct"),
    )
    db.add(sol_row)
    db.flush()
    # Plugin binary doesn't expose per-route stops — store a single empty route as placeholder
    route_row = Route(solution_id=sol_row.id, route_index=1)
    db.add(route_row)
    db.flush()


def run_solver_job(job_id: int, db: Session) -> None:
    job: Job | None = db.query(Job).filter(Job.id == job_id).first()
    if job is None:
        return

    job.status = JobStatus.running
    job.started_at = datetime.utcnow()
    db.commit()

    try:
        env = _collect_env()
        instance, dataset_type = _load_instance(job.instance_name)

        plugin = _get_plugin(job.method) if job.method not in ("greedy", "regret") else None

        if plugin is not None:
            _run_plugin(job, instance, dataset_type, env, plugin, db)
        else:
            _run_alns(job, instance, dataset_type, env, db)

        job.status = JobStatus.done
        job.finished_at = datetime.utcnow()
        db.commit()

    except Exception as exc:
        db.rollback()
        job = db.query(Job).filter(Job.id == job_id).first()
        if job:
            job.status = JobStatus.failed
            job.finished_at = datetime.utcnow()
            job.error_msg = str(exc)
            db.commit()
