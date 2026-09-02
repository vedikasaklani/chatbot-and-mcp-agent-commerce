from fastapi import APIRouter, Depends, HTTPException
from api.dependencies import oauth_scheme1
from database.database import get_db
from sqlalchemy.orm import Session
import database.database_models as database_models
from utils.auth import get_password_hash, verify_password
from database.database_models import User
from models import RegisterRequest
from security import create_access_token
from fastapi.security import OAuth2PasswordRequestForm

router=APIRouter(
    prefix="/auth", tags=["authentication"]
)

@router.post("/register")
def register(data:RegisterRequest, db: Session = Depends(get_db)):
    email = data.resolved_email
    if not email:
        raise HTTPException(status_code=400, detail="Email is required")

    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=400, detail="Email already exists")

    user = User(email=email, hashed_password=get_password_hash(data.password))
    db.add(user)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=400, detail="Could not create user")

    db.refresh(user)
    return {
        "access_token": create_access_token(str(user.id)),
        "token_type": "bearer"
    }


@router.post("/login")
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    user = db.query(database_models.User).filter(
        database_models.User.email == form_data.username
    ).first()

    if not user or not verify_password(
        form_data.password,
        user.hashed_password
    ):
        raise HTTPException(
            status_code=401,
            detail="Incorrect email or password"
        )

    token = create_access_token(user.id)

    return {
        "access_token": token,
        "token_type": "bearer"
    }
