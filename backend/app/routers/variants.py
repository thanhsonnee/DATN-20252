"""
VRP Variant management.
Seeds built-in PDPTW variant on first request.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, selectinload

from app.core.deps import get_current_user
from app.db.models import User, VrpConstraint, VrpVariant
from app.db.session import get_db
from app.models.schemas import VrpVariantDetailOut, VrpVariantOut

router = APIRouter(prefix="/variants", tags=["variants"])

_SEED_VARIANTS = [
    {
        "name": "PDPTW",
        "description": (
            "Pickup and Delivery Problem with Time Windows. "
            "Mỗi yêu cầu gồm một điểm lấy hàng (pickup) và một điểm giao hàng (delivery) "
            "phải được phục vụ bởi cùng một xe, theo thứ tự pickup → delivery, "
            "trong khung thời gian quy định."
        ),
        "paper_link": "https://doi.org/10.1287/trsc.1030.0052",
        "is_active": True,
        "constraints": [
            {
                "constraint_id": "time_window",
                "description": "Mỗi điểm dừng phải được phục vụ trong khung thời gian [e_i, l_i].",
                "constraint_statement": r"e_i \leq s_i \leq l_i \quad \forall i \in N",
            },
            {
                "constraint_id": "capacity",
                "description": "Tổng tải trọng trên xe tại mọi thời điểm không vượt quá sức chứa Q.",
                "constraint_statement": r"\sum_{i \in \text{route}} q_i \leq Q",
            },
            {
                "constraint_id": "precedence",
                "description": "Điểm pickup phải được thăm trước điểm delivery tương ứng.",
                "constraint_statement": r"t_{p(i)} < t_{d(i)} \quad \forall i \in R",
            },
            {
                "constraint_id": "pairing",
                "description": "Pickup và delivery của cùng một yêu cầu phải do cùng một xe phục vụ.",
                "constraint_statement": r"k_{p(i)} = k_{d(i)} \quad \forall i \in R",
            },
            {
                "constraint_id": "depot",
                "description": "Mỗi tuyến bắt đầu và kết thúc tại kho (depot 0) trong khung thời gian của kho.",
                "constraint_statement": r"e_0 \leq t_{\text{start}} \leq t_{\text{end}} \leq l_0",
            },
        ],
    },
    {
        "name": "CVRP",
        "description": (
            "Capacitated Vehicle Routing Problem. "
            "Bài toán định tuyến xe với ràng buộc sức chứa. "
            "Không có ràng buộc thời gian."
        ),
        "paper_link": None,
        "is_active": True,
        "constraints": [
            {
                "constraint_id": "capacity",
                "description": "Tổng tải trọng trên xe không vượt quá sức chứa Q.",
                "constraint_statement": r"\sum_{i \in \text{route}} q_i \leq Q",
            },
            {
                "constraint_id": "depot",
                "description": "Mỗi tuyến bắt đầu và kết thúc tại kho.",
                "constraint_statement": r"\text{route}[0] = \text{route}[-1] = 0",
            },
        ],
    },
]


def _seed_variants(db: Session) -> None:
    """Insert built-in variants if not present."""
    for v_data in _SEED_VARIANTS:
        existing = db.query(VrpVariant).filter(VrpVariant.name == v_data["name"]).first()
        if existing:
            continue
        variant = VrpVariant(
            name=v_data["name"],
            description=v_data["description"],
            paper_link=v_data["paper_link"],
            is_active=v_data["is_active"],
        )
        db.add(variant)
        db.flush()
        for c_data in v_data["constraints"]:
            db.add(VrpConstraint(
                variant_id=variant.id,
                constraint_id=c_data["constraint_id"],
                description=c_data["description"],
                constraint_statement=c_data["constraint_statement"],
            ))
    db.commit()


# ── 41) get_variant_list ──────────────────────────────────────────────────────

@router.get("/", response_model=list[VrpVariantOut])
def list_variants(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    _seed_variants(db)
    return db.query(VrpVariant).order_by(VrpVariant.id.asc()).all()


# ── 42) get_variant_detail ────────────────────────────────────────────────────

@router.get("/{variant_id}", response_model=VrpVariantDetailOut)
def get_variant(
    variant_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    _seed_variants(db)
    variant = (
        db.query(VrpVariant)
        .options(selectinload(VrpVariant.constraints))
        .filter(VrpVariant.id == variant_id)
        .first()
    )
    if not variant:
        raise HTTPException(status_code=404, detail="Không tìm thấy variant")
    return variant
