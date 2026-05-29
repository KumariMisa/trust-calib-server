import time
from datetime import datetime
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.database import engine, Base
from app.middleware.session import SessionMiddleware
from app.api import auth, conversation, chat

# Track server start time
START_TIME = time.time()

# Initialize database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="MVP Backend API for Claude AI Clone",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Register CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register session-cookie parsing middleware
app.add_middleware(SessionMiddleware)

# Mount endpoints
app.include_router(auth.router)
app.include_router(conversation.router)
app.include_router(chat.router)

@app.get("/health", tags=["Utilities"])
def health_check():
    return {
        "status": "healthy",
        "uptime": round(time.time() - START_TIME, 2),
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "version": "1.0.0"
    }
