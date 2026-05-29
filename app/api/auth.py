from fastapi import APIRouter, Depends, Response, Request
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.config import settings
from app.schemas.auth import UserRegister, UserLogin, UserOut
from app.services.auth_service import AuthService
from app.middleware.session import get_current_user
from app.models.user import User

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/register", response_model=UserOut)
def register(user_data: UserRegister, db: Session = Depends(get_db)):
    return AuthService.register_user(
        db=db,
        name=user_data.name,
        username=user_data.username,
        password=user_data.password
    )

@router.post("/login", response_model=UserOut)
def login(login_data: UserLogin, response: Response, db: Session = Depends(get_db)):
    session = AuthService.login_user(
        db=db,
        username=login_data.username,
        password=login_data.password
    )
    
    # Set HttpOnly Session Cookie
    response.set_cookie(
        key=settings.SESSION_COOKIE_NAME,
        value=session.id,
        httponly=True,
        samesite="lax",
        secure=False,  # Set True in production (HTTPS required)
        max_age=settings.SESSION_EXPIRY_DAYS * 24 * 60 * 60
    )
    
    # Return the user info
    return session.user

@router.post("/logout")
def logout(response: Response, request: Request, db: Session = Depends(get_db)):
    session_id = getattr(request.state, "session_id", None)
    if session_id:
        AuthService.logout_user(db=db, session_id=session_id)
        
    response.delete_cookie(settings.SESSION_COOKIE_NAME)
    return {"message": "Logged out successfully"}

@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return current_user
