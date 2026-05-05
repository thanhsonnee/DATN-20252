from __future__ import annotations

import csv
import io
import json
import traceback
from functools import lru_cache
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.deps import require_researcher_or_above
from app.db.models import Algorithm, Route, RouteStop, Solution, User, Job
from app.db.session import get_db
from app.models.schemas import (
    BaselineOut,
    BksEntry,
    DatasetStats,
    MetricResultItem,
    RouteOut,
    RouteStopOut,
    SolutionListItem,
    SolutionListResponse,
    SolutionOut,
)

router = APIRouter(prefix="/solutions", tags=["solutions"])

_REPO_ROOT = Path(__file__).resolve().parents[3]
_BKS_PATH = _REPO_ROOT / "solutions" / "bks.dat"


# ── BKS helpers ───────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def _load_bks() -> dict[str, BksEntry]:
    """Load bks.dat once; returns dict keyed by instance_name."""
    result: dict[str, BksEntry] = {}
    if not _BKS_PATH.exists():
        return result
    with open(_BKS_PATH, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh, delimiter=";")
        for row in reader:
            name = row.get("instance", "").strip()
            try:
                entry = BksEntry(
                    instance_name=name,
                    bks_nv=int(row["vehicles"]),
                    bks_cost=float(row["cost"]),
                    reference=row.get("reference", "").strip(),
                    date=row.get("date", "").strip(),
                )
                result[name] = entry
            except (KeyError, ValueError):
                pass
    return result


def _detect_dataset(instance_name: str) -> str:
    """Heuristic: infer dataset label from instance name prefix."""
    n = instance_name.lower()
    if any(n.startswith(p) for p in ("bar-", "ber-", "poa-", "nyc-")):
        return "sartori"
    if any(n.startswith(p) for p in ("lc", "lrc", "lr", "rc", "c1", "r1", "c2", "r2")):
        return "lilim"
    return "unknown"


# ── Metric computation ─────────────────────────────────────────────────────────

def _compute_metrics(sol: Solution) -> list[MetricResultItem]:
    """Compute built-in metrics for a solution."""
    bks = _load_bks()
    instance_name = sol.job.instance_name if sol.job else ""
    bks_entry = bks.get(instance_name)
    results: list[MetricResultItem] = []

    # NV
    results.append(MetricResultItem(
        metric_name="Số phương tiện (NV)",
        value=float(sol.num_vehicles),
        value_text=str(sol.num_vehicles),
    ))
    # TD
    results.append(MetricResultItem(
        metric_name="Tổng quãng đường (TD)",
        value=round(sol.total_distance, 4),
        value_text=f"{sol.total_distance:.4f}",
    ))
    # Gap NV
    if bks_entry and bks_entry.bks_nv > 0:
        gap_nv = (sol.num_vehicles - bks_entry.bks_nv) / bks_entry.bks_nv * 100
        results.append(MetricResultItem(
            metric_name="Gap NV (%)",
            value=round(gap_nv, 2),
            value_text=f"{gap_nv:+.2f}%",
        ))
    else:
        results.append(MetricResultItem(metric_name="Gap NV (%)", value=None, value_text="N/A"))
    # Gap TD
    if bks_entry and bks_entry.bks_cost > 0:
        gap_td = (sol.total_distance - bks_entry.bks_cost) / bks_entry.bks_cost * 100
        results.append(MetricResultItem(
            metric_name="Gap TD (%)",
            value=round(gap_td, 2),
            value_text=f"{gap_td:+.2f}%",
        ))
    else:
        results.append(MetricResultItem(metric_name="Gap TD (%)", value=None, value_text="N/A"))
    # Improvement
    if sol.init_cost and sol.init_cost > 0:
        improve = (sol.init_cost - sol.total_distance) / sol.init_cost * 100
        results.append(MetricResultItem(
            metric_name="Cải thiện so với nghiệm ban đầu (%)",
            value=round(improve, 2),
            value_text=f"{improve:.2f}%",
        ))
    else:
        results.append(MetricResultItem(metric_name="Cải thiện so với nghiệm ban đầu (%)", value=None, value_text="N/A"))
    # Iterations
    results.append(MetricResultItem(
        metric_name="Số iterations ALNS",
        value=float(sol.iterations) if sol.iterations else None,
        value_text=str(sol.iterations) if sol.iterations else "N/A",
    ))
    # Iter/sec
    if sol.iterations and sol.elapsed_sec and sol.elapsed_sec > 0:
        ips = sol.iterations / sol.elapsed_sec
        results.append(MetricResultItem(
            metric_name="Iterations/giây",
            value=round(ips, 2),
            value_text=f"{ips:.2f}",
        ))
    else:
        results.append(MetricResultItem(metric_name="Iterations/giây", value=None, value_text="N/A"))

    return results


# ── Solution helpers ───────────────────────────────────────────────────────────

def _build_route_out(r: Route) -> RouteOut:
    stops = [
        RouteStopOut(
            position=s.position,
            node_id=s.node_id,
            stop_type=s.stop_type,
            arrival_time=s.arrival_time,
            service_start=s.service_start,
            tw_early=s.tw_early,
            tw_late=s.tw_late,
        )
        for s in r.stops
    ]
    return RouteOut(
        route_index=r.route_index,
        num_stops=len(stops),
        stops=stops,
    )


def _enrich(sol: Solution, include_metrics: bool = False) -> SolutionOut:
    routes = [_build_route_out(r) for r in sol.routes]
    metrics = _compute_metrics(sol) if include_metrics else None
    return SolutionOut(
        id=sol.id,
        job_id=sol.job_id,
        instance_name=sol.job.instance_name if sol.job else "",
        method=sol.job.method if sol.job else "",
        num_vehicles=sol.num_vehicles,
        total_distance=sol.total_distance,
        total_cost=sol.total_cost,
        dataset_type=sol.dataset_type,
        created_at=sol.created_at,
        routes=routes,
        iterations=sol.iterations,
        elapsed_sec=sol.elapsed_sec,
        init_cost=sol.init_cost,
        init_nv=sol.init_nv,
        hostname=sol.hostname,
        os_info=sol.os_info,
        cpu_info=sol.cpu_info,
        ram_gb=sol.ram_gb,
        cpu_usage_pct=sol.cpu_usage_pct,
        metric_results=metrics,
    )


def _load_options():
    return [
        joinedload(Solution.job),
        selectinload(Solution.routes).selectinload(Route.stops),
    ]


def _safe_enrich(sol: Solution, include_metrics: bool = False) -> SolutionOut:
    try:
        return _enrich(sol, include_metrics=include_metrics)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}")


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/bks", response_model=Optional[BksEntry])
def get_bks(
    instance_name: str = Query(...),
    _: User = Depends(require_researcher_or_above),
):
    """Return BKS entry for an instance, or null if not found."""
    bks = _load_bks()
    return bks.get(instance_name)


@router.get("/stats", response_model=list[DatasetStats])
def get_stats(
    db: Session = Depends(get_db),
    _: User = Depends(require_researcher_or_above),
):
    """
    Return aggregated performance stats grouped by (dataset, method).
    Used by the comparison page.
    """
    sols = (
        db.query(Solution)
        .options(joinedload(Solution.job))
        .filter(Solution.job.has(Job.status == "done"))
        .all()
    )
    bks = _load_bks()

    from collections import defaultdict
    groups: dict[tuple[str, str], list[Solution]] = defaultdict(list)
    for sol in sols:
        if not sol.job:
            continue
        ds = _detect_dataset(sol.job.instance_name)
        method = sol.job.method
        groups[(ds, method)].append(sol)

    result: list[DatasetStats] = []
    for (ds, method), group in sorted(groups.items()):
        n = len(group)

        def _avg(values):
            vals = [v for v in values if v is not None]
            return round(sum(vals) / len(vals), 4) if vals else None

        avg_nv = _avg([s.num_vehicles for s in group])
        avg_cost = _avg([s.total_distance for s in group])
        avg_init = _avg([s.init_cost for s in group])

        improve_vals = []
        for s in group:
            if s.init_cost and s.init_cost > 0:
                improve_vals.append((s.init_cost - s.total_distance) / s.init_cost * 100)
        avg_improve = _avg(improve_vals) if improve_vals else None

        gap_nv_vals, gap_cost_vals = [], []
        for s in group:
            entry = bks.get(s.job.instance_name)
            if entry:
                if entry.bks_nv > 0:
                    gap_nv_vals.append((s.num_vehicles - entry.bks_nv) / entry.bks_nv * 100)
                if entry.bks_cost > 0:
                    gap_cost_vals.append((s.total_distance - entry.bks_cost) / entry.bks_cost * 100)

        avg_elapsed = _avg([s.elapsed_sec for s in group])
        avg_iters = _avg([s.iterations for s in group])

        iter_per_sec_vals = []
        for s in group:
            if s.iterations and s.elapsed_sec and s.elapsed_sec > 0:
                iter_per_sec_vals.append(s.iterations / s.elapsed_sec)
        avg_iter_per_sec = _avg(iter_per_sec_vals) if iter_per_sec_vals else None

        result.append(DatasetStats(
            dataset=ds,
            method=method,
            count=n,
            avg_nv=avg_nv or 0,
            avg_cost=avg_cost or 0,
            avg_init_cost=avg_init,
            avg_improve_pct=avg_improve,
            avg_gap_nv_pct=_avg(gap_nv_vals) if gap_nv_vals else None,
            avg_gap_cost_pct=_avg(gap_cost_vals) if gap_cost_vals else None,
            avg_elapsed_sec=avg_elapsed,
            avg_iterations=avg_iters,
            avg_iter_per_sec=avg_iter_per_sec,
        ))

    return result


# ── 35) get_solution_list ──────────────────────────────────────────────────────

@router.get("/", response_model=SolutionListResponse)
def list_solutions(
    job_id: Optional[int] = Query(None),
    instance_name: Optional[str] = Query(None),
    algorithm_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_researcher_or_above),
):
    q = db.query(Solution).join(Solution.job)

    if job_id is not None:
        q = q.filter(Solution.job_id == job_id)
    if instance_name is not None:
        q = q.filter(Job.instance_name == instance_name)
    if algorithm_id is not None:
        q = q.filter(Job.algorithm_id == algorithm_id)

    total = q.count()
    offset = (page - 1) * limit
    sols = q.order_by(Solution.created_at.desc()).offset(offset).limit(limit).all()

    items = [
        SolutionListItem(
            id=s.id,
            job_id=s.job_id,
            num_vehicles=s.num_vehicles,
            total_distance=s.total_distance,
            total_cost=s.total_cost,
            dataset_type=s.dataset_type,
            elapsed_sec=s.elapsed_sec,
            created_at=s.created_at,
        )
        for s in sols
    ]
    return SolutionListResponse(code="SUCCESS", data=items, total=total)


# ── 36) get_solution_detail ────────────────────────────────────────────────────

@router.get("/by-job/{job_id}", response_model=SolutionOut)
def get_solution_by_job(
    job_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_researcher_or_above),
):
    sol = db.query(Solution).options(*_load_options()).filter(Solution.job_id == job_id).first()
    if not sol:
        raise HTTPException(status_code=404, detail="Solution not found for this job")
    return _safe_enrich(sol, include_metrics=True)


@router.get("/{solution_id}", response_model=SolutionOut)
def get_solution(
    solution_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_researcher_or_above),
):
    sol = db.query(Solution).options(*_load_options()).filter(Solution.id == solution_id).first()
    if not sol:
        raise HTTPException(status_code=404, detail="Solution not found")
    return _safe_enrich(sol, include_metrics=True)


# ── 37) get_solution_routes ────────────────────────────────────────────────────

@router.get("/{solution_id}/routes")
def get_solution_routes(
    solution_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_researcher_or_above),
):
    sol = db.query(Solution).options(
        selectinload(Solution.routes).selectinload(Route.stops)
    ).filter(Solution.id == solution_id).first()
    if not sol:
        raise HTTPException(status_code=404, detail="Solution not found")

    routes_out = []
    for r in sol.routes:
        stops_out = [
            {
                "position": s.position,
                "node_id": s.node_id,
                "stop_type": s.stop_type,
                "arrival_time": s.arrival_time,
                "service_start": s.service_start,
                "tw_early": s.tw_early,
                "tw_late": s.tw_late,
            }
            for s in r.stops
        ]
        routes_out.append({
            "route_index": r.route_index,
            "num_stops": len(stops_out),
            "travel_time": None,
            "total_waiting": None,
            "stops": stops_out,
        })

    return {"code": "SUCCESS", "data": routes_out}


# ── 38) export_solution ────────────────────────────────────────────────────────

@router.get("/{solution_id}/export")
def export_solution(
    solution_id: int,
    format: str = Query(..., pattern="^(csv|json)$"),
    db: Session = Depends(get_db),
    _: User = Depends(require_researcher_or_above),
):
    sol = db.query(Solution).options(*_load_options()).filter(Solution.id == solution_id).first()
    if not sol:
        raise HTTPException(status_code=404, detail="Solution not found")

    instance_name = sol.job.instance_name if sol.job else f"solution_{solution_id}"

    if format == "json":
        payload = {
            "solution_id": sol.id,
            "job_id": sol.job_id,
            "instance_name": instance_name,
            "num_vehicles": sol.num_vehicles,
            "total_distance": sol.total_distance,
            "total_cost": sol.total_cost,
            "dataset_type": sol.dataset_type,
            "elapsed_sec": sol.elapsed_sec,
            "created_at": sol.created_at.isoformat(),
            "routes": [
                {
                    "route_index": r.route_index,
                    "stops": [
                        {
                            "position": s.position,
                            "node_id": s.node_id,
                            "stop_type": s.stop_type,
                        }
                        for s in r.stops
                    ],
                }
                for r in sol.routes
            ],
        }
        content = json.dumps(payload, ensure_ascii=False, indent=2)
        filename = f"solution_{solution_id}_{instance_name}.json"
        return StreamingResponse(
            io.BytesIO(content.encode("utf-8")),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    # CSV format
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["solution_id", "job_id", "instance_name", "num_vehicles", "total_distance", "total_cost", "dataset_type"])
    writer.writerow([sol.id, sol.job_id, instance_name, sol.num_vehicles, sol.total_distance, sol.total_cost, sol.dataset_type])
    writer.writerow([])
    writer.writerow(["route_index", "position", "node_id", "stop_type"])
    for r in sol.routes:
        for s in r.stops:
            writer.writerow([r.route_index, s.position, s.node_id, s.stop_type or ""])

    filename = f"solution_{solution_id}_{instance_name}.csv"
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8")),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
