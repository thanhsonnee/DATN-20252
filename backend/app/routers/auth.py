from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    generate_secure_token,
    hash_password,
    verify_password,
)
from app.db.models import (
    EmailVerificationToken,
    PasswordResetToken,
    RefreshToken,
    User,
    UserRole,
)
from app.db.session import get_db
from app.models.schemas import (
    ForgotPasswordRequest,
    LoginRequest,
    RefreshTokenRequest,
    RegisterRequest,
    ResetPasswordRequest,
)
from app.services import email_service

router = APIRouter(prefix="/auth", tags=["auth"])


def _ok(message: str = "", data: dict | None = None) -> dict:
    return {"code": "SUCCESS", "message": message, "data": data or {}}


# ── 1) Sign up ─────────────────────────────────────────────────────────────────

@router.post("/signup", status_code=status.HTTP_201_CREATED)
def signup(body: RegisterRequest, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(status_code=400, detail="Email đã được sử dụng")

    user = User(
        email=body.email,
        hashed_password=hash_password(body.password),
        full_name=body.full_name or body.email.split("@")[0],
        role=body.role or UserRole.algo_tester,
        is_active=False,  # inactive until email verified
    )
    db.add(user)
    db.flush()  # get user.id without committing

    token_str = generate_secure_token()
    expires = datetime.utcnow() + timedelta(hours=settings.EMAIL_VERIFICATION_EXPIRE_HOURS)
    verification = EmailVerificationToken(
        user_id=user.id,
        token=token_str,
        expires_at=expires,
    )
    db.add(verification)
    db.commit()
    db.refresh(user)

    try:
        email_service.send_verification_email(user.email, token_str)
    except Exception:
        pass  # don't fail registration if email sending errors

    return _ok(
        message="Vui lòng kiểm tra email để xác minh tài khoản",
        data={"user_id": user.id, "email": user.email},
    )


# ── 2) Verify email ────────────────────────────────────────────────────────────

@router.get("/verify-email")
def verify_email(token: str = Query(...), db: Session = Depends(get_db)):
    record = (
        db.query(EmailVerificationToken)
        .filter(
            EmailVerificationToken.token == token,
            EmailVerificationToken.used == False,  # noqa: E712
        )
        .first()
    )
    if not record:
        raise HTTPException(status_code=400, detail="Token không hợp lệ hoặc đã được sử dụng")
    if record.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Token đã hết hạn")

    record.used = True
    user = db.query(User).filter(User.id == record.user_id).first()
    if user:
        user.is_active = True
    db.commit()

    return _ok(message="Xác minh thành công")


# ── 3) Login ───────────────────────────────────────────────────────────────────

@router.post("/login")
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user: User | None = db.query(User).filter(User.email == body.email).first()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Email hoặc mật khẩu không đúng")

    # Check if email is unverified (has unused verification token)
    pending_verification = (
        db.query(EmailVerificationToken)
        .filter(
            EmailVerificationToken.user_id == user.id,
            EmailVerificationToken.used == False,  # noqa: E712
        )
        .first()
    )
    if pending_verification and not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tài khoản chưa xác minh email. Vui lòng kiểm tra hộp thư.",
        )

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tài khoản bị vô hiệu hóa")

    access_token = create_access_token(subject=user.email, role=user.role.value)
    refresh_token_str = create_refresh_token(subject=user.email, role=user.role.value)

    # Persist refresh token
    expires = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    db.add(RefreshToken(user_id=user.id, token=refresh_token_str, expires_at=expires))
    db.commit()

    # Flat response — keeps frontend compatible; refresh_token is bonus field
    return {
        "access_token": access_token,
        "refresh_token": refresh_token_str,
        "token_type": "bearer",
        "user_id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role.value,
    }


# ── 4) Logout ──────────────────────────────────────────────────────────────────

@router.post("/logout")
def logout(body: RefreshTokenRequest, db: Session = Depends(get_db)):
    record = (
        db.query(RefreshToken)
        .filter(RefreshToken.token == body.refresh_token, RefreshToken.revoked == False)  # noqa: E712
        .first()
    )
    if record:
        record.revoked = True
        db.commit()
    return _ok(message="Đăng xuất thành công. Refresh token đã bị thu hồi.")


# ── 5) Forgot password ─────────────────────────────────────────────────────────

@router.post("/forgot-password")
def forgot_password(body: ForgotPasswordRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email).first()
    if user and user.is_active:
        # Invalidate existing reset tokens
        db.query(PasswordResetToken).filter(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used == False,  # noqa: E712
        ).update({"used": True})

        token_str = generate_secure_token()
        expires = datetime.utcnow() + timedelta(hours=settings.PASSWORD_RESET_EXPIRE_HOURS)
        db.add(PasswordResetToken(user_id=user.id, token=token_str, expires_at=expires))
        db.commit()

        try:
            email_service.send_password_reset_email(user.email, token_str)
        except Exception:
            pass

    # Always return success to prevent email enumeration
    return _ok(message="Email đặt lại mật khẩu đã được gửi (nếu tài khoản tồn tại)")


# ── 6) Reset password ──────────────────────────────────────────────────────────

@router.post("/reset-password")
def reset_password(body: ResetPasswordRequest, db: Session = Depends(get_db)):
    record = (
        db.query(PasswordResetToken)
        .filter(
            PasswordResetToken.token == body.token,
            PasswordResetToken.used == False,  # noqa: E712
        )
        .first()
    )
    if not record:
        raise HTTPException(status_code=400, detail="Token không hợp lệ hoặc đã được sử dụng")
    if record.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Token đã hết hạn")

    user = db.query(User).filter(User.id == record.user_id).first()
    if not user:
        raise HTTPException(status_code=400, detail="Người dùng không tồn tại")

    user.hashed_password = hash_password(body.new_password)
    record.used = True

    # Revoke all refresh tokens for this user (force re-login)
    db.query(RefreshToken).filter(
        RefreshToken.user_id == user.id,
        RefreshToken.revoked == False,  # noqa: E712
    ).update({"revoked": True})

    db.commit()
    return _ok(message="Mật khẩu đã được đặt lại thành công")


# ── 7) Refresh token ───────────────────────────────────────────────────────────

@router.post("/refresh-token")
def refresh_token(body: RefreshTokenRequest, db: Session = Depends(get_db)):
    payload = decode_refresh_token(body.refresh_token)
    if not payload:
        raise HTTPException(status_code=401, detail="Refresh token không hợp lệ")

    record = (
        db.query(RefreshToken)
        .filter(
            RefreshToken.token == body.refresh_token,
            RefreshToken.revoked == False,  # noqa: E712
        )
        .first()
    )
    if not record:
        raise HTTPException(status_code=401, detail="Refresh token đã bị thu hồi hoặc không tồn tại")
    if record.expires_at < datetime.utcnow():
        raise HTTPException(status_code=401, detail="Refresh token đã hết hạn")

    user = db.query(User).filter(User.id == record.user_id, User.is_active == True).first()  # noqa: E712
    if not user:
        raise HTTPException(status_code=401, detail="Người dùng không tồn tại hoặc bị vô hiệu hóa")

    # Rotate: revoke old token, issue new pair
    record.revoked = True

    new_access = create_access_token(subject=user.email, role=user.role.value)
    new_refresh_str = create_refresh_token(subject=user.email, role=user.role.value)
    expires = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    db.add(RefreshToken(user_id=user.id, token=new_refresh_str, expires_at=expires))
    db.commit()

    return _ok(
        data={
            "access_token": new_access,
            "refresh_token": new_refresh_str,
            "token_type": "bearer",
        }
    )
