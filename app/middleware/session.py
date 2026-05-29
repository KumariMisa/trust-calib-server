from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from fastapi import HTTPException, Depends
from datetime import datetime
from app.core.config import settings
from app.core.database import SessionLocal
from app.models.session import Session
from app.models.user import User

class SessionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request.state.user = None
        request.state.session_id = None
        
        session_id = request.cookies.get(settings.SESSION_COOKIE_NAME)
        if session_id:
            db = SessionLocal()
            try:
                session_row = db.query(Session).filter(
                    Session.id == session_id,
                    Session.expires_at > datetime.utcnow()
                ).first()
                
                if session_row:
                    user = db.query(User).filter(User.id == session_row.user_id).first()
                    if user:
                        # Load user to request state
                        request.state.user = user
                        request.state.session_id = session_row.id
            finally:
                db.close()
                
        response = await call_next(request)
        return response

# Dependency to retrieve the current user
def get_current_user(request: Request) -> User:
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user
