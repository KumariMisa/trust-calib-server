from fastapi import APIRouter, Depends, Body
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.schemas.chat import ConversationOut, ConversationDetailOut, ConversationCreate
from app.services.chat_service import ChatService
from app.middleware.session import get_current_user
from app.models.user import User

router = APIRouter(prefix="/conversations", tags=["Conversations"])

@router.post("/new", response_model=ConversationOut)
def create_new_conversation(
    payload: ConversationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    title = payload.title or "New Chat"
    return ChatService.create_conversation(db=db, user_id=current_user.id, title=title)

@router.get("", response_model=List[ConversationOut])
def get_conversations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return ChatService.get_user_conversations(db=db, user_id=current_user.id)

@router.get("/{id}", response_model=ConversationDetailOut)
def get_conversation_detail(
    id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return ChatService.get_conversation(db=db, conversation_id=id, user_id=current_user.id)

@router.post("/{id}/rename", response_model=ConversationOut)
def rename_conversation(
    id: str,
    title: str = Body(..., embed=True),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return ChatService.rename_conversation(
        db=db,
        conversation_id=id,
        user_id=current_user.id,
        title=title
    )

@router.delete("/{id}")
def delete_conversation(
    id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    ChatService.delete_conversation(db=db, conversation_id=id, user_id=current_user.id)
    return {"message": "Conversation deleted successfully"}
