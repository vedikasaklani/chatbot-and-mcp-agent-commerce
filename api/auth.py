import requests
from fastapi import APIRouter, Depends, HTTPException,Query, Form
from api.dependencies import oauth_scheme1
from database.database import get_db
from sqlalchemy.orm import Session
import database.database_models as database_models
from utils.auth import get_password_hash, verify_password
from database.database_models import User
from database.models import RegisterRequest
from security import create_access_token
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import RedirectResponse

from dotenv import load_dotenv
load_dotenv()
import os

WORKOS_API_KEY = os.getenv("WORKOS_API_KEY")

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


@router.get("/workos/login")
def workos_login_page(
    external_auth_id: str = Query(...)
):
    #the frontend login ui workos should redirect to
    frontend_login_url = (
        "https://agent-commerce-payout-automation.onrender.com/"
        f"?external_auth_id={external_auth_id}"
    )

    return RedirectResponse(
        url=frontend_login_url,
        status_code=302
    )


@router.post("/workos/login")
def workos_login(
    external_auth_id: str = Form(...),
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    #authenticate using existing : 

    user = (
        db.query(database_models.User)
        .filter(database_models.User.email == username)
        .first()
    )

    if not user or not verify_password(
        password,
        user.hashed_password
    ):
        raise HTTPException(
            status_code=401,
            detail="Incorrect email or password"
        )

    #authentication with workos

    if not WORKOS_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="WORKOS_API_KEY is not configured"
        )

    workos_response = requests.post(
        "https://api.workos.com/authkit/oauth2/complete",
        headers={
            "Authorization": f"Bearer {WORKOS_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "external_auth_id": external_auth_id,
            "user": {
                "id": str(user.id),
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
            },
        },
        timeout=10,
    )

    #workos errors

    if not workos_response.ok:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Unable to complete WorkOS authentication",
                "workos_error": workos_response.text,
            },
        )

    workos_data = workos_response.json()

    redirect_uri = workos_data.get("redirect_uri")

    if not redirect_uri:
        raise HTTPException(
            status_code=500,
            detail="WorkOS did not return a redirect_uri"
        )

    #return control to workos
    return RedirectResponse(
        url=redirect_uri,
        status_code=302
    )