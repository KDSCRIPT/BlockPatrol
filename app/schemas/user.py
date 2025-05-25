from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime

class UserBase(BaseModel):
    username: str
    email: EmailStr

class UserCreate(UserBase):
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

class UserResetPassword(BaseModel):
    username: str
    old_password: str
    new_password: str

class UserInDB(UserBase):
    id: int
    aptos_address: str
    is_active: bool
    is_admin: bool
    created_at: datetime
    
    class Config:
        orm_mode = True

class UserResponse(UserBase):
    id: int
    aptos_address: str
    is_active: bool
    is_admin: bool
    
    class Config:
        orm_mode = True

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    aptos_address: Optional[str] = None

class TokenData(BaseModel):
    username: Optional[str] = None 