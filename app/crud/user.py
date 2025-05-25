from sqlalchemy.orm import Session
import os
from dotenv import load_dotenv
import logging

from app.models.user import User
from app.schemas.user import UserCreate
from app.core.security import get_password_hash, verify_password
from app.utils.aptos import create_aptos_account

load_dotenv()

# Default admin credentials
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "adminpassword")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@example.com")

logger = logging.getLogger(__name__)

def get_user(db: Session, user_id: int):
    """Get a user by ID."""
    return db.query(User).filter(User.id == user_id).first()

def get_user_by_username(db: Session, username: str):
    """Get a user by username."""
    return db.query(User).filter(User.username == username).first()

def get_user_by_email(db: Session, email: str):
    """Get a user by email."""
    return db.query(User).filter(User.email == email).first()

def get_users(db: Session, skip: int = 0, limit: int = 100):
    """Get a list of users."""
    return db.query(User).offset(skip).limit(limit).all()

def create_user(db: Session, user: UserCreate):
    """Create a new user."""
    # Check if username or email already exists
    if get_user_by_username(db, user.username):
        return None
    if get_user_by_email(db, user.email):
        return None
    
    # Create an Aptos account for the user
    aptos_account = create_aptos_account()
    
    # Create the user in the database
    hashed_password = get_password_hash(user.password)
    db_user = User(
        username=user.username,
        email=user.email,
        hashed_password=hashed_password,
        aptos_address=aptos_account["address"],
        aptos_private_key=aptos_account["private_key"],
        is_admin=False
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def create_admin_user(db: Session):
    """Create the admin user if it doesn't exist."""
    admin = get_user_by_username(db, ADMIN_USERNAME)
    if admin:
        # Check if the existing admin has a mock address (0x1)
        if admin.aptos_address == "0x1":
            logger.info("Admin has a mock Aptos address. Generating a new real Aptos account...")
            try:
                # Create a new real Aptos account
                aptos_account = create_aptos_account()
                
                # Update the admin user with the new account
                admin.aptos_address = aptos_account["address"]
                admin.aptos_private_key = aptos_account["private_key"]
                db.commit()
                db.refresh(admin)
                logger.info(f"Updated admin Aptos account to: {admin.aptos_address}")
            except Exception as e:
                logger.error(f"Failed to update admin Aptos account: {str(e)}")
                # If we can't create a new account, continue with the existing one
        return admin
    
    # Admin doesn't exist, create a new one with a real Aptos account
    try:
        # Create an Aptos account for the admin
        aptos_account = create_aptos_account()
        logger.info(f"Created admin Aptos account: {aptos_account['address']} (funded with 10M octas)")
        
        # Create the admin user
        hashed_password = get_password_hash(ADMIN_PASSWORD)
        admin_user = User(
            username=ADMIN_USERNAME,
            email=ADMIN_EMAIL,
            hashed_password=hashed_password,
            aptos_address=aptos_account["address"],
            aptos_private_key=aptos_account["private_key"],
            is_admin=True
        )
        db.add(admin_user)
        db.commit()
        db.refresh(admin_user)
        return admin_user
    except Exception as e:
        logger.error(f"Failed to create admin user: {str(e)}")
        # If we failed to create a real Aptos account, raise the exception
        raise

def authenticate_user(db: Session, username: str, password: str):
    """Authenticate a user."""
    user = get_user_by_username(db, username)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user

def update_password(db: Session, user_id: int, new_password: str):
    """Update a user's password."""
    user = get_user(db, user_id)
    if not user:
        return None
    
    hashed_password = get_password_hash(new_password)
    user.hashed_password = hashed_password
    db.commit()
    db.refresh(user)
    return user 