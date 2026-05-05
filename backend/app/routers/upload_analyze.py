"""
Two-step upload flow with LLM analysis:

  POST /upload-analyze/dataset    → analyze, save to _pending/, return temp_id + analysis
  POST /upload-analyze/algorithm  → same for algorithm source code
  POST /upload-analyze/metric     → same for metric plugin

  POST /upload-analyze/confirm    → move _pending/ → official dir, persist to DB
  DELETE /upload-analyze/reject/{temp_id} → delete temp files
"""
from __future__ import annotations

import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_current_user
from app.db.session import get_db
from app.db.models import User
import logging
from app.services.gemini_analysis import analyze as gemini_analyze

_log = logging.getLogger(__name__)

router = APIRouter(prefix="/upload-analyze", tags=["upload-analyze"])

_REPO_ROOT = Path(__file__).resolve().parents[3]
_INSTANCE_EXTS = {".txt", ".pdptw", ".csv"}


# ── helpers ────────────────────────────────────────────────────────────────────

def _instances_dir() -> Path:
    p = Path(settings.INSTANCES_DIR)
    if not p.is_absolute():
        p = (_REPO_ROOT / p).resolve()
    return p


def _plugins_dir() -> Path:
    return _REPO_ROOT / "solver" / "plugins"


def _metrics_dir() -> Path:
    return _REPO_ROOT / "solver" / "metric_plugins"


def _pending_dir(kind: str) -> Path:
    mapping = {
        "dataset": _instances_dir() / "_pending",
        "algorithm": _plugins_dir() / "_pending",
        "metric": _metrics_dir() / "_pending",
    }
    d = mapping[kind]
    d.mkdir(parents=True, exist_ok=True)
    return d


def _pending_meta_path(kind: str, temp_id: str) -> Path:
    return _pending_dir(kind) / f"{temp_id}.meta.json"


def _read_pending_meta(kind: str, temp_id: str) -> dict:
    p = _pending_meta_path(kind, temp_id)
    if not p.exists():
        raise HTTPException(status_code=404, detail="Pending upload not found hoặc đã hết hạn")
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        raise HTTPException(status_code=500, detail="Lỗi đọc pending metadata")


def _decode_text(content: bytes, filename: str) -> str:
    for enc in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return content.decode(enc)
        except Exception:
            continue
    return content.decode("utf-8", errors="replace")


# ── dataset analyze ────────────────────────────────────────────────────────────

@router.post("/dataset")
async def analyze_dataset(
    files: List[UploadFile] = File(...),
    visibility: str = Form(default="public"),
    shared_with_emails: str = Form(default="[]"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.db.models import UserRole
    from app.db.models import User as UserModel
    from app.routers.instances import _compute_fingerprint, _find_duplicate, _instances_dir as _idir

    allowed = {UserRole.admin, UserRole.algo_tester, UserRole.dataset_provider}
    if current_user.role not in allowed:
        raise HTTPException(status_code=403, detail="Forbidden")

    base = _idir()
    temp_id = str(uuid.uuid4())
    pending = _pending_dir("dataset") / temp_id
    pending.mkdir(parents=True)

    content_map: dict[str, str] = {}  # only 1 representative file for LLM
    file_entries: list[dict] = []

    for file in files:
        raw = Path(file.filename or "unknown")
        parts = [p for p in raw.parts if p not in ("", ".", "..") and p != "/"]
        if not parts:
            continue
        rel = Path(*parts)
        if rel.suffix not in _INSTANCE_EXTS:
            continue

        content = await file.read()

        # Duplicate check
        fp = _compute_fingerprint(content)
        dup = _find_duplicate(fp, base)
        if dup:
            shutil.rmtree(pending, ignore_errors=True)
            raise HTTPException(
                status_code=409,
                detail=f"File '{rel.name}' trùng nội dung với instance đã có: {dup}",
            )

        # Save to pending (preserve folder structure)
        dest = pending / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(content)

        # Only feed the first valid file to LLM — all files in a folder share the same format
        if not content_map:
            text = _decode_text(content, str(rel))
            content_map[str(rel)] = text[:8_000]

        file_entries.append({
            "filename": str(rel),
            "rel_path": rel.as_posix(),
            "fingerprint": fp,
        })

    if not file_entries:
        shutil.rmtree(pending, ignore_errors=True)
        raise HTTPException(status_code=400, detail="Không có file dataset hợp lệ")

    # Call OpenAI (best-effort — fallback to empty form if API unavailable)
    llm_available = True
    try:
        analysis = gemini_analyze(content_map, "dataset")
    except Exception as exc:
        _log.error("LLM analysis (dataset) failed: %s", exc, exc_info=True)
        llm_available = False
        analysis = {
            "problem_variant": "",
            "description": "",
            "hard_constraints": [],
            "soft_constraints": [],
            "dataset_format": "",
            "reference_papers": [],
        }

    # Parse shared_with emails
    try:
        emails = json.loads(shared_with_emails)
        if not isinstance(emails, list):
            emails = []
    except Exception:
        emails = []
    from app.db.models import User as UserModel
    shared_with_ids = []
    for email in emails:
        u = db.query(UserModel).filter(UserModel.email == email).first()
        if u:
            shared_with_ids.append(u.id)

    # Save pending metadata
    meta = {
        "kind": "dataset",
        "temp_id": temp_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "uploader_id": current_user.id,
        "uploader_name": current_user.full_name,
        "uploader_email": current_user.email,
        "visibility": visibility,
        "shared_with_ids": shared_with_ids,
        "files": file_entries,
        "analysis": analysis,
    }
    _pending_meta_path("dataset", temp_id).write_text(
        json.dumps(meta, ensure_ascii=False), encoding="utf-8"
    )

    return {"temp_id": temp_id, "analysis": analysis, "files": [f["filename"] for f in file_entries], "llm_available": llm_available}


# ── algorithm analyze ──────────────────────────────────────────────────────────

@router.post("/algorithm")
async def analyze_algorithm(
    files: List[UploadFile] = File(...),
    current_user: User = Depends(get_current_user),
):
    from app.db.models import UserRole
    allowed = {UserRole.admin, UserRole.algo_tester}
    if current_user.role not in allowed:
        raise HTTPException(status_code=403, detail="Forbidden")

    temp_id = str(uuid.uuid4())
    pending = _pending_dir("algorithm") / temp_id
    pending.mkdir(parents=True)

    content_map: dict[str, str] = {}
    file_entries: list[dict] = []

    for file in files:
        if not file.filename:
            continue
        rel = file.filename.replace("\\", "/")
        parts = rel.split("/")
        if any(p.startswith(".") for p in parts):
            continue

        # Non-admin users may only upload a single .py file (no folder structure)
        from app.db.models import UserRole as _UserRole
        is_folder_upload = len(parts) > 1 or len(files) > 1
        if is_folder_upload and current_user.role != _UserRole.admin:
            shutil.rmtree(pending, ignore_errors=True)
            raise HTTPException(
                status_code=403,
                detail="Chỉ admin mới được upload thư mục thuật toán. User chỉ được upload 1 file .py.",
            )

        content = await file.read()
        # Preserve folder structure in pending
        dest = pending / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(content)
        text = _decode_text(content, rel)
        content_map[rel] = text[:8_000]
        file_entries.append({"filename": rel})

    if not file_entries:
        shutil.rmtree(pending, ignore_errors=True)
        raise HTTPException(status_code=400, detail="Không có file hợp lệ")

    # Exclude auto-generated plugin.py stub from LLM — it has no real content.
    # Prefer README / actual source files so LLM can identify the variant correctly.
    llm_content_map = {k: v for k, v in content_map.items() if not k.endswith("plugin.py")}
    if not llm_content_map:
        llm_content_map = content_map  # fallback: plugin.py is the only file

    llm_available = True
    try:
        analysis = gemini_analyze(llm_content_map, "algorithm")
    except Exception as exc:
        _log.error("LLM analysis (algorithm) failed: %s", exc, exc_info=True)
        llm_available = False
        analysis = {
            "problem_variant": "",
            "description": "",
            "hard_constraints": [],
            "soft_constraints": [],
            "dataset_format": "N/A",
            "reference_papers": [],
        }

    meta = {
        "kind": "algorithm",
        "temp_id": temp_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "uploader_id": current_user.id,
        "uploader_name": current_user.full_name,
        "uploader_email": current_user.email,
        "files": file_entries,
        "analysis": analysis,
    }
    _pending_meta_path("algorithm", temp_id).write_text(
        json.dumps(meta, ensure_ascii=False), encoding="utf-8"
    )

    return {"temp_id": temp_id, "analysis": analysis, "files": [f["filename"] for f in file_entries], "llm_available": llm_available}


# ── metric analyze ─────────────────────────────────────────────────────────────

@router.post("/metric")
async def analyze_metric(
    file: UploadFile = File(...),
    visibility: str = Form(default="public"),
    shared_with_emails: str = Form(default="[]"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.db.models import UserRole
    allowed = {UserRole.admin, UserRole.metric_provider}
    if current_user.role not in allowed:
        raise HTTPException(status_code=403, detail="Forbidden")

    content = await file.read()
    text = _decode_text(content, file.filename or "metric.py")

    temp_id = str(uuid.uuid4())
    pending = _pending_dir("metric") / temp_id
    pending.mkdir(parents=True)
    dest = pending / (file.filename or "metric.py")
    dest.write_bytes(content)

    llm_available = True
    try:
        analysis = gemini_analyze({file.filename or "metric.py": text[:8_000]}, "metric")
    except Exception as exc:
        _log.error("LLM analysis (metric) failed: %s", exc, exc_info=True)
        llm_available = False
        analysis = {
            "problem_variant": "",
            "description": "",
            "hard_constraints": [],
            "soft_constraints": [],
            "dataset_format": "N/A",
            "reference_papers": [],
        }

    try:
        emails = json.loads(shared_with_emails)
        if not isinstance(emails, list):
            emails = []
    except Exception:
        emails = []
    from app.db.models import User as UserModel
    shared_with_ids = []
    for email in emails:
        u = db.query(UserModel).filter(UserModel.email == email).first()
        if u:
            shared_with_ids.append(u.id)

    meta = {
        "kind": "metric",
        "temp_id": temp_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "uploader_id": current_user.id,
        "uploader_name": current_user.full_name,
        "uploader_email": current_user.email,
        "filename": file.filename,
        "visibility": visibility,
        "shared_with_ids": shared_with_ids,
        "analysis": analysis,
    }
    _pending_meta_path("metric", temp_id).write_text(
        json.dumps(meta, ensure_ascii=False), encoding="utf-8"
    )

    return {"temp_id": temp_id, "analysis": analysis, "llm_available": llm_available}


# ── confirm ────────────────────────────────────────────────────────────────────

@router.post("/confirm")
async def confirm_upload(
    body: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    body: { temp_id, kind, analysis (user-edited) }
    Moves pending files to official directory and persists analysis.
    """
    temp_id = body.get("temp_id")
    kind = body.get("kind")
    analysis = body.get("analysis", {})

    if kind not in ("dataset", "algorithm", "metric"):
        raise HTTPException(status_code=400, detail="kind phải là dataset / algorithm / metric")

    meta = _read_pending_meta(kind, temp_id)
    if meta.get("uploader_id") != current_user.id:
        raise HTTPException(status_code=403, detail="Không có quyền confirm upload này")

    pending_dir = _pending_dir(kind) / temp_id

    vrp_variant = body.get("vrp_variant")
    selected_metrics = body.get("selected_metrics")
    flow_steps = body.get("flow_steps")

    if kind == "dataset":
        _confirm_dataset(meta, analysis, pending_dir, db)
    elif kind == "algorithm":
        _confirm_algorithm(meta, analysis, pending_dir, db, vrp_variant=vrp_variant, selected_metrics=selected_metrics, flow_steps=flow_steps, current_user=current_user)
    elif kind == "metric":
        _confirm_metric(meta, analysis, pending_dir, db)

    # Cleanup pending
    shutil.rmtree(pending_dir, ignore_errors=True)
    _pending_meta_path(kind, temp_id).unlink(missing_ok=True)

    return {"status": "confirmed", "kind": kind}


def _confirm_dataset(meta: dict, analysis: dict, pending_dir: Path, db: Session):
    from app.routers.instances import _write_meta, _instances_dir as _idir, _parse_header

    base = _idir()
    for entry in meta.get("files", []):
        src = pending_dir / entry["rel_path"]
        if not src.exists():
            continue
        dest = base / entry["rel_path"]
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dest))
        fp = entry.get("fingerprint")
        _write_meta(
            dest,
            meta["uploader_id"],
            meta["uploader_name"],
            meta["uploader_email"],
            meta.get("visibility", "public"),
            meta.get("shared_with_ids", []),
            fingerprint=fp,
        )
        # Persist analysis alongside meta
        analysis_path = dest.with_suffix(dest.suffix + ".analysis.json")
        analysis_path.write_text(json.dumps(analysis, ensure_ascii=False), encoding="utf-8")


def _run_verify_job(job_id: int) -> None:
    """Module-level target for multiprocessing.Process — must be picklable on Windows."""
    from app.db.session import SessionLocal
    from app.services.solver_service import run_solver_job
    db = SessionLocal()
    try:
        run_solver_job(job_id, db)
    finally:
        db.close()


_VARIANT_DATASET_FOLDERS: dict[str, list[str]] = {
    "PDPTW":  ["lilim-dataset", "ropke-cordeau-dataset", "sartori-dataset"],
    "2E-VRP": ["2E-EVRP-Instances-2", "2e-vrp-pdd-main"],
}


def _find_smallest_instance(vrp_variant: str) -> str | None:
    """Return the name of the smallest instance file that matches the variant's dataset folders."""
    instances_dir = _instances_dir()
    folders = _VARIANT_DATASET_FOLDERS.get(vrp_variant, [])
    best: tuple[int, str] | None = None
    instance_exts = {".txt", ".pdptw", ".csv"}
    for folder_name in folders:
        folder = instances_dir / folder_name
        if not folder.exists():
            continue
        for f in folder.rglob("*"):
            if f.suffix in instance_exts and f.is_file():
                size = f.stat().st_size
                if best is None or size < best[0]:
                    best = (size, f.name)
    return best[1] if best else None


def _confirm_algorithm(meta: dict, analysis: dict, pending_dir: Path, db: Session,
                        vrp_variant: str | None = None, selected_metrics: str | None = None,
                        flow_steps: str | None = None, current_user: "User | None" = None):
    import multiprocessing
    from app.routers.algorithms_api import _PLUGINS_DIR, _validate_plugin, _extract_plugin_name
    from app.db.models import Algorithm, Job, JobStatus, UserRole

    is_admin_upload = current_user is not None and current_user.role == UserRole.admin

    # Collect all files (rel posix path → absolute path)
    all_files: dict[str, Path] = {
        f.relative_to(pending_dir).as_posix(): f
        for f in pending_dir.rglob("*")
        if f.is_file()
    }

    py_files = {rel: path for rel, path in all_files.items() if rel.endswith(".py")}
    if not py_files:
        raise HTTPException(status_code=400, detail="Không tìm thấy file .py trong pending")

    # Find entry point: first .py that has all 3 required functions
    entry_rel: str | None = None
    entry_code: str = ""
    for rel, path in py_files.items():
        code = path.read_text(encoding="utf-8", errors="replace")
        if not _validate_plugin(code):
            entry_rel = rel
            entry_code = code
            break

    if not entry_rel:
        raise HTTPException(
            status_code=400,
            detail="Không tìm thấy file plugin hợp lệ (cần get_name, get_description, run)",
        )

    plugin_name = _extract_plugin_name(entry_code) or Path(entry_rel).stem
    safe_base = plugin_name.lower().replace(" ", "_")

    if db.query(Algorithm).filter(Algorithm.name == plugin_name).first():
        raise HTTPException(status_code=400, detail=f"Thuật toán '{plugin_name}' đã tồn tại")

    _PLUGINS_DIR.mkdir(parents=True, exist_ok=True)
    is_folder = len(all_files) > 1 or "/" in entry_rel

    if is_folder:
        plugin_dir = _PLUGINS_DIR / safe_base
        if plugin_dir.exists():
            shutil.rmtree(plugin_dir)
        plugin_dir.mkdir(parents=True)

        for rel, src in all_files.items():
            # Strip leading folder component (same logic as direct upload endpoint)
            parts = rel.split("/")
            dest_rel = "/".join(parts[1:]) if len(parts) > 1 else rel
            dest = plugin_dir / dest_rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(src), str(dest))

        entry_parts = entry_rel.split("/")
        entry_in_dir = "/".join(entry_parts[1:]) if len(entry_parts) > 1 else entry_rel
        stored_filename = f"{safe_base}/{entry_in_dir}"
    else:
        stored_filename = f"{safe_base}.py"
        shutil.copy(str(next(iter(py_files.values()))), str(_PLUGINS_DIR / stored_filename))

    # flow_steps: prefer explicit param (from frontend), fallback to analysis dict
    if flow_steps:
        flow_steps_json = flow_steps  # already a JSON string
    else:
        flow_steps_raw = analysis.get("flow_steps")
        flow_steps_json = json.dumps(flow_steps_raw, ensure_ascii=False) if flow_steps_raw else None

    algo = Algorithm(
        name=plugin_name,
        description=analysis.get("description"),
        is_system=is_admin_upload,
        filename=stored_filename,
        uploaded_by_id=meta["uploader_id"],
        vrp_variant=vrp_variant or None,
        selected_metrics=selected_metrics or None,
        flow_steps=flow_steps_json,
    )
    db.add(algo)
    db.commit()

    # Auto-verify: create a short job on the smallest matching instance
    instance_name = _find_smallest_instance(vrp_variant or "")
    if instance_name:
        verify_job = Job(
            instance_name=instance_name,
            method=plugin_name,
            time_limit_sec=60,
            seed=0,
            owner_id=meta["uploader_id"],
            status=JobStatus.pending,
        )
        db.add(verify_job)
        db.commit()
        db.refresh(verify_job)
        p = multiprocessing.Process(target=_run_verify_job, args=(verify_job.id,), daemon=True)
        p.start()


def _confirm_metric(meta: dict, analysis: dict, pending_dir: Path, db: Session):
    import ast as _ast
    from app.routers.metrics_api import _METRIC_PLUGINS_DIR
    from app.db.models import Metric

    filename = meta.get("filename") or "metric.py"
    src = pending_dir / filename
    if not src.exists():
        src = next(pending_dir.iterdir(), None)
        if not src:
            raise HTTPException(status_code=400, detail="Pending metric file không tồn tại")

    code = src.read_text(encoding="utf-8", errors="replace")

    # Extract plugin name from get_name()
    plugin_name = None
    try:
        tree = _ast.parse(code)
        for node in _ast.walk(tree):
            if isinstance(node, _ast.FunctionDef) and node.name == "get_name":
                for stmt in node.body:
                    if isinstance(stmt, _ast.Return) and isinstance(stmt.value, _ast.Constant):
                        plugin_name = str(stmt.value.value)
                        break
    except Exception:
        pass
    if not plugin_name:
        plugin_name = Path(src.name).stem

    if db.query(Metric).filter(Metric.name == plugin_name).first():
        raise HTTPException(status_code=400, detail=f"Độ đo '{plugin_name}' đã tồn tại")

    safe_filename = f"{plugin_name.lower().replace(' ', '_')}.py"
    _METRIC_PLUGINS_DIR.mkdir(parents=True, exist_ok=True)
    dest = _METRIC_PLUGINS_DIR / safe_filename
    shutil.copy(str(src), str(dest))

    visibility = meta.get("visibility", "public")
    shared_with_ids = meta.get("shared_with_ids", [])

    metric = Metric(
        name=plugin_name,
        description=analysis.get("description") or None,
        is_system=False,
        filename=safe_filename,
        uploaded_by_id=meta["uploader_id"],
        visibility=visibility,
        shared_with_ids=json.dumps(shared_with_ids) if shared_with_ids else None,
    )
    db.add(metric)
    db.commit()

    analysis_path = dest.with_suffix(dest.suffix + ".analysis.json")
    analysis_path.write_text(json.dumps(analysis, ensure_ascii=False), encoding="utf-8")


# ── reject ─────────────────────────────────────────────────────────────────────

@router.delete("/reject/{kind}/{temp_id}")
async def reject_upload(
    kind: str,
    temp_id: str,
    current_user: User = Depends(get_current_user),
):
    if kind not in ("dataset", "algorithm", "metric"):
        raise HTTPException(status_code=400, detail="kind không hợp lệ")

    meta = _read_pending_meta(kind, temp_id)
    if meta.get("uploader_id") != current_user.id:
        raise HTTPException(status_code=403, detail="Không có quyền reject upload này")

    pending_dir = _pending_dir(kind) / temp_id
    shutil.rmtree(pending_dir, ignore_errors=True)
    _pending_meta_path(kind, temp_id).unlink(missing_ok=True)

    return {"status": "rejected", "temp_id": temp_id}
