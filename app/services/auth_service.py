from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from fastapi import HTTPException
from app.models.user import User
from app.models.session import Session as DBSession
from app.core.security import hash_password, verify_password
from app.core.config import settings

class AuthService:
    @staticmethod
    def register_user(db: Session, name: str, username: str, password: str) -> User:
        # Check if username already exists
        existing_user = db.query(User).filter(User.username == username.lower()).first()
        if existing_user:
            raise HTTPException(status_code=400, detail="Username is already taken")
            
        password_hash = hash_password(password)
        new_user = User(
            name=name,
            username=username.lower(),
            password_hash=password_hash
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        return new_user

    @staticmethod
    def login_user(db: Session, username: str, password: str) -> DBSession:
        user = db.query(User).filter(User.username == username.lower()).first()
        if not user or not verify_password(password, user.password_hash):
            raise HTTPException(status_code=401, detail="Invalid username or password")
            
        # Create session row
        expires_at = datetime.utcnow() + timedelta(days=settings.SESSION_EXPIRY_DAYS)
        session = DBSession(
            user_id=user.id,
            expires_at=expires_at
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        return session

    @staticmethod
    def logout_user(db: Session, session_id: str):
        session = db.query(DBSession).filter(DBSession.id == session_id).first()
        if session:
            db.delete(session)
            db.commit()
        return True
