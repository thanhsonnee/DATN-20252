from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_admin
from app.core.security import hash_password, verify_password
from app.db.models import (
    EmailVerificationToken,
    PasswordResetToken,
    RefreshToken,
    User,
    UserRole,
)
from app.db.session import get_db
from app.models.schemas import (
    ChangePasswordRequest,
    UserCreate,
    UserOut,
    UserUpdate,
)

router = APIRouter(prefix="/users", tags=["users"])


def _ok(message: str = "", data=None) -> dict:
    return {"code": "SUCCESS", "message": message, "data": data}


# ── Fixed-path routes first (must come before /{user_id}) ────────────────────

@router.get("/me", response_model=UserOut)
def get_me(current: User = Depends(get_current_user)):
    """Lấy thông tin người dùng hiện tại."""
    return current


@router.patch("/me")
def update_me(
    body: UserUpdate,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """Người dùng tự cập nhật thông tin của mình (chỉ full_name)."""
    data = body.model_dump(exclude_none=True)
    # Non-admin can only update full_name
    data = {k: v for k, v in data.items() if k == "full_name"}

    for field, value in data.items():
        setattr(current, field, value)
    db.commit()
    db.refresh(current)

    return _ok(
        data={
            "id": current.id,
            "email": current.email,
            "full_name": current.full_name,
            "role": current.role.value,
            "is_active": current.is_active,
            "registered_at": current.created_at.isoformat(),
        }
    )


# ── 10) change_password ────────────────────────────────────────────────────────

@router.post("/me/change-password")
def change_password(
    body: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """Đổi mật khẩu — yêu cầu mật khẩu cũ."""
    if not verify_password(body.old_password, current.hashed_password):
        raise HTTPException(status_code=400, detail="Mật khẩu cũ không đúng")

    current.hashed_password = hash_password(body.new_password)
    db.commit()
    return _ok(message="Đổi mật khẩu thành công")


# ── Admin-only list & create ───────────────────────────────────────────────────

@router.get("/", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    return db.query(User).all()


@router.get("/by-email", response_model=UserOut)
def get_user_by_email(
    email: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng với email này")
    return user


@router.post("/", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    body: UserCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Admin tạo người dùng trực tiếp (không cần xác minh email)."""
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(
        email=body.email,
        hashed_password=hash_password(body.password),
        full_name=body.full_name,
        role=body.role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# ── 8) get_user_info by ID ─────────────────────────────────────────────────────

@router.get("/{user_id}")
def get_user_info(
    user_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """
    Lấy thông tin người dùng theo ID.
    - Người dùng thường chỉ xem được chính mình.
    - Admin xem được bất kỳ ai.
    """
    if current.role != UserRole.admin and current.id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Không có quyền truy cập")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng")

    return _ok(
        message="Lấy thông tin người dùng thành công",
        data={
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role.value,
            "is_active": user.is_active,
            "registered_at": user.created_at.isoformat(),
        }
    )


# ── 9) set_user_info ───────────────────────────────────────────────────────────

@router.patch("/{user_id}")
def update_user(
    user_id: int,
    body: UserUpdate,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """
    Cập nhật thông tin người dùng.
    - Người dùng thường chỉ cập nhật được chính mình (full_name).
    - Admin cập nhật được bất kỳ ai (full_name, role, is_active).
    """
    if current.role != UserRole.admin and current.id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Không có quyền truy cập")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng")

    data = body.model_dump(exclude_none=True)

    # Non-admin can only update full_name
    if current.role != UserRole.admin:
        data = {k: v for k, v in data.items() if k == "full_name"}

    # Admin cannot demote themselves
    if current.role == UserRole.admin and current.id == user_id and "role" in data and data["role"] != UserRole.admin:
        raise HTTPException(status_code=400, detail="Admin không thể tự hạ role của chính mình")

    if "password" in data:
        user.hashed_password = hash_password(data.pop("password"))
    for field, value in data.items():
        setattr(user, field, value)

    db.commit()
    db.refresh(user)

    return _ok(
        data={
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role.value,
            "is_active": user.is_active,
            "registered_at": user.created_at.isoformat(),
        }
    )


# ── 11) delete_user ────────────────────────────────────────────────────────────

@router.delete("/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Xoá người dùng — chỉ admin."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng")
    # Clean up token rows first (in case DB-level cascade is not yet active)
    db.query(EmailVerificationToken).filter(EmailVerificationToken.user_id == user_id).delete()
    db.query(RefreshToken).filter(RefreshToken.user_id == user_id).delete()
    db.query(PasswordResetToken).filter(PasswordResetToken.user_id == user_id).delete()
    db.delete(user)
    db.commit()
    return _ok(message="Xoá người dùng thành công")
