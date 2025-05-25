from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.security import create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES
from app.crud.user import authenticate_user, create_user, update_password, get_user_by_username
from app.db.database import get_db
from app.schemas.user import Token, UserCreate, UserResponse, UserResetPassword
from app.core.deps import get_current_active_user
from app.models.user import User

router = APIRouter()

@router.post("/signup", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def signup(user: UserCreate, db: Session = Depends(get_db)):
    """
    Create a new user with an Aptos account funded with 10 million octas.
    """
    db_user = create_user(db, user)
    if db_user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username or email already registered"
        )
    print(f"Created user Aptos account: {db_user.aptos_address} (funded with 10M octas)")
    return db_user

@router.post("/login", response_model=Token)
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """
    OAuth2 compatible token login, get an access token for future requests.
    """
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer", "aptos_address": user.aptos_address}

@router.post("/reset-password", response_model=UserResponse)
def reset_password(
    reset_data: UserResetPassword, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Reset user password.
    """
    # Verify the old password
    user = authenticate_user(db, current_user.username, reset_data.old_password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect password"
        )
    
    # Update the password
    updated_user = update_password(db, user.id, reset_data.new_password)
    if not updated_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return updated_user

@router.post("/logout")
def logout(current_user: User = Depends(get_current_active_user)):
    """
    Logout endpoint (client-side only, JWT cannot be invalidated on server).
    """
    return {"detail": "Successfully logged out"} 