from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_researcher_or_above
from app.db.models import Order, User, UserRole
from app.db.session import get_db
from app.models.schemas import OrderCreate, OrderOut, OrderUpdate

router = APIRouter(prefix="/orders", tags=["orders"])


@router.get("/", response_model=list[OrderOut])
def list_orders(db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    q = db.query(Order)
    if current.role == UserRole.customer:
        q = q.filter(Order.customer_id == current.id)
    return q.order_by(Order.created_at.desc()).all()


@router.post("/", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
def create_order(body: OrderCreate, db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    order = Order(customer_id=current.id, **body.model_dump())
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


@router.get("/{order_id}", response_model=OrderOut)
def get_order(order_id: int, db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if current.role == UserRole.customer and order.customer_id != current.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    return order


@router.patch("/{order_id}", response_model=OrderOut)
def update_order(
    order_id: int,
    body: OrderUpdate,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    # Only researcher/manager can change status; customer can only update description
    if current.role == UserRole.customer:
        if body.status is not None:
            raise HTTPException(status_code=403, detail="Customers cannot change order status")
        if order.customer_id != current.id:
            raise HTTPException(status_code=403, detail="Forbidden")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(order, field, value)
    db.commit()
    db.refresh(order)
    return order


@router.delete("/{order_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_order(order_id: int, db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if current.role == UserRole.customer and order.customer_id != current.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    db.delete(order)
    db.commit()
