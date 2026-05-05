"""
Metric plugin management.
- System metrics seeded at startup (NV, TD, Gap%, etc.), cannot be deleted/edited.
- metric_provider role can upload custom Python metric plugins.
- Plugin interface: get_name() -> str, get_description() -> str,
  compute(solution, instance, **kwargs) -> float
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

from fastapi import APIRouter, Body, Depends, Form, HTTPException, UploadFile, File, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_metric_provider
from app.db.session import get_db
from app.db.models import Metric, User
from app.db.session import get_db
from app.models.schemas import MetricOut

router = APIRouter(prefix="/metrics", tags=["metrics"])

_REPO_ROOT = Path(__file__).resolve().parents[3]
_METRIC_PLUGINS_DIR = _REPO_ROOT / "solver" / "metric_plugins"
_REQUIRED_FUNCTIONS = {"get_name", "get_description", "compute"}

_SYSTEM_METRICS = [
    # ── Common (both datasets) ─────────────────────────────────────────────────
    ("Number of Vehicles (NV)", "Number of vehicles used in the optimal solution. Primary criterion — fewer vehicles is always better regardless of cost."),
    ("Gap NV (%)", "Vehicle count deviation from Best Known Solution (BKS). Gap(%) = (NV - BKS_NV) / BKS_NV × 100"),
    ("Best (instances)", "Number of instances where the solution equals or improves on the BKS, out of the total run."),
    ("CPU Time (s)", "Algorithm runtime in seconds from start to final solution."),
    ("ALNS Iterations", "Total number of destroy-repair-evaluate iterations performed within the time limit."),
    ("Iterations/second", "Average processing speed: number of iterations per second."),
    # ── Li&Lim dataset ─────────────────────────────────────────────────────────
    ("Total Distance (TD)", "Total travel distance across all routes. Applies to Li&Lim dataset where travel time equals Euclidean distance (tij = dij)."),
    ("Gap TD (%)", "Total distance deviation from BKS (Li&Lim). Gap(%) = (TD - BKS_TD) / BKS_TD × 100"),
    ("Improvement TD (%)", "Percentage improvement in Total Distance from initial to final solution (Li&Lim dataset)."),
    # ── Sartori & Buriol dataset ───────────────────────────────────────────────
    ("Total Cost", "Total travel cost across all routes. Applies to Sartori & Buriol dataset where cost is based on actual road travel time (OSRM routing), not Euclidean distance."),
    ("Gap Cost (%)", "Total cost deviation from BKS (Sartori). Gap(%) = (Cost - BKS_Cost) / BKS_Cost × 100"),
    ("Improvement Cost (%)", "Percentage improvement in Total Cost from initial to final solution (Sartori & Buriol dataset)."),
]


def _ensure_system_metrics(db: Session) -> None:
    expected_names = {name for name, _ in _SYSTEM_METRICS}
    # Remove stale system metrics (old names / renamed)
    stale = db.query(Metric).filter(Metric.is_system == True, ~Metric.name.in_(expected_names)).all()
    for m in stale:
        db.delete(m)
    # Upsert: update description if exists, insert if not
    for name, desc in _SYSTEM_METRICS:
        existing = db.query(Metric).filter(Metric.name == name).first()
        if existing:
            existing.description = desc
        else:
            db.add(Metric(name=name, description=desc, is_system=True, filename=None, uploaded_by_id=None))
    db.commit()


def _validate_plugin(code: str) -> list[str]:
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        raise HTTPException(status_code=400, detail=f"Syntax error: {e}")
    defined = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
    }
    return list(_REQUIRED_FUNCTIONS - defined)


def _can_access_metric(metric: Metric, current: User) -> bool:
    from app.db.models import UserRole
    if current.role == UserRole.admin:
        return True
    if metric.is_system:
        return True
    if metric.visibility == "public":
        return True
    if metric.visibility == "private":
        return metric.uploaded_by_id == current.id
    if metric.visibility == "shared":
        if metric.uploaded_by_id == current.id:
            return True
        try:
            ids = json.loads(metric.shared_with_ids or "[]")
            return current.id in ids
        except Exception:
            return False
    return False


@router.get("/", response_model=list[MetricOut])
def list_metrics(
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    _ensure_system_metrics(db)
    all_metrics = db.query(Metric).order_by(Metric.is_system.desc(), Metric.created_at.asc()).all()
    return [m for m in all_metrics if _can_access_metric(m, current)]


@router.post("/upload", response_model=MetricOut, status_code=status.HTTP_201_CREATED)
async def upload_metric(
    file: UploadFile = File(...),
    visibility: str = Form(default="public"),
    shared_with_emails: str = Form(default="[]"),
    db: Session = Depends(get_db),
    current: User = Depends(require_metric_provider),
):
    if not file.filename or not file.filename.endswith(".py"):
        raise HTTPException(status_code=400, detail="Chỉ chấp nhận file .py")

    code = (await file.read()).decode("utf-8", errors="replace")

    missing = _validate_plugin(code)
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Plugin thiếu các hàm bắt buộc: {', '.join(sorted(missing))}. "
                   f"Cần có: get_name(), get_description(), compute(solution, instance, **kwargs)",
        )

    plugin_name: str | None = None
    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "get_name":
                for stmt in node.body:
                    if isinstance(stmt, ast.Return) and isinstance(stmt.value, ast.Constant):
                        plugin_name = str(stmt.value.value)
                        break
    except Exception:
        pass

    if not plugin_name:
        plugin_name = Path(file.filename).stem

    if db.query(Metric).filter(Metric.name == plugin_name).first():
        raise HTTPException(status_code=400, detail=f"Độ đo '{plugin_name}' đã tồn tại")

    if visibility not in ("public", "private", "shared"):
        visibility = "public"
    try:
        emails = json.loads(shared_with_emails)
        if not isinstance(emails, list):
            emails = []
    except Exception:
        emails = []
    from app.db.models import User as UserModel
    shared_with_ids_list = []
    for email in emails:
        u = db.query(UserModel).filter(UserModel.email == email).first()
        if u:
            shared_with_ids_list.append(u.id)

    _METRIC_PLUGINS_DIR.mkdir(parents=True, exist_ok=True)
    safe_filename = f"{plugin_name.lower().replace(' ', '_')}.py"
    dest = _METRIC_PLUGINS_DIR / safe_filename
    dest.write_text(code, encoding="utf-8")

    metric = Metric(
        name=plugin_name,
        description=None,
        is_system=False,
        filename=safe_filename,
        uploaded_by_id=current.id,
        visibility=visibility,
        shared_with_ids=json.dumps(shared_with_ids_list) if shared_with_ids_list else None,
    )
    db.add(metric)
    db.commit()
    db.refresh(metric)
    return metric


@router.get("/{metric_id}", response_model=MetricOut)
def get_metric(
    metric_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    _ensure_system_metrics(db)
    metric = db.query(Metric).filter(Metric.id == metric_id).first()
    if not metric:
        raise HTTPException(status_code=404, detail="Không tìm thấy độ đo")
    if not _can_access_metric(metric, current):
        raise HTTPException(status_code=403, detail="Bạn không có quyền xem độ đo này")
    return metric


@router.patch("/{metric_id}/visibility", response_model=MetricOut)
def update_metric_visibility(
    metric_id: int,
    visibility: str = Body(...),
    shared_with_emails: list[str] = Body(default=[]),
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    from app.db.models import UserRole
    from app.db.models import User as UserModel

    allowed = {UserRole.admin, UserRole.metric_provider}
    if current.role not in allowed:
        raise HTTPException(status_code=403, detail="Forbidden")
    if visibility not in ("public", "private", "shared"):
        raise HTTPException(status_code=400, detail="visibility phải là public, private hoặc shared")

    metric = db.query(Metric).filter(Metric.id == metric_id).first()
    if not metric:
        raise HTTPException(status_code=404, detail="Không tìm thấy độ đo")
    if metric.is_system:
        raise HTTPException(status_code=403, detail="Không thể thay đổi quyền độ đo hệ thống")
    if current.role != UserRole.admin and metric.uploaded_by_id != current.id:
        raise HTTPException(status_code=403, detail="Bạn không có quyền thay đổi quyền độ đo này")

    # Resolve emails → IDs
    shared_with_ids: list[int] = []
    for email in shared_with_emails:
        u = db.query(UserModel).filter(UserModel.email == email).first()
        if u:
            shared_with_ids.append(u.id)

    metric.visibility = visibility
    metric.shared_with_ids = json.dumps(shared_with_ids) if shared_with_ids else None
    db.commit()
    db.refresh(metric)
    return metric


@router.delete("/{metric_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_metric(
    metric_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(require_metric_provider),
):
    from app.db.models import UserRole
    metric = db.query(Metric).filter(Metric.id == metric_id).first()
    if not metric:
        raise HTTPException(status_code=404, detail="Không tìm thấy độ đo")
    if metric.is_system:
        raise HTTPException(status_code=403, detail="Không thể xóa độ đo hệ thống")
    if current.role != UserRole.admin and metric.uploaded_by_id != current.id:
        raise HTTPException(status_code=403, detail="Bạn không có quyền xóa độ đo này")

    if metric.filename:
        plugin_file = _METRIC_PLUGINS_DIR / metric.filename
        if plugin_file.exists():
            plugin_file.unlink()

    db.delete(metric)
    db.commit()
