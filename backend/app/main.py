from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db.models import Base  # noqa: F401 — imports trigger table registration for all models including token tables
from app.db.session import engine
from app.routers import auth, fleet, instances, jobs, orders, solutions, users
from app.routers import algorithms_api, metrics_api, variants, upload_analyze

# Create all tables on startup
Base.metadata.create_all(bind=engine)


def _migrate_add_columns() -> None:
    """Add new columns to existing tables that create_all won't touch."""
    from sqlalchemy import text, inspect

    inspector = inspect(engine)
    tables = {t for t in inspector.get_table_names()}

    with engine.connect() as conn:
        # algorithms: visibility + shared_with_ids
        if "algorithms" in tables:
            algo_cols = {c["name"] for c in inspector.get_columns("algorithms")}
            if "visibility" not in algo_cols:
                conn.execute(text("ALTER TABLE algorithms ADD COLUMN visibility VARCHAR(20) DEFAULT 'public'"))
            if "shared_with_ids" not in algo_cols:
                conn.execute(text("ALTER TABLE algorithms ADD COLUMN shared_with_ids TEXT"))

        # jobs: algorithm_id FK
        if "jobs" in tables:
            job_cols = {c["name"] for c in inspector.get_columns("jobs")}
            if "algorithm_id" not in job_cols:
                conn.execute(text("ALTER TABLE jobs ADD COLUMN algorithm_id INTEGER REFERENCES algorithms(id)"))

        # route_stops: time-window enrichment fields
        if "route_stops" in tables:
            stop_cols = {c["name"] for c in inspector.get_columns("route_stops")}
            for col, typedef in [
                ("stop_type",    "VARCHAR(10)"),
                ("arrival_time", "FLOAT"),
                ("service_start","FLOAT"),
                ("tw_early",     "FLOAT"),
                ("tw_late",      "FLOAT"),
            ]:
                if col not in stop_cols:
                    conn.execute(text(f"ALTER TABLE route_stops ADD COLUMN {col} {typedef}"))

        # solutions: total_cost + dataset_type
        if "solutions" in tables:
            sol_cols = {c["name"] for c in inspector.get_columns("solutions")}
            if "total_cost" not in sol_cols:
                conn.execute(text("ALTER TABLE solutions ADD COLUMN total_cost FLOAT"))
            if "dataset_type" not in sol_cols:
                conn.execute(text("ALTER TABLE solutions ADD COLUMN dataset_type VARCHAR(50)"))

        conn.commit()


_migrate_add_columns()


def _backfill_fingerprints() -> None:
    """
    Backfill file_size / num_lines / sha256 into existing .meta.json files
    that were written before deduplication was added. Runs once at startup,
    skips files that already have a fingerprint.
    """
    import hashlib as _hl
    import json as _json
    from pathlib import Path as _Path
    from app.core.config import settings as _s

    base = _Path(_s.INSTANCES_DIR)
    if not base.is_absolute():
        base = (_Path(__file__).resolve().parents[2] / base).resolve()
    if not base.exists():
        return

    _INSTANCE_EXTS = {".txt", ".pdptw", ".csv"}

    def _fp(content: bytes) -> dict:
        text = content.decode("utf-8", errors="replace")
        non_empty = [l for l in text.splitlines() if l.strip()]
        head10 = "\n".join(non_empty[:10]).encode("utf-8", errors="replace")
        return {
            "file_size": len(content),
            "num_lines": len(non_empty),
            "sha256_full": _hl.sha256(content).hexdigest(),
            "sha256_head10": _hl.sha256(head10).hexdigest(),
        }

    # Pass 1: add fingerprints to existing .meta.json that lack them
    for meta_path in base.rglob("*.meta.json"):
        if meta_path.name.startswith("."):
            continue
        try:
            meta = _json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if "sha256_full" in meta:
            continue  # already backfilled
        stem = meta_path.name  # "foo.txt.meta.json"
        instance_name = stem[: -len(".meta.json")]
        instance_path = meta_path.parent / instance_name
        if not instance_path.exists() or instance_path.suffix not in _INSTANCE_EXTS:
            continue
        try:
            meta.update(_fp(instance_path.read_bytes()))
            meta_path.write_text(_json.dumps(meta, ensure_ascii=False), encoding="utf-8")
        except Exception:
            continue

    # Pass 2: create .meta.json for instance files that have none at all
    for instance_path in base.rglob("*"):
        if instance_path.suffix not in _INSTANCE_EXTS:
            continue
        if "_pending" in instance_path.parts:
            continue
        meta_path = instance_path.with_suffix(instance_path.suffix + ".meta.json")
        if meta_path.exists():
            continue
        try:
            meta = _fp(instance_path.read_bytes())
            meta_path.write_text(_json.dumps(meta, ensure_ascii=False), encoding="utf-8")
        except Exception:
            continue


_backfill_fingerprints()

app = FastAPI(
    title="PDPTW Logistics API",
    description="B2B Logistics System powered by ALNS PDPTW Solver",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(fleet.router)
app.include_router(instances.router)
app.include_router(jobs.router)
app.include_router(solutions.router)
app.include_router(orders.router)
app.include_router(algorithms_api.router)
app.include_router(metrics_api.router)
app.include_router(variants.router)
app.include_router(upload_analyze.router)


@app.get("/health")
def health():
    return {"status": "ok"}
