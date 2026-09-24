from fastapi import APIRouter, Depends, HTTPException, status
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.security import create_access_token, create_refresh_token, decode_token, hash_password, verify_password
from app.db.base import get_db
from app.dependencies import get_current_user
from app.models.org import Class
from app.models.user import User, UserRole
from app.schemas.auth import ChangePasswordRequest, ClassOut, LoginRequest, MeOut, RefreshRequest, TokenPair

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.get("/classes", response_model=list[ClassOut])
def list_classes(db: Session = Depends(get_db)):
    return db.query(Class).order_by(Class.grade_level, Class.label).all()


@router.post("/login", response_model=TokenPair)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == body.username).first()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Login yoki parol xato")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Hisob faol emas")

    if user.role.value == "student":
        if body.class_id is None or user.student is None or user.student.class_id != body.class_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sinf mos kelmadi")

    access = create_access_token(user.id, user.role.value)
    refresh = create_refresh_token(user.id, user.role.value)
    return TokenPair(access_token=access, refresh_token=refresh)


@router.post("/refresh", response_model=TokenPair)
def refresh(body: RefreshRequest, db: Session = Depends(get_db)):
    try:
        payload = decode_token(body.refresh_token)
        if payload.get("type") != "refresh":
            raise JWTError("wrong token type")
        user_id = int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token")

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")

    access = create_access_token(user.id, user.role.value)
    new_refresh = create_refresh_token(user.id, user.role.value)
    return TokenPair(access_token=access, refresh_token=new_refresh)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(_user: User = Depends(get_current_user)):
    # Tokens are stateless JWTs with no server-side session store in v1 —
    # logout is enforced client-side by discarding them. This endpoint just
    # validates the caller is authenticated before they do so.
    return None


@router.get("/me", response_model=MeOut)
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    homeroom_class_ids: list[int] = []
    if user.role == UserRole.teacher and user.teacher is not None:
        homeroom_class_ids = [
            c.id for c in db.query(Class).filter_by(homeroom_teacher_id=user.teacher.id).all()
        ]
    return MeOut(
        id=user.id,
        username=user.username,
        full_name=user.full_name,
        role=user.role.value,
        homeroom_class_ids=homeroom_class_ids,
    )


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    body: ChangePasswordRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Joriy parol xato")
    if len(body.new_password) < 6:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Yangi parol kamida 6 belgidan iborat bo'lishi kerak")
    user.password_hash = hash_password(body.new_password)
    db.commit()
    return None
