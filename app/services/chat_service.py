from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.models.conversation import Conversation
from app.models.message import Message
import uuid

class ChatService:
    @staticmethod
    def create_conversation(db: Session, user_id: str, title: str = "New Chat") -> Conversation:
        conversation = Conversation(
            id=str(uuid.uuid4()),
            user_id=user_id,
            title=title
        )
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
        return conversation

    @staticmethod
    def get_user_conversations(db: Session, user_id: str) -> list[Conversation]:
        return db.query(Conversation).filter(
            Conversation.user_id == user_id
        ).order_by(Conversation.updated_at.desc()).all()

    @staticmethod
    def get_conversation(db: Session, conversation_id: str, user_id: str) -> Conversation:
        conversation = db.query(Conversation).filter(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id
        ).first()
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return conversation

    @staticmethod
    def delete_conversation(db: Session, conversation_id: str, user_id: str):
        conversation = db.query(Conversation).filter(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id
        ).first()
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        db.delete(conversation)
        db.commit()
        return True

    @staticmethod
    def rename_conversation(db: Session, conversation_id: str, user_id: str, title: str) -> Conversation:
        conversation = db.query(Conversation).filter(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id
        ).first()
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        conversation.title = title
        db.commit()
        db.refresh(conversation)
        return conversation

    @staticmethod
    def update_conversation_title_optimistic(db: Session, conversation_id: str, user_message: str):
        """
        If a conversation title is "New Chat", we auto-update the title
        to be a truncated version of the first user message.
        """
        conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
        if conversation and conversation.title == "New Chat":
            # Truncate first message to 30 chars
            clean_message = user_message.strip()
            title = clean_message[:24] + "..." if len(clean_message) > 24 else clean_message
            conversation.title = title
            db.commit()
            db.refresh(conversation)
