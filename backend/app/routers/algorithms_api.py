"""
Algorithm plugin management.
- System algorithm (ALNS) seeded at startup, cannot be deleted/edited.
- algo_tester role can upload custom Python plugins.
- Plugin interface required: get_name() -> str, get_description() -> str,
  run(instance, time_limit_sec, seed, **kwargs) -> AlnsResult-compatible
"""
from __future__ import annotations

import ast
import os
import sys
from pathlib import Path

import shutil
from fastapi import APIRouter, Body, Depends, HTTPException, UploadFile, File, status
from typing import List
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_algo_tester, require_admin
from app.db.models import Algorithm, User
from app.db.session import get_db
from app.models.schemas import AlgorithmOut, AlgorithmUpdate

router = APIRouter(prefix="/algorithms", tags=["algorithms"])

_REPO_ROOT = Path(__file__).resolve().parents[3]
_PLUGINS_DIR = _REPO_ROOT / "solver" / "plugins"
_REQUIRED_FUNCTIONS = {"get_name", "get_description", "run"}

SYSTEM_ALGORITHM_NAME = "ALNS"


def _ensure_system_algorithm(db: Session) -> None:
    """Insert the built-in ALNS record if not present."""
    if not db.query(Algorithm).filter(Algorithm.name == SYSTEM_ALGORITHM_NAME).first():
        db.add(Algorithm(
            name=SYSTEM_ALGORITHM_NAME,
            description=(
                "Adaptive Large Neighborhood Search — thuật toán tìm kiếm lân cận lớn thích nghi. "
                "3 giai đoạn: diversify / balance / intensify. Hỗ trợ Sartori & Buriol và Li & Lim."
            ),
            is_system=True,
            filename=None,
            uploaded_by_id=None,
        ))
        db.commit()


def _validate_plugin(code: str) -> list[str]:
    """Parse AST and return list of missing required top-level function names."""
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        raise HTTPException(status_code=400, detail=f"Syntax error: {e}")
    defined = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
    }
    missing = _REQUIRED_FUNCTIONS - defined
    return list(missing)


@router.get("/", response_model=list[AlgorithmOut])
def list_algorithms(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    _ensure_system_algorithm(db)
    return db.query(Algorithm).order_by(Algorithm.is_system.desc(), Algorithm.created_at.asc()).all()


@router.get("/{algo_id}", response_model=AlgorithmOut)
def get_algorithm(
    algo_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    _ensure_system_algorithm(db)
    algo = db.query(Algorithm).filter(Algorithm.id == algo_id).first()
    if not algo:
        raise HTTPException(status_code=404, detail="Không tìm thấy thuật toán")
    return algo


def _extract_plugin_name(code: str) -> str | None:
    """Best-effort: extract return value of get_name() as a string literal."""
    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "get_name":
                for stmt in node.body:
                    if isinstance(stmt, ast.Return) and isinstance(stmt.value, ast.Constant):
                        return str(stmt.value.value)
    except Exception:
        pass
    return None


@router.post("/upload", response_model=AlgorithmOut, status_code=status.HTTP_201_CREATED)
async def upload_algorithm(
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current: User = Depends(require_algo_tester),
):
    if not files:
        raise HTTPException(status_code=400, detail="Không có file nào được gửi lên")

    # Read all files into memory (skip .git internals and hidden dirs)
    file_contents: dict[str, bytes] = {}
    for f in files:
        if not f.filename:
            continue
        rel = f.filename.replace("\\", "/")
        # Skip .git and other hidden directories
        parts = rel.split("/")
        if any(p.startswith(".") for p in parts):
            continue
        file_contents[rel] = await f.read()

    if not file_contents:
        raise HTTPException(status_code=400, detail="Không có file nào hợp lệ")

    py_files = {k: v for k, v in file_contents.items() if k.endswith(".py")}
    if not py_files:
        raise HTTPException(
            status_code=400,
            detail=(
                "Folder không chứa file Python (.py) nào. "
                "Cần có ít nhất 1 file .py làm entry point với 3 hàm: "
                "get_name(), get_description(), run(). "
                "Nếu thuật toán viết bằng C++/Java/..., hãy thêm file plugin.py để gọi binary từ đó."
            )
        )

    # Find entry point: the .py file that contains all 3 required functions
    entry_rel: str | None = None
    entry_code: str = ""
    for rel, content in py_files.items():
        code = content.decode("utf-8", errors="replace")
        missing = _validate_plugin(code)
        if not missing:
            entry_rel = rel
            entry_code = code
            break

    if not entry_rel:
        # Show which functions are missing in the best candidate
        best_rel = next(iter(py_files))
        best_code = py_files[best_rel].decode("utf-8", errors="replace")
        missing = _validate_plugin(best_code)
        raise HTTPException(
            status_code=400,
            detail=f"Không tìm thấy file entry point hợp lệ. "
                   f"File '{best_rel}' thiếu: {', '.join(sorted(missing))}. "
                   f"Cần có: get_name(), get_description(), run(instance, time_limit_sec, seed, **kwargs)",
        )

    plugin_name = _extract_plugin_name(entry_code) or Path(entry_rel).stem

    if db.query(Algorithm).filter(Algorithm.name == plugin_name).first():
        raise HTTPException(status_code=400, detail=f"Thuật toán '{plugin_name}' đã tồn tại")

    _PLUGINS_DIR.mkdir(parents=True, exist_ok=True)
    safe_base = plugin_name.lower().replace(" ", "_")

    is_folder_upload = len(file_contents) > 1 or "/" in entry_rel

    if is_folder_upload:
        # Save entire folder structure to solver/plugins/<safe_base>/
        plugin_dir = _PLUGINS_DIR / safe_base
        if plugin_dir.exists():
            shutil.rmtree(plugin_dir)
        plugin_dir.mkdir(parents=True)

        for rel, content in file_contents.items():
            # Strip leading folder component if all paths share a common root
            parts = rel.split("/")
            dest_rel = "/".join(parts[1:]) if len(parts) > 1 else rel
            dest = plugin_dir / dest_rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(content)

        # Entry point relative to plugins dir
        entry_parts = entry_rel.split("/")
        entry_in_dir = "/".join(entry_parts[1:]) if len(entry_parts) > 1 else entry_rel
        stored_filename = f"{safe_base}/{entry_in_dir}"
    else:
        # Single file
        stored_filename = f"{safe_base}.py"
        (_PLUGINS_DIR / stored_filename).write_text(entry_code, encoding="utf-8")

    algo = Algorithm(
        name=plugin_name,
        description=None,
        is_system=False,
        filename=stored_filename,
        uploaded_by_id=current.id,
    )
    db.add(algo)
    db.commit()
    db.refresh(algo)
    return algo


@router.patch("/{algo_id}/visibility", response_model=AlgorithmOut)
def share_algorithm(
    algo_id: int,
    visibility: str = Body(...),
    shared_with_emails: list[str] = Body(default=[]),
    db: Session = Depends(get_db),
    current: User = Depends(require_algo_tester),
):
    import json
    from app.db.models import UserRole, User as UserModel

    algo = db.query(Algorithm).filter(Algorithm.id == algo_id).first()
    if not algo:
        raise HTTPException(status_code=404, detail="Không tìm thấy thuật toán")
    if algo.is_system:
        raise HTTPException(status_code=403, detail="Không thể thay đổi quyền thuật toán hệ thống")
    if current.role != UserRole.admin and algo.uploaded_by_id != current.id:
        raise HTTPException(status_code=403, detail="Bạn không có quyền thay đổi quyền thuật toán này")
    if visibility not in ("public", "private", "shared"):
        raise HTTPException(status_code=400, detail="visibility phải là public, private hoặc shared")

    shared_ids: list[int] = []
    for email in (shared_with_emails or []):
        u = db.query(UserModel).filter(UserModel.email == email).first()
        if u:
            shared_ids.append(u.id)

    algo.visibility = visibility
    algo.shared_with_ids = json.dumps(shared_ids) if shared_ids else None
    db.commit()
    db.refresh(algo)
    return algo


@router.patch("/{algo_id}", response_model=AlgorithmOut)
def update_algorithm(
    algo_id: int,
    body: AlgorithmUpdate,
    db: Session = Depends(get_db),
    current: User = Depends(require_algo_tester),
):
    algo = db.query(Algorithm).filter(Algorithm.id == algo_id).first()
    if not algo:
        raise HTTPException(status_code=404, detail="Không tìm thấy thuật toán")
    if body.vrp_variant is not None:
        algo.vrp_variant = body.vrp_variant
    if body.selected_metrics is not None:
        algo.selected_metrics = body.selected_metrics
    if body.description is not None:
        algo.description = body.description
    if body.flow_steps is not None:
        algo.flow_steps = body.flow_steps
    db.commit()
    db.refresh(algo)
    return algo


@router.post("/{algo_id}/reanalyze", response_model=AlgorithmOut)
def reanalyze_algorithm(
    algo_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(require_algo_tester),
):
    """Re-run LLM analysis on algorithm files and update description + flow_steps."""
    import json as _json
    from app.services.gemini_analysis import analyze as gemini_analyze

    algo = db.query(Algorithm).filter(Algorithm.id == algo_id).first()
    if not algo:
        raise HTTPException(status_code=404, detail="Không tìm thấy thuật toán")
    if not algo.filename:
        raise HTTPException(status_code=400, detail="Thuật toán không có file nguồn")

    plugin_path = _PLUGINS_DIR / algo.filename
    if not plugin_path.exists():
        raise HTTPException(status_code=404, detail="File plugin không tồn tại trên disk")

    # Collect source files for LLM (plugin dir or single file)
    content_map: dict[str, str] = {}
    plugin_dir = plugin_path.parent
    py_files = list(plugin_dir.rglob("*.py")) if plugin_dir != _PLUGINS_DIR else [plugin_path]
    for f in py_files[:5]:  # limit to 5 files to avoid huge prompts
        try:
            text = f.read_text(encoding="utf-8", errors="replace")[:4_000]
            content_map[f.name] = text
        except Exception:
            pass

    if not content_map:
        raise HTTPException(status_code=400, detail="Không đọc được file nguồn")

    try:
        analysis = gemini_analyze(content_map, "algorithm")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"LLM analysis failed: {exc}")

    algo.description = analysis.get("description") or algo.description
    flow_raw = analysis.get("flow_steps")
    if flow_raw:
        algo.flow_steps = _json.dumps(flow_raw, ensure_ascii=False)
    if analysis.get("problem_variant") and analysis["problem_variant"] != "Unknown":
        algo.vrp_variant = analysis["problem_variant"]

    db.commit()
    db.refresh(algo)
    return algo


@router.delete("/{algo_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_algorithm(
    algo_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(require_algo_tester),
):
    algo = db.query(Algorithm).filter(Algorithm.id == algo_id).first()
    if not algo:
        raise HTTPException(status_code=404, detail="Không tìm thấy thuật toán")
    if algo.is_system:
        raise HTTPException(status_code=403, detail="Không thể xóa thuật toán hệ thống")

    if algo.filename:
        plugin_file = _PLUGINS_DIR / algo.filename
        if plugin_file.exists():
            plugin_file.unlink()
        # If stored in a subfolder, remove the whole folder
        plugin_dir = _PLUGINS_DIR / Path(algo.filename).parts[0]
        if "/" in algo.filename and plugin_dir.is_dir():
            shutil.rmtree(plugin_dir)

    db.delete(algo)
    db.commit()
