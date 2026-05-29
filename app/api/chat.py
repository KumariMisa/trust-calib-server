from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
import json
from sse_starlette.sse import EventSourceResponse
from app.core.database import get_db
from app.schemas.chat import SendMessageRequest
from app.services.chat_service import ChatService
from app.services.langgraph_service import LangGraphService
from app.middleware.session import get_current_user
from app.models.user import User

router = APIRouter(prefix="/chat", tags=["Chat"])

@router.post("/send")
async def send_message(
    payload: SendMessageRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Verify active conversation ownership first
    ChatService.get_conversation(db=db, conversation_id=payload.conversation_id, user_id=current_user.id)
    
    # Optimistically generate title if it is the first user message
    ChatService.update_conversation_title_optimistic(
        db=db,
        conversation_id=payload.conversation_id,
        user_message=payload.message
    )

    async def event_stream():
        try:
            async for event in LangGraphService.execute_workflow(
                db=db,
                conversation_id=payload.conversation_id,
                user_id=current_user.id,
                user_message=payload.message,
                model=payload.model
            ):
                yield {
                    "event": event["event"],
                    "data": json.dumps(event)
                }
        except Exception as e:
            yield {
                "event": "error",
                "data": json.dumps({"detail": str(e)})
            }

    return EventSourceResponse(event_stream())
