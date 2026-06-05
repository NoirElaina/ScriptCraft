from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    created_at: datetime


class RegisterRequest(BaseModel):
    username: str = Field(min_length=2, max_length=80)
    email: str = Field(min_length=3, max_length=180)
    password: str = Field(min_length=6, max_length=128)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        text = value.strip().lower()
        if "@" not in text or "." not in text.rsplit("@", 1)[-1]:
            raise ValueError("邮箱格式不正确")
        return text


class LoginRequest(BaseModel):
    identifier: str = Field(min_length=1, max_length=180)
    password: str = Field(min_length=1, max_length=128)


class AuthTokenResponse(BaseModel):
    token: str
    expires_at: datetime
    user: UserResponse
