from pydantic import BaseModel


class ClassOut(BaseModel):
    id: int
    display_name: str

    class Config:
        from_attributes = True


class LoginRequest(BaseModel):
    username: str
    password: str
    class_id: int | None = None  # required for student login, ignored for teacher/admin


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class MeOut(BaseModel):
    id: int
    username: str
    full_name: str
    role: str
    homeroom_class_ids: list[int] = []

    class Config:
        from_attributes = True


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str
