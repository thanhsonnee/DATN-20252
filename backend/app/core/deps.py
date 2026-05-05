from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.db.models import User, UserRole
from app.db.session import get_db

bearer = HTTPBearer()


def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    payload = decode_token(creds.credentials)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user = db.query(User).filter(User.email == payload.get("sub")).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    return user


def require_algo_tester(user: User = Depends(get_current_user)) -> User:
    if user.role not in (UserRole.admin, UserRole.algo_tester):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Algo tester or Admin required")
    return user


def require_dataset_provider(user: User = Depends(get_current_user)) -> User:
    if user.role not in (UserRole.admin, UserRole.dataset_provider):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Dataset provider or Admin required")
    return user


def require_metric_provider(user: User = Depends(get_current_user)) -> User:
    if user.role not in (UserRole.admin, UserRole.metric_provider):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Metric provider or Admin required")
    return user


def require_any_role(user: User = Depends(get_current_user)) -> User:
    """Any authenticated, active user."""
    return user


# Legacy aliases kept for routers that still reference them
require_researcher_or_above = require_algo_tester
require_manager = require_admin
