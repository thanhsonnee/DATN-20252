from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_researcher_or_above
from app.db.models import User, Vehicle
from app.db.session import get_db
from app.models.schemas import VehicleCreate, VehicleOut, VehicleUpdate

router = APIRouter(prefix="/fleet", tags=["fleet"])


@router.get("/", response_model=list[VehicleOut])
def list_vehicles(db: Session = Depends(get_db), _: User = Depends(require_researcher_or_above)):
    return db.query(Vehicle).order_by(Vehicle.id).all()


@router.post("/", response_model=VehicleOut, status_code=status.HTTP_201_CREATED)
def create_vehicle(body: VehicleCreate, db: Session = Depends(get_db), _: User = Depends(require_researcher_or_above)):
    if db.query(Vehicle).filter(Vehicle.plate == body.plate).first():
        raise HTTPException(status_code=400, detail="Plate already exists")
    v = Vehicle(**body.model_dump())
    db.add(v)
    db.commit()
    db.refresh(v)
    return v


@router.patch("/{vehicle_id}", response_model=VehicleOut)
def update_vehicle(vehicle_id: int, body: VehicleUpdate, db: Session = Depends(get_db), _: User = Depends(require_researcher_or_above)):
    v = db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()
    if not v:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(v, field, value)
    db.commit()
    db.refresh(v)
    return v


@router.delete("/{vehicle_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_vehicle(vehicle_id: int, db: Session = Depends(get_db), _: User = Depends(require_researcher_or_above)):
    v = db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()
    if not v:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    db.delete(v)
    db.commit()
