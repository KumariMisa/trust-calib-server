from pydantic import BaseModel, Field, field_validator
from datetime import datetime
import re

class UserRegister(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    username: str = Field(..., min_length=3, max_length=20)
    password: str = Field(..., min_length=8)

    @field_validator('username')
    @classmethod
    def validate_username(cls, v: str) -> str:
        # Enforce lowercase
        v = v.lower()
        # Enforce letters, numbers, underscores only, no spaces
        if not re.match(r'^[a-z0-9_]+$', v):
            raise ValueError('Username can only contain lowercase letters, numbers, and underscores')
        return v

class UserLogin(BaseModel):
    username: str
    password: str

class UserOut(BaseModel):
    id: str
    name: str
    username: str
    created_at: datetime

    class Config:
        from_attributes = True
