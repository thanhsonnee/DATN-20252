"""
List, upload, and delete benchmark instance files.
"""
from __future__ import annotations

import hashlib
import io
import json
import shutil
import tarfile
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Body, Depends, Form, HTTPException, UploadFile, File, Query

from app.core.config import settings
from app.core.deps import get_current_user
from app.db.session import get_db
from sqlalchemy.orm import Session
from app.db.models import Algorithm, Job, Solution, User
from app.models.schemas import BaselineOut, DatasetStatAlgoResult, DatasetStatInstanceRow, DatasetStatResponse, InstanceInfo

router = APIRouter(prefix="/instances", tags=["instances"])

_REPO_ROOT = Path(__file__).resolve().parents[3]
_INSTANCE_EXTS = {".txt", ".pdptw", ".csv"}


def _meta_path(file_path: Path) -> Path:
    """Return the sidecar metadata file path for an instance file."""
    return file_path.with_suffix(file_path.suffix + ".meta.json")


def _folder_meta_path(folder: Path) -> Path:
    return folder / ".folder.meta.json"


def _read_meta(file_path: Path) -> dict:
    mp = _meta_path(file_path)
    if mp.exists():
        try:
            return json.loads(mp.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _read_folder_meta(folder: Path) -> dict:
    mp = _folder_meta_path(folder)
    if mp.exists():
        try:
            return json.loads(mp.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _write_meta(
    file_path: Path,
    uploader_id: int,
    uploader_name: str,
    uploader_email: str,
    visibility: str = "public",
    shared_with: list | None = None,
    fingerprint: dict | None = None,
) -> None:
    mp = _meta_path(file_path)
    data = {
        "uploaded_by": uploader_name,
        "uploaded_by_email": uploader_email,
        "uploaded_by_id": uploader_id,
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
        "visibility": visibility,
        "shared_with": shared_with or [],
    }
    if fingerprint:
        data.update(fingerprint)
    mp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def _write_folder_meta(
    folder: Path,
    uploader_id: int,
    uploader_name: str,
    uploader_email: str,
    visibility: str = "public",
    shared_with: list | None = None,
) -> None:
    """Write folder-level visibility metadata. Does NOT overwrite existing meta."""
    mp = _folder_meta_path(folder)
    if mp.exists():
        return
    data = {
        "uploaded_by": uploader_name,
        "uploaded_by_email": uploader_email,
        "uploaded_by_id": uploader_id,
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
        "visibility": visibility,
        "shared_with": shared_with or [],
    }
    mp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def _item_meta(item: Path) -> dict:
    """Read metadata for a top-level item (folder or file)."""
    if item.is_dir():
        return _read_folder_meta(item)
    return _read_meta(item)


def _can_access(item: Path, current: "User") -> bool:
    """Check if current user can access a top-level item."""
    from app.db.models import UserRole
    if current.role == UserRole.admin:
        return True
    if item.is_dir() and item.name in _SYSTEM_DATASET_FOLDERS:
        return True
    meta = _item_meta(item)
    if not meta:
        return True  # no meta → public (backward compat)
    visibility = meta.get("visibility", "public")
    if visibility == "public":
        return True
    owner_id = meta.get("uploaded_by_id")
    if visibility == "private":
        return owner_id == current.id
    if visibility == "shared":
        if owner_id == current.id:
            return True
        return current.id in (meta.get("shared_with") or [])
    return False


def _instances_dir() -> Path:
    p = Path(settings.INSTANCES_DIR)
    if not p.is_absolute():
        p = (_REPO_ROOT / p).resolve()
    return p


def _safe_resolve(base: Path, rel: str) -> Path:
    """Resolve a relative path under base, raising 400 if it escapes."""
    target = (base / rel).resolve()
    if not str(target).startswith(str(base.resolve())):
        raise HTTPException(status_code=400, detail="Invalid path")
    return target


def _detect_fmt(lines: list[str]) -> str:
    """Return 'lilim', 'ropke_cordeau', '2e_vrp_pdd', '2e_evrp', or 'sartori'."""
    if not lines:
        return "sartori"
    first_line = lines[0]
    # CSV: comma-separated header row → 2E-VRP-PDD format
    if "," in first_line and first_line.split(",")[0].strip().upper() in ("TYPE", "ID", "NODE"):
        return "2e_vrp_pdd"
    first = first_line.split()
    # 2E-EVRP: header row starts with "StringID"
    if first and first[0].upper() == "STRINGID":
        return "2e_evrp"
    if len(first) >= 2 and all(x.lstrip("-").isdigit() for x in first[:2]):
        return "lilim"
    for line in lines[:30]:
        if line.strip().upper().startswith("NODE_COORD_SECTION"):
            return "ropke_cordeau"
    return "sartori"


def _compute_fingerprint(content: bytes) -> dict:
    """Compute deduplication fingerprint for raw file bytes."""
    text = content.decode("utf-8", errors="replace")
    non_empty_lines = [l for l in text.splitlines() if l.strip()]
    head10 = "\n".join(non_empty_lines[:10]).encode("utf-8", errors="replace")
    return {
        "file_size": len(content),
        "num_lines": len(non_empty_lines),
        "sha256_full": hashlib.sha256(content).hexdigest(),
        "sha256_head10": hashlib.sha256(head10).hexdigest(),
    }


def _find_duplicate(fp: dict, base: Path) -> Optional[str]:
    """
    Scan all .meta.json files under base for a content duplicate of fp.
    Returns the relative path of the first matching file, or None.
    Early-exits on first match — never scans all files unnecessarily.

    Tầng 1: file_size + num_lines must both match.
    Tầng 2: sha256_full or sha256_head10 must match.
    """
    for meta_path in base.rglob("*.meta.json"):
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        # Tầng 1: quick numeric filter
        if meta.get("file_size") != fp["file_size"]:
            continue
        if meta.get("num_lines") != fp["num_lines"]:
            continue
        # Tầng 2: hash check
        if (meta.get("sha256_full") == fp["sha256_full"]
                or meta.get("sha256_head10") == fp["sha256_head10"]):
            # Reconstruct the instance file path from the .meta.json path
            instance_path = meta_path.with_name(meta_path.stem)  # strip ".meta.json"
            try:
                return instance_path.relative_to(base).as_posix()
            except ValueError:
                return meta_path.name
    return None


def _parse_header(path: Path) -> dict:
    try:
        lines = [l.strip() for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
        fmt = _detect_fmt(lines)

        if fmt == "lilim":
            first = lines[0].split()
            result: dict = {"num_vehicles": int(first[0]), "capacity": float(first[1])}
            node_lines = len(lines) - 1
            if node_lines > 1:
                result["num_requests"] = (node_lines - 1) // 2
            return result

        if fmt == "ropke_cordeau":
            result = {}
            for line in lines:
                upper = line.upper()
                if upper.startswith("NODE_COORD_SECTION"):
                    break
                if ":" in line:
                    key, val = line.split(":", 1)
                    k = key.strip().upper()
                    if k == "CAPACITY":
                        result["capacity"] = float(val.strip())
                    elif k == "DIMENSION":
                        dim = int(val.strip())
                        result["num_requests"] = (dim - 1) // 2
                    elif k == "VEHICLES":
                        result["num_vehicles"] = int(val.strip())
            return result if result else {}

        if fmt == "2e_vrp_pdd":
            result = {}
            # FE Cap from depot row (Type=0)
            for line in lines[1:]:
                parts = [p.strip() for p in line.split(",")]
                if parts[0] == "0" and len(parts) >= 10:
                    try:
                        if parts[9]: result["capacity"] = float(parts[9])
                    except ValueError:
                        pass
                    break
            # Count non-depot, non-satellite rows as rough request count
            data_rows = len([l for l in lines[1:] if l.split(",")[0].strip() not in ("", "0", "1")])
            if data_rows:
                result["num_requests"] = data_rows // 2
            return result if result else {"num_requests": 0}

        if fmt == "2e_evrp":
            import re as _re
            _cap_pat = _re.compile(r"/\s*([\d.]+)\s*/")
            result = {}
            num_customers = 0
            for line in lines[1:]:
                parts = line.split()
                if not parts:
                    continue
                # Capacity line: single-letter key followed by description and /value/
                if len(parts[0]) == 1 and parts[0].isalpha() and "/" in line:
                    m = _cap_pat.search(line)
                    if m and parts[0] == "L":
                        try:
                            result["capacity"] = float(m.group(1))
                        except ValueError:
                            pass
                elif len(parts) >= 2 and parts[1].lower() == "c":
                    num_customers += 1
            if num_customers:
                result["num_requests"] = num_customers
            return result if result else {"num_requests": 0}

        # Sartori: "NAME: value" (no space before colon)
        if any(l.startswith("NAME:") or l.startswith("TYPE:") for l in lines[:6]):
            result = {}
            for line in lines:
                if line.startswith("CAPACITY:"):
                    result["capacity"] = float(line.split(":", 1)[1].strip())
                elif line.startswith("SIZE:"):
                    size = int(line.split(":", 1)[1].strip())
                    result["num_requests"] = (size - 1) // 2
            return result if result else {}

    except Exception:
        pass
    return {}


def _collect_files(directory: Path, current: "User") -> list[InstanceInfo]:
    """Return all valid instance files recursively as a flat list, filtered by visibility."""
    base = _instances_dir()
    # Get accessible top-level items
    accessible_tops: set[str] = set()
    for top in base.iterdir():
        if _can_access(top, current):
            accessible_tops.add(top.name)

    results: list[InstanceInfo] = []
    seen: set[str] = set()
    candidates: list[Path] = []
    for ext in _INSTANCE_EXTS:
        candidates.extend(directory.rglob(f"*{ext}"))
    for f in sorted(set(candidates)):
        if not f.is_file():
            continue
        # Check top-level access
        rel = f.relative_to(base)
        top_name = rel.parts[0] if rel.parts else ""
        if top_name not in accessible_tops:
            continue
        meta = _parse_header(f)
        if not meta:
            continue
        name = f.stem if f.suffix in _INSTANCE_EXTS else f.name
        if name in seen:
            continue
        seen.add(name)
        rel_path = rel.as_posix()
        upload_meta = _read_meta(f)
        results.append(InstanceInfo(
            name=name, path=rel_path,
            uploaded_by=upload_meta.get("uploaded_by"),
            uploaded_at=upload_meta.get("uploaded_at"),
            uploaded_by_id=upload_meta.get("uploaded_by_id"),
            visibility=upload_meta.get("visibility", "public"),
            shared_with=upload_meta.get("shared_with"),
            **meta,
        ))
    return results


def _count_instance_files(directory: Path) -> int:
    """Count instance files by extension only (no parsing)."""
    count = 0
    for ext in _INSTANCE_EXTS:
        count += sum(1 for f in directory.rglob(f"*{ext}") if f.is_file())
    return count


def _list_dir(directory: Path, base: Path, current: "User", is_root: bool = False) -> list[InstanceInfo]:
    """Return direct children of directory as InstanceInfo list, filtered by visibility at root level."""
    results: list[InstanceInfo] = []
    for item in sorted(directory.iterdir()):
        # At root level, apply visibility filtering
        if is_root and not _can_access(item, current):
            continue
        # Skip hidden meta files
        if item.name.startswith("."):
            continue
        rel_path = item.relative_to(base).as_posix()
        if item.is_dir():
            file_count = _count_instance_files(item)
            folder_meta = _read_folder_meta(item)
            results.append(InstanceInfo(
                name=item.name,
                path=rel_path,
                is_folder=True,
                file_count=file_count,
                uploaded_by=folder_meta.get("uploaded_by"),
                uploaded_at=folder_meta.get("uploaded_at"),
                uploaded_by_id=folder_meta.get("uploaded_by_id"),
                visibility=folder_meta.get("visibility", "public"),
                shared_with=folder_meta.get("shared_with"),
            ))
        elif item.is_file() and item.suffix in _INSTANCE_EXTS:
            meta = _parse_header(item)
            if not meta:
                continue
            name = item.stem if item.suffix in _INSTANCE_EXTS else item.name
            upload_meta = _read_meta(item)
            results.append(InstanceInfo(
                name=name, path=rel_path,
                uploaded_by=upload_meta.get("uploaded_by"),
                uploaded_at=upload_meta.get("uploaded_at"),
                uploaded_by_id=upload_meta.get("uploaded_by_id"),
                visibility=upload_meta.get("visibility", "public"),
                shared_with=upload_meta.get("shared_with"),
                **meta,
            ))
    return results


@router.get("/", response_model=list[InstanceInfo])
def list_instances(
    folder: Optional[str] = Query(default=None),
    flat: bool = Query(default=False),
    current: User = Depends(get_current_user),
):
    base = _instances_dir()
    if not base.exists():
        return []

    if flat:
        return _collect_files(base, current)

    target = _safe_resolve(base, folder) if folder else base
    if not target.is_dir():
        raise HTTPException(status_code=404, detail="Folder not found")
    is_root = (target == base)
    return _list_dir(target, base, current, is_root=is_root)


@router.post("/upload", status_code=201)
async def upload_instances(
    files: List[UploadFile] = File(...),
    visibility: str = Form(default="public"),
    shared_with_emails: str = Form(default="[]"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.db.models import UserRole
    from app.db.models import User as UserModel
    allowed = {UserRole.admin, UserRole.algo_tester, UserRole.dataset_provider}
    if current_user.role not in allowed:
        raise HTTPException(status_code=403, detail="Forbidden")

    # algo_tester: always private
    if current_user.role == UserRole.algo_tester:
        visibility = "private"
        shared_with_ids: list = []
    else:
        if visibility not in ("public", "private", "shared"):
            visibility = "public"
        try:
            emails = json.loads(shared_with_emails)
            if not isinstance(emails, list):
                emails = []
        except Exception:
            emails = []
        shared_with_ids = []
        for email in emails:
            u = db.query(UserModel).filter(UserModel.email == email).first()
            if u:
                shared_with_ids.append(u.id)

    base = _instances_dir()
    base.mkdir(parents=True, exist_ok=True)
    uploaded: list[InstanceInfo] = []
    skipped: list[str] = []
    failed: list[dict] = []
    written_folder_metas: set[str] = set()

    for file in files:
        raw = Path(file.filename or "")
        parts = [p for p in raw.parts if p not in ("", ".", "..") and p != "/"]
        if not parts:
            continue
        rel = Path(*parts)
        filename = str(rel)

        # Chỉ chấp nhận file có extension hợp lệ
        if Path(rel).suffix not in _INSTANCE_EXTS:
            failed.append({"filename": filename, "status": "failed", "error_msg": "Định dạng file không được hỗ trợ"})
            continue

        dest = base / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            skipped.append(filename)
            continue

        content = await file.read()

        # Kiểm tra trùng lặp nội dung trước khi ghi file
        fp = _compute_fingerprint(content)
        dup = _find_duplicate(fp, base)
        if dup:
            failed.append({
                "filename": filename,
                "status": "failed",
                "error_msg": f"Nội dung file trùng với instance đã có trong hệ thống: {dup}",
            })
            continue

        dest.write_bytes(content)

        # Validate: file phải parse được header hợp lệ
        header = _parse_header(dest)
        if not header:
            dest.unlink(missing_ok=True)
            failed.append({"filename": filename, "status": "failed", "error_msg": "Không nhận dạng được định dạng PDPTW"})
            continue

        _write_meta(dest, current_user.id, current_user.full_name, current_user.email, visibility, shared_with_ids, fingerprint=fp)

        # Write folder meta for top-level folder (once per folder)
        top_dir = base / rel.parts[0] if len(rel.parts) > 1 else None
        if top_dir and top_dir.is_dir() and top_dir.name not in written_folder_metas:
            _write_folder_meta(top_dir, current_user.id, current_user.full_name, current_user.email, visibility, shared_with_ids)
            written_folder_metas.add(top_dir.name)

        name = dest.stem if dest.suffix in _INSTANCE_EXTS else dest.name
        upload_meta = _read_meta(dest)
        uploaded.append(InstanceInfo(
            name=name,
            path=rel.as_posix(),
            uploaded_by=upload_meta.get("uploaded_by"),
            uploaded_at=upload_meta.get("uploaded_at"),
            uploaded_by_id=upload_meta.get("uploaded_by_id"),
            visibility=upload_meta.get("visibility", visibility),
            shared_with=upload_meta.get("shared_with"),
            **_parse_header(dest),
        ))
    if not uploaded and not skipped and failed:
        raise HTTPException(status_code=422, detail=f"Tất cả {len(failed)} file không hợp lệ, không có file nào được upload")
    if not uploaded and skipped:
        raise HTTPException(status_code=409, detail=f"Tất cả {len(skipped)} file đã tồn tại, không có file nào được upload")
    return {"uploaded": [i.model_dump() for i in uploaded], "skipped": skipped, "failed": failed}


_ARCHIVE_EXTS = {".zip", ".gz", ".bz2", ".tar"}
_MAX_ARCHIVE_SIZE = 500 * 1024 * 1024  # 500 MB


def _is_archive(filename: str) -> bool:
    name = filename.lower()
    return name.endswith(".zip") or name.endswith(".tar.gz") or name.endswith(".tar.bz2") or name.endswith(".tar")


def _extract_archive(data: bytes, filename: str) -> list[tuple[str, bytes]]:
    """Extract archive bytes and return list of (relative_path, file_bytes) for all entries."""
    name = filename.lower()
    entries: list[tuple[str, bytes]] = []

    if name.endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                entries.append((info.filename, zf.read(info.filename)))

    elif name.endswith(".tar.gz") or name.endswith(".tar.bz2") or name.endswith(".tar"):
        mode = "r:gz" if name.endswith(".tar.gz") else ("r:bz2" if name.endswith(".tar.bz2") else "r:")
        with tarfile.open(fileobj=io.BytesIO(data), mode=mode) as tf:
            for member in tf.getmembers():
                if not member.isfile():
                    continue
                f = tf.extractfile(member)
                if f is None:
                    continue
                entries.append((member.name, f.read()))

    return entries


@router.post("/upload-archive", status_code=201)
async def upload_archive(
    file: UploadFile = File(...),
    visibility: str = Form(default="public"),
    shared_with_emails: str = Form(default="[]"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Upload một file nén (.zip, .tar.gz, .tar.bz2) chứa các instance PDPTW."""
    from app.db.models import UserRole
    from app.db.models import User as UserModel

    allowed = {UserRole.admin, UserRole.algo_tester, UserRole.dataset_provider}
    if current_user.role not in allowed:
        raise HTTPException(status_code=403, detail="Forbidden")

    filename = file.filename or ""
    if not _is_archive(filename):
        raise HTTPException(
            status_code=400,
            detail="Chỉ chấp nhận file nén: .zip, .tar.gz, .tar.bz2, .tar",
        )

    # algo_tester: always private
    if current_user.role == UserRole.algo_tester:
        visibility = "private"
        shared_with_ids: list = []
    else:
        if visibility not in ("public", "private", "shared"):
            visibility = "public"
        try:
            emails = json.loads(shared_with_emails)
            if not isinstance(emails, list):
                emails = []
        except Exception:
            emails = []
        shared_with_ids = []
        for email in emails:
            u = db.query(UserModel).filter(UserModel.email == email).first()
            if u:
                shared_with_ids.append(u.id)

    data = await file.read()
    if len(data) > _MAX_ARCHIVE_SIZE:
        raise HTTPException(status_code=413, detail="File nén quá lớn (tối đa 500 MB)")

    try:
        entries = _extract_archive(data, filename)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Không thể giải nén file: {exc}")

    if not entries:
        raise HTTPException(status_code=422, detail="File nén rỗng hoặc không chứa file nào")

    base = _instances_dir()
    base.mkdir(parents=True, exist_ok=True)

    uploaded: list[InstanceInfo] = []
    skipped: list[str] = []
    failed: list[dict] = []
    written_folder_metas: set[str] = set()

    for raw_path, content in entries:
        # Sanitise path components
        parts = [p for p in Path(raw_path).parts if p not in ("", ".", "..") and p != "/"]
        if not parts:
            continue
        rel = Path(*parts)
        filename_rel = rel.as_posix()

        # Only accept known instance extensions
        if rel.suffix not in _INSTANCE_EXTS:
            failed.append({"filename": filename_rel, "status": "failed", "error_msg": "Định dạng file không được hỗ trợ"})
            continue

        dest = base / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            skipped.append(filename_rel)
            continue

        # Kiểm tra trùng lặp nội dung trước khi ghi file
        fp = _compute_fingerprint(content)
        dup = _find_duplicate(fp, base)
        if dup:
            failed.append({
                "filename": filename_rel,
                "status": "failed",
                "error_msg": f"Nội dung file trùng với instance đã có trong hệ thống: {dup}",
            })
            continue

        dest.write_bytes(content)

        header = _parse_header(dest)
        if not header:
            dest.unlink(missing_ok=True)
            failed.append({"filename": filename_rel, "status": "failed", "error_msg": "Không nhận dạng được định dạng PDPTW"})
            continue

        _write_meta(dest, current_user.id, current_user.full_name, current_user.email, visibility, shared_with_ids, fingerprint=fp)

        top_dir = base / rel.parts[0] if len(rel.parts) > 1 else None
        if top_dir and top_dir.is_dir() and top_dir.name not in written_folder_metas:
            _write_folder_meta(top_dir, current_user.id, current_user.full_name, current_user.email, visibility, shared_with_ids)
            written_folder_metas.add(top_dir.name)

        name = dest.stem if dest.suffix in _INSTANCE_EXTS else dest.name
        upload_meta = _read_meta(dest)
        uploaded.append(InstanceInfo(
            name=name,
            path=rel.as_posix(),
            uploaded_by=upload_meta.get("uploaded_by"),
            uploaded_at=upload_meta.get("uploaded_at"),
            uploaded_by_id=upload_meta.get("uploaded_by_id"),
            visibility=upload_meta.get("visibility", visibility),
            shared_with=upload_meta.get("shared_with"),
            **_parse_header(dest),
        ))

    if not uploaded and not skipped and failed:
        raise HTTPException(status_code=422, detail=f"Tất cả {len(failed)} file trong archive không hợp lệ")
    if not uploaded and skipped:
        raise HTTPException(status_code=409, detail=f"Tất cả {len(skipped)} file trong archive đã tồn tại")
    return {"uploaded": [i.model_dump() for i in uploaded], "skipped": skipped, "failed": failed}


@router.get("/content")
def get_instance_content(
    path: str = Query(...),
    _: User = Depends(get_current_user),
):
    base = _instances_dir()
    target = _safe_resolve(base, path)
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    try:
        content = target.read_text(encoding="utf-8")
    except Exception:
        raise HTTPException(status_code=422, detail="Cannot read file")

    parse_report = _build_parse_report(target)
    upload_meta = _read_meta(target)

    return {
        "path": path,
        "name": target.name,
        "content": content,
        "metadata": {
            "dataset_type": parse_report.get("dataset_type"),
            "dataset_type_label": parse_report.get("dataset_type_label"),
            "stats": parse_report.get("stats", {}),
            "errors": parse_report.get("errors", []),
            "warnings": parse_report.get("warnings", []),
            "fields": parse_report.get("fields", []),
            "visibility": upload_meta.get("visibility", "public"),
            "uploaded_by": upload_meta.get("uploaded_by"),
            "uploaded_by_email": upload_meta.get("uploaded_by_email"),
            "uploaded_at": upload_meta.get("uploaded_at"),
        },
    }


_SYSTEM_DATASET_FOLDERS = {"sartori-dataset", "lilim-dataset", "2e-vrp-pdd-main"}


@router.delete("/")
def delete_instance(
    path: str = Query(...),
    current: User = Depends(get_current_user),
):
    from app.db.models import UserRole
    allowed = {UserRole.admin, UserRole.algo_tester, UserRole.dataset_provider}
    if current.role not in allowed:
        raise HTTPException(status_code=403, detail="Forbidden")

    base = _instances_dir()
    target = _safe_resolve(base, path)
    if not target.exists():
        raise HTTPException(status_code=404, detail="Không tìm thấy")

    top_level = Path(path).parts[0] if Path(path).parts else ""

    # Protect system dataset folders — admin can still delete
    if top_level in _SYSTEM_DATASET_FOLDERS and current.role != UserRole.admin:
        raise HTTPException(status_code=403, detail=f"'{top_level}' là dataset hệ thống, không thể xóa")

    # Ownership / access check (admin bypasses)
    if current.role != UserRole.admin:
        top_path = base / top_level
        meta = _item_meta(top_path)
        owner_id = meta.get("uploaded_by_id") if meta else None

        if current.role == UserRole.algo_tester:
            # algo_tester can delete any dataset they have access to
            if not _can_access(top_path, current):
                raise HTTPException(status_code=403, detail="Bạn không có quyền xóa dataset này")
        else:
            # dataset_provider: can delete if they own it OR it has no owner (unclaimed)
            if owner_id is not None and owner_id != current.id:
                raise HTTPException(status_code=403, detail="Bạn không có quyền xóa dataset này")

    if target.is_dir():
        shutil.rmtree(target)
    else:
        target.unlink()
        # Clean up sidecar
        mp = _meta_path(target)
        if mp.exists():
            mp.unlink()
    return {"deleted": path}


@router.patch("/visibility")
def update_visibility(
    path: str = Body(...),
    visibility: str = Body(...),
    shared_with_emails: list[str] = Body(default=[]),
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    from app.db.models import UserRole
    from app.db.models import User as UserModel

    allowed = {UserRole.admin, UserRole.dataset_provider}
    if current.role not in allowed:
        raise HTTPException(status_code=403, detail="Forbidden")

    if visibility not in ("public", "private", "shared"):
        raise HTTPException(status_code=400, detail="visibility phải là public, private hoặc shared")

    base = _instances_dir()
    target = _safe_resolve(base, path)
    if not target.exists():
        raise HTTPException(status_code=404, detail="Không tìm thấy")

    top_level = Path(path).parts[0] if Path(path).parts else ""
    if top_level in _SYSTEM_DATASET_FOLDERS:
        raise HTTPException(status_code=403, detail="Không thể thay đổi quyền của dataset hệ thống")

    # Ownership check (admin bypasses)
    top_path = base / top_level
    meta = _item_meta(top_path)
    owner_id = meta.get("uploaded_by_id") if meta else None
    # dataset_provider: can edit if they own it OR it has no owner (unclaimed)
    if current.role != UserRole.admin and owner_id is not None and owner_id != current.id:
        raise HTTPException(status_code=403, detail="Bạn không có quyền thay đổi quyền của dataset này")

    # Resolve emails → user IDs
    shared_with_ids: list[int] = []
    not_found: list[str] = []
    for email in shared_with_emails:
        u = db.query(UserModel).filter(UserModel.email == email).first()
        if u:
            shared_with_ids.append(u.id)
        else:
            not_found.append(email)

    # Update meta
    mp = _folder_meta_path(target) if target.is_dir() else _meta_path(target)
    if mp.exists():
        try:
            data = json.loads(mp.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    else:
        data = {}
    data["visibility"] = visibility
    data["shared_with"] = shared_with_ids
    mp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    return {
        "path": path,
        "visibility": visibility,
        "shared_with": shared_with_ids,
        "not_found_emails": not_found,
    }


def _node_type(p: int, d: int) -> tuple[str, int | None]:
    """Return (type, pair) for a node given its pickup/delivery columns."""
    if p == 0 and d == 0:
        return "depot", None
    if p == 0:          # d != 0 → this node is pickup, delivery is d
        return "pickup", d
    return "delivery", p  # p != 0 → this node is delivery, pickup is p


@router.get("/nodes")
def get_instance_nodes(
    name: str = Query(...),
    _: User = Depends(get_current_user),
):
    """Return node coordinates + type (depot/pickup/delivery) by reading the file directly."""
    base = _instances_dir()
    candidates = list(base.rglob(name)) + list(base.rglob(f"{name}.txt"))
    if not candidates:
        raise HTTPException(status_code=404, detail="Instance not found")

    file_path = candidates[0]
    try:
        lines = [l.strip() for l in file_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    except Exception:
        raise HTTPException(status_code=422, detail="Cannot read file")

    if not lines:
        raise HTTPException(status_code=422, detail="Empty file")

    dataset_type = _detect_fmt(lines)
    nodes = []

    if dataset_type == "lilim":
        for line in lines[1:]:
            parts = line.split()
            if len(parts) < 9:
                continue
            try:
                nid, lat, lon = int(parts[0]), float(parts[1]), float(parts[2])
                ntype, pair = _node_type(int(parts[7]), int(parts[8]))
                nodes.append({"id": nid, "lat": lat, "lon": lon, "type": ntype, "pair": pair})
            except ValueError:
                pass

    elif dataset_type == "ropke_cordeau":
        # Phase 1: collect coordinates from NODE_COORD_SECTION
        coords: dict[int, tuple[float, float]] = {}
        in_coords = False
        for line in lines:
            if line.upper().startswith("NODE_COORD_SECTION"):
                in_coords = True
                continue
            if in_coords:
                if line.upper().startswith("PICKUP_AND_DELIVERY_SECTION") or not line[0].isdigit():
                    break
                parts = line.split()
                if len(parts) >= 3:
                    try:
                        coords[int(parts[0])] = (float(parts[1]), float(parts[2]))
                    except ValueError:
                        pass

        # Phase 2: collect types from PICKUP_AND_DELIVERY_SECTION
        # format: id demand e l service pickup delivery
        in_pd = False
        for line in lines:
            if line.upper().startswith("PICKUP_AND_DELIVERY_SECTION"):
                in_pd = True
                continue
            if in_pd:
                parts = line.split()
                if len(parts) < 7:
                    break
                try:
                    nid = int(parts[0])
                    demand = int(parts[1])
                    pickup_col = int(parts[5])
                    delivery_col = int(parts[6])
                    if nid not in coords:
                        continue
                    lat, lon = coords[nid]
                    if demand == 0:
                        ntype, pair = "depot", None
                    elif demand > 0 and delivery_col != 0:
                        ntype, pair = "pickup", delivery_col
                    else:
                        ntype, pair = "delivery", pickup_col
                    nodes.append({"id": nid, "lat": lat, "lon": lon, "type": ntype, "pair": pair})
                except ValueError:
                    pass

    else:  # sartori
        in_nodes = False
        for line in lines:
            if line.upper() == "NODES":
                in_nodes = True
                continue
            if line.upper() == "EDGES":
                break
            if not in_nodes:
                continue
            parts = line.split()
            if len(parts) < 9:
                continue
            try:
                nid, lat, lon = int(parts[0]), float(parts[1]), float(parts[2])
                ntype, pair = _node_type(int(parts[7]), int(parts[8]))
                nodes.append({"id": nid, "lat": lat, "lon": lon, "type": ntype, "pair": pair})
            except ValueError:
                pass

    return {"dataset_type": dataset_type, "nodes": nodes}


# ── Parse report ──────────────────────────────────────────────────────────────

def _build_parse_report(file_path: Path) -> dict:
    """
    Parse instance file and return a structured field-mapping report.
    Status values:
      'ok'      – field read directly from file and used as-is
      'derived' – field computed/inferred from other data in the file
      'ignored' – field present in file but not used by the algorithm
      'error'   – field required but missing or invalid
    """
    import sys as _sys
    _REPO_ROOT_local = Path(__file__).resolve().parents[3]
    if str(_REPO_ROOT_local) not in _sys.path:
        _sys.path.insert(0, str(_REPO_ROOT_local))

    try:
        lines = [l.strip() for l in file_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    except Exception as e:
        return {"errors": [f"Cannot read file: {e}"], "fields": []}

    dataset_type = _detect_fmt(lines)

    # ---- 2E-EVRP: parse and return immediately ----
    if dataset_type == "2e_evrp":
        try:
            from solver.parsers.two_echelon_evrp import TwoEchelonEVRPParser, parse_report_2eevrp  # type: ignore
            inst_evrp = TwoEchelonEVRPParser().parse(str(file_path))
            return parse_report_2eevrp(inst_evrp)
        except Exception as e:
            return {
                "instance_name": file_path.stem,
                "dataset_type": "2e_evrp",
                "dataset_type_label": "2E-EVRP",
                "stats": {},
                "errors": [str(e)],
                "warnings": [],
                "fields": [],
            }

    # ---- 2E-VRP-PDD: parse and return immediately (separate model/report) ----
    if dataset_type == "2e_vrp_pdd":
        try:
            from solver.parsers.two_echelon import TwoEchelonParser, parse_report_2evrp  # type: ignore
            inst2e = TwoEchelonParser().parse(str(file_path))
            return parse_report_2evrp(inst2e)
        except Exception as e:
            return {
                "instance_name": file_path.stem,
                "dataset_type": "2e_vrp_pdd",
                "dataset_type_label": "2E-VRP-PDD",
                "stats": {},
                "errors": [str(e)],
                "warnings": [],
                "fields": [],
            }

    # ---- PDPTW formats (sartori / lilim / ropke_cordeau) ----
    parse_errors: list[str] = []
    stats: dict = {}
    try:
        from solver.parsers import load_instance  # type: ignore
        inst = load_instance(str(file_path), dataset_type=dataset_type)
        stats = {
            "num_nodes": inst.num_nodes(),
            "num_requests": inst.num_requests(),
            "capacity": inst.capacity,
            "horizon": inst.horizon,
            "depot_id": inst.depot_id,
            "travel_time_size": len(inst.travel_time),
        }
    except Exception as e:
        if hasattr(e, "errors"):
            parse_errors = e.errors  # type: ignore[attr-defined]
        else:
            parse_errors = [str(e)]

    # ---- Build field table per dataset type ----
    F = dict  # shorthand

    if dataset_type == "sartori":
        label = "Sartori & Buriol"
        warnings: list[str] = []
        # Read a few header values for display
        hdr: dict[str, str] = {}
        for line in lines:
            if ":" in line and not line.upper().startswith("NODES"):
                k, v = line.split(":", 1)
                hdr[k.strip().upper()] = v.strip()
        fields = [
            # Instance-level
            F(category="Instance", field="name",         status="ok",      source="Header NAME",          value=hdr.get("NAME",""),     note="Tên instance"),
            F(category="Instance", field="capacity",     status="ok",      source="Header CAPACITY",       value=hdr.get("CAPACITY",""), note="Tải trọng tối đa mỗi xe"),
            F(category="Instance", field="horizon",      status="ok",      source="Header ROUTE-TIME",     value=hdr.get("ROUTE-TIME",""),note="Thời gian tối đa 1 route"),
            F(category="Instance", field="travel_time",  status="ok",      source="Section EDGES",         value=f"{hdr.get('SIZE','?')}×{hdr.get('SIZE','?')} matrix", note="Ma trận thời gian di chuyển có sẵn trong file"),
            # Node fields
            F(category="Node",     field="id",           status="ok",      source="NODES col 0",           value="",  note="ID node"),
            F(category="Node",     field="lat, lon",     status="ok",      source="NODES col 1, 2",        value="",  note="Tọa độ địa lý thực (Barcelona)"),
            F(category="Node",     field="demand",       status="ok",      source="NODES col 3",           value="",  note="+demand pickup, −demand delivery"),
            F(category="Node",     field="tw_early",     status="ok",      source="NODES col 4",           value="",  note="Thời điểm sớm nhất phục vụ"),
            F(category="Node",     field="tw_late",      status="ok",      source="NODES col 5",           value="",  note="Thời điểm trễ nhất phục vụ"),
            F(category="Node",     field="service_dur",  status="ok",      source="NODES col 6",           value="",  note="Thời gian phục vụ tại node"),
            F(category="Node",     field="p, d (pairing)",status="ok",     source="NODES col 7, 8",        value="",  note="p=pickup partner, d=delivery partner"),
            # Ignored fields
            F(category="Bỏ qua",  field="LOCATION",     status="ignored", source="Header",                value=hdr.get("LOCATION",""), note="Không dùng trong thuật toán"),
            F(category="Bỏ qua",  field="COMMENT",      status="ignored", source="Header",                value=hdr.get("COMMENT",""),  note="Không dùng trong thuật toán"),
            F(category="Bỏ qua",  field="DISTRIBUTION", status="ignored", source="Header",                value=hdr.get("DISTRIBUTION",""), note="Không dùng trong thuật toán"),
            F(category="Bỏ qua",  field="TYPE",         status="ignored", source="Header",                value=hdr.get("TYPE",""),     note="Không dùng trong thuật toán"),
        ]

    elif dataset_type == "lilim":
        label = "Li & Lim"
        warnings = ["Tọa độ (x, y) là abstract — không hiển thị đúng trên bản đồ địa lý thực",
                    "Ma trận travel_time không có trong file, phải tính từ khoảng cách Euclidean"]
        first = lines[0].split() if lines else []
        cap_val = first[1] if len(first) > 1 else "?"
        veh_val = first[0] if first else "?"
        spd_val = first[2] if len(first) > 2 else "?"
        fields = [
            # Instance-level
            F(category="Instance", field="name",        status="derived", source="(tên file)",            value=file_path.stem,  note="Không có trong file, lấy từ tên file"),
            F(category="Instance", field="capacity",    status="ok",      source="Header dòng 1, cột 2",  value=cap_val,         note="Tải trọng tối đa mỗi xe"),
            F(category="Instance", field="horizon",     status="derived", source="depot tw_late",         value="",              note="Không có trong file, lấy từ time window của depot (node 0)"),
            F(category="Instance", field="travel_time", status="derived", source="(tính toán)",           value="Euclidean(x,y)",note="Không có trong file, tính từ khoảng cách Euclidean giữa các tọa độ"),
            # Node fields
            F(category="Node",     field="id",          status="ok",      source="col 0",                 value="",  note="ID node"),
            F(category="Node",     field="lat (← x)",   status="ok",      source="col 1",                 value="",  note="Tọa độ abstract x (không phải địa lý thực)"),
            F(category="Node",     field="lon (← y)",   status="ok",      source="col 2",                 value="",  note="Tọa độ abstract y (không phải địa lý thực)"),
            F(category="Node",     field="demand",      status="ok",      source="col 3",                 value="",  note="+demand pickup, −demand delivery"),
            F(category="Node",     field="tw_early",    status="ok",      source="col 4",                 value="",  note="Thời điểm sớm nhất phục vụ"),
            F(category="Node",     field="tw_late",     status="ok",      source="col 5",                 value="",  note="Thời điểm trễ nhất phục vụ"),
            F(category="Node",     field="service_dur", status="ok",      source="col 6",                 value="",  note="Thời gian phục vụ tại node"),
            F(category="Node",     field="p, d (pairing)",status="ok",    source="col 7, 8",              value="",  note="p=pickup partner, d=delivery partner"),
            # Ignored
            F(category="Bỏ qua",  field="num_vehicles",status="ignored", source="Header dòng 1, cột 1",  value=veh_val, note="Số xe gợi ý — thuật toán tự quyết định"),
            F(category="Bỏ qua",  field="speed",       status="ignored", source="Header dòng 1, cột 3",  value=spd_val, note="Vận tốc — không dùng (travel_time tính từ tọa độ)"),
        ]

    else:  # ropke_cordeau
        label = "Ropke & Cordeau"
        warnings = ["Tọa độ (x, y) là abstract — không hiển thị đúng trên bản đồ địa lý thực",
                    "Ma trận travel_time không có trong file, phải tính từ khoảng cách Euclidean"]
        hdr = {}
        for line in lines:
            if line.upper().startswith("NODE_COORD_SECTION"):
                break
            if ":" in line:
                k, v = line.split(":", 1)
                hdr[k.strip().upper()] = v.strip()
        fields = [
            # Instance-level
            F(category="Instance", field="name",        status="ok",      source="Header NAME",           value=hdr.get("NAME",""),       note="Tên instance"),
            F(category="Instance", field="capacity",    status="ok",      source="Header CAPACITY",       value=hdr.get("CAPACITY",""),   note="Tải trọng tối đa mỗi xe"),
            F(category="Instance", field="horizon",     status="derived", source="depot tw_late",         value="",                       note="Không có trong file, lấy từ time window của depot"),
            F(category="Instance", field="travel_time", status="derived", source="(tính toán)",           value=f"Euclidean (EDGE_WEIGHT_TYPE={hdr.get('EDGE_WEIGHT_TYPE','?')})", note="Tính từ khoảng cách Euclidean"),
            # From NODE_COORD_SECTION
            F(category="Node",     field="id",          status="ok",      source="NODE_COORD_SECTION col 0",  value="", note="ID node"),
            F(category="Node",     field="lat (← x)",   status="ok",      source="NODE_COORD_SECTION col 1",  value="", note="Tọa độ abstract x"),
            F(category="Node",     field="lon (← y)",   status="ok",      source="NODE_COORD_SECTION col 2",  value="", note="Tọa độ abstract y"),
            # From PICKUP_AND_DELIVERY_SECTION
            F(category="Node",     field="demand",      status="ok",      source="PICKUP_DELIVERY col 1",  value="", note="+demand pickup, −demand delivery"),
            F(category="Node",     field="tw_early",    status="ok",      source="PICKUP_DELIVERY col 2",  value="", note="Thời điểm sớm nhất phục vụ"),
            F(category="Node",     field="tw_late",     status="ok",      source="PICKUP_DELIVERY col 3",  value="", note="Thời điểm trễ nhất phục vụ"),
            F(category="Node",     field="service_dur", status="ok",      source="PICKUP_DELIVERY col 4",  value="", note="Thời gian phục vụ tại node"),
            F(category="Node",     field="p, d (pairing)",status="ok",    source="PICKUP_DELIVERY col 5,6",value="", note="Cặp pickup-delivery"),
            # Ignored
            F(category="Bỏ qua",  field="VEHICLES",    status="ignored", source="Header",                 value=hdr.get("VEHICLES",""), note="Số xe gợi ý — không dùng"),
            F(category="Bỏ qua",  field="TYPE",        status="ignored", source="Header",                 value=hdr.get("TYPE",""),     note="Loại bài toán — không dùng"),
            F(category="Bỏ qua",  field="DIMENSION",   status="ignored", source="Header",                 value=hdr.get("DIMENSION",""),note="Dùng để đọc file, không lưu vào Instance"),
        ]

    return {
        "instance_name": file_path.stem,
        "dataset_type": dataset_type,
        "dataset_type_label": label,
        "stats": stats,
        "errors": parse_errors,
        "warnings": warnings,
        "fields": fields,
    }


@router.get("/parse-report")
def get_parse_report(
    name: str = Query(...),
    _: User = Depends(get_current_user),
):
    """Return a structured field-mapping report for an instance file."""
    base = _instances_dir()
    candidates = (
        list(base.rglob(name))
        + list(base.rglob(f"{name}.txt"))
        + list(base.rglob(f"{name}.pdptw"))
        + list(base.rglob(f"{name}.csv"))
    )
    if not candidates:
        raise HTTPException(status_code=404, detail="Instance not found")
    return _build_parse_report(candidates[0])


# ── 14) get_instance_detail ───────────────────────────────────────────────────

@router.get("/detail")
def get_instance_detail(
    name: str = Query(..., description="Instance name (stem, không có extension)"),
    current: User = Depends(get_current_user),
):
    """
    Trả về thông tin chi tiết của một instance:
    tên, dataset, loại, số node/request, capacity, horizon, visibility, thời điểm parse.
    """
    base = _instances_dir()
    candidates: list[Path] = []
    for ext in _INSTANCE_EXTS:
        candidates += list(base.rglob(f"{name}{ext}"))
    candidates += list(base.rglob(name))
    if not candidates:
        raise HTTPException(status_code=404, detail="Instance không tồn tại")

    f = candidates[0]
    rel = f.relative_to(base)

    # Access check via top-level folder
    top = base / rel.parts[0]
    if not _can_access(top, current):
        raise HTTPException(status_code=403, detail="Không có quyền truy cập")

    header = _parse_header(f)
    upload_meta = _read_meta(f)

    # Detect dataset_type from format
    try:
        lines = [l.strip() for l in f.read_text(encoding="utf-8").splitlines() if l.strip()]
        fmt = _detect_fmt(lines)
        fmt_map = {"sartori": "sartori", "lilim": "lilim", "ropke_cordeau": "sartori"}
        dataset_type = fmt_map.get(fmt, "custom")
    except Exception:
        dataset_type = "custom"

    dataset_name = rel.parts[0] if len(rel.parts) > 1 else f.stem
    parsed_at = upload_meta.get("uploaded_at") or f.stat().st_mtime

    return {
        "code": "SUCCESS",
        "data": {
            "instance_name": f.stem,
            "filename": f.name,
            "path": rel.as_posix(),
            "dataset_name": dataset_name,
            "dataset_type": dataset_type,
            "variant_id": upload_meta.get("variant_id"),
            "num_nodes": header.get("num_nodes"),
            "num_requests": header.get("num_requests"),
            "capacity": header.get("capacity"),
            "horizon": header.get("horizon"),
            "visibility": upload_meta.get("visibility", "public"),
            "shared_with": upload_meta.get("shared_with", []),
            "parsed_at": parsed_at,
            "uploaded_by": upload_meta.get("uploaded_by"),
        },
    }


# ── 19) get_parse_report (dataset-level scan) ─────────────────────────────────

@router.get("/dataset-parse-report")
def get_dataset_parse_report(
    dataset_name: str = Query(..., description="Tên folder dataset"),
    current: User = Depends(get_current_user),
):
    """
    Quét toàn bộ file trong một dataset folder, thử parse từng file.
    Trả về: filename, status (success|failed), error_msg, num_nodes, num_requests.
    """
    base = _instances_dir()
    folder = base / dataset_name
    if not folder.exists() or not folder.is_dir():
        raise HTTPException(status_code=404, detail="Dataset không tồn tại")
    if not _can_access(folder, current):
        raise HTTPException(status_code=403, detail="Không có quyền truy cập")

    results = []
    for ext in _INSTANCE_EXTS:
        for f in sorted(folder.rglob(f"*{ext}")):
            if not f.is_file():
                continue
            header = _parse_header(f)
            if header:
                results.append({
                    "filename": f.name,
                    "status": "success",
                    "error_msg": None,
                    "num_nodes": header.get("num_nodes"),
                    "num_requests": header.get("num_requests"),
                })
            else:
                results.append({
                    "filename": f.name,
                    "status": "failed",
                    "error_msg": "Không parse được header",
                    "num_nodes": None,
                    "num_requests": None,
                })

    return {"code": "SUCCESS", "data": results}


# ── 20) check_compatibility ───────────────────────────────────────────────────

@router.get("/check-compatibility")
def check_compatibility(
    instance_name: str = Query(...),
    algorithm_id: int = Query(...),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """
    Kiểm tra thuật toán có thể chạy trên instance không,
    dựa trên dataset_type của instance và vrp_variant thuật toán hỗ trợ.
    """
    from app.db.models import Algorithm

    # Find instance file
    base = _instances_dir()
    candidates: list[Path] = []
    for ext in _INSTANCE_EXTS:
        candidates += list(base.rglob(f"{instance_name}{ext}"))
    if not candidates:
        raise HTTPException(status_code=404, detail="Instance không tồn tại")

    f = candidates[0]
    try:
        lines = [l.strip() for l in f.read_text(encoding="utf-8").splitlines() if l.strip()]
        fmt = _detect_fmt(lines)
    except Exception:
        fmt = "unknown"

    algo = db.query(Algorithm).filter(Algorithm.id == algorithm_id).first()
    if not algo:
        raise HTTPException(status_code=404, detail="Thuật toán không tồn tại")

    # System ALNS supports PDPTW (sartori, lilim, ropke_cordeau)
    pdptw_fmts = {"sartori", "lilim", "ropke_cordeau"}
    if algo.is_system:
        compatible = fmt in pdptw_fmts
        reason = None if compatible else f"ALNS chỉ hỗ trợ PDPTW (sartori/lilim/ropke_cordeau), instance này là '{fmt}'"
    else:
        # Custom algo: check vrp_variant field
        supported = algo.vrp_variant or ""  # e.g. "PDPTW" or comma-separated
        if not supported:
            compatible = True  # no restriction declared → assume compatible
            reason = "Thuật toán chưa khai báo variant, giả định tương thích"
        elif fmt in pdptw_fmts and "PDPTW" in supported.upper():
            compatible = True
            reason = None
        else:
            compatible = False
            reason = f"Thuật toán hỗ trợ '{supported}', instance là '{fmt}'"

    return {
        "code": "SUCCESS",
        "data": {
            "compatible": compatible,
            "reason": reason,
            "instance_format": fmt,
            "algorithm_variant": algo.vrp_variant,
        },
    }


# ── 39) get_baseline ─────────────────────────────────────────────────────────

@router.get("/baseline")
def get_baseline(
    instance_name: str = Query(..., description="Instance name"),
    _: User = Depends(get_current_user),
):
    """
    Trả về Best Known Solution (BKS) cho một instance.
    Đọc từ solutions/bks.dat.
    """
    import csv as _csv
    from functools import lru_cache

    bks_path = _REPO_ROOT / "solutions" / "bks.dat"
    if not bks_path.exists():
        raise HTTPException(status_code=404, detail="Không tìm thấy file bks.dat")

    entry = None
    with open(bks_path, newline="", encoding="utf-8") as fh:
        reader = _csv.DictReader(fh, delimiter=";")
        for row in reader:
            if row.get("instance", "").strip() == instance_name:
                try:
                    ref = row.get("reference", "").strip()
                    # Try to extract year from reference string (e.g. "Author2007")
                    year = None
                    for part in ref.split():
                        digits = "".join(c for c in part if c.isdigit())
                        if len(digits) == 4:
                            try:
                                year = int(digits)
                            except ValueError:
                                pass
                    entry = {
                        "instance_name": instance_name,
                        "bks_nv": int(row["vehicles"]),
                        "bks_cost": float(row["cost"]),
                        "source": ref or None,
                        "year": year,
                    }
                except (KeyError, ValueError):
                    pass
                break

    if not entry:
        raise HTTPException(status_code=404, detail=f"Không có BKS cho instance '{instance_name}'")

    return {"code": "SUCCESS", "data": entry}


# ── 40) get_dataset_statistic ─────────────────────────────────────────────────

@router.get("/dataset-statistic")
def get_dataset_statistic(
    dataset_name: str = Query(..., description="Tên dataset (tên folder)"),
    algorithm_ids: Optional[List[int]] = Query(None, description="Lọc theo algorithm IDs; bỏ trống = tất cả"),
    display_type: str = Query("table", pattern="^(table|polygon)$"),
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """
    Thống kê kết quả của các thuật toán trên từng instance trong một dataset.
    So sánh với BKS nếu có.
    """
    import csv as _csv

    base = _instances_dir()
    folder = base / dataset_name
    if not folder.exists() or not folder.is_dir():
        raise HTTPException(status_code=404, detail="Dataset không tồn tại")
    if not _can_access(folder, current):
        raise HTTPException(status_code=403, detail="Không có quyền truy cập")

    # Collect all instance names in the dataset folder
    instance_names: list[str] = []
    for ext in _INSTANCE_EXTS:
        for f in sorted(folder.rglob(f"*{ext}")):
            if f.is_file():
                instance_names.append(f.stem)
    instance_names = sorted(set(instance_names))

    # Load BKS
    bks_map: dict[str, dict] = {}
    bks_path = _REPO_ROOT / "solutions" / "bks.dat"
    if bks_path.exists():
        with open(bks_path, newline="", encoding="utf-8") as fh:
            reader = _csv.DictReader(fh, delimiter=";")
            for row in reader:
                name = row.get("instance", "").strip()
                try:
                    bks_map[name] = {
                        "bks_nv": int(row["vehicles"]),
                        "bks_cost": float(row["cost"]),
                    }
                except (KeyError, ValueError):
                    pass

    # Fetch algorithms
    algo_q = db.query(Algorithm)
    if algorithm_ids:
        algo_q = algo_q.filter(Algorithm.id.in_(algorithm_ids))
    algorithms = algo_q.all()
    algo_by_id = {a.id: a for a in algorithms}

    rows: list[DatasetStatInstanceRow] = []
    for iname in instance_names:
        bks = bks_map.get(iname)

        # Find all done solutions for this instance
        sols = (
            db.query(Solution)
            .join(Solution.job)
            .filter(Job.instance_name == iname, Job.status == "done")
            .all()
        )

        # Group by algorithm (via algorithm_id or method)
        from collections import defaultdict
        algo_results: dict[str, list[Solution]] = defaultdict(list)
        for sol in sols:
            if not sol.job:
                continue
            if algorithm_ids and sol.job.algorithm_id not in algorithm_ids:
                continue
            # Key: algorithm name
            if sol.job.algorithm_id and sol.job.algorithm_id in algo_by_id:
                key = algo_by_id[sol.job.algorithm_id].name
            else:
                key = sol.job.method or "unknown"
            algo_results[key].append(sol)

        if not algo_results and not bks:
            continue  # Skip instances with no results and no BKS

        results: list[DatasetStatAlgoResult] = []
        for algo_name, algo_sols in sorted(algo_results.items()):
            # Use the best solution (lowest total_distance)
            best = min(algo_sols, key=lambda s: s.total_distance)
            gap_pct = None
            if bks and bks["bks_cost"] > 0:
                gap_pct = round((best.total_distance - bks["bks_cost"]) / bks["bks_cost"] * 100, 2)
            results.append(DatasetStatAlgoResult(
                algorithm_name=algo_name,
                num_vehicles=best.num_vehicles,
                total_cost=round(best.total_distance, 4),
                gap_pct=gap_pct,
            ))

        rows.append(DatasetStatInstanceRow(
            instance_name=iname,
            bks_nv=bks["bks_nv"] if bks else None,
            bks_cost=bks["bks_cost"] if bks else None,
            results=results,
        ))

    return DatasetStatResponse(code="SUCCESS", data=rows)


@router.get("/{instance_name}", response_model=InstanceInfo)
def get_instance(instance_name: str, _: User = Depends(get_current_user)):
    base = _instances_dir()
    candidates = list(base.rglob(f"{instance_name}")) + list(base.rglob(f"{instance_name}.txt"))
    if not candidates:
        raise HTTPException(status_code=404, detail="Instance not found")
    f = candidates[0]
    meta = _parse_header(f)
    return InstanceInfo(name=instance_name, path=f.relative_to(base).as_posix(), **meta)
