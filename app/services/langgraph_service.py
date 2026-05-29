from sqlalchemy.orm import Session
from typing import AsyncGenerator, Dict, Any
from app.graph.builder import chat_graph

class LangGraphService:
    @staticmethod
    async def execute_workflow(
        db: Session,
        conversation_id: str,
        user_id: str,
        user_message: str,
        model: str = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Coordinates graph execution and yields token streams to the frontend.
        """
        input_data = {
            "conversation_id": conversation_id,
            "user_id": user_id,
            "user_message": user_message,
            "metadata": {"model": model} if model else {}
        }
        
        async for event in chat_graph.astream(input_data, db):
            yield event
            
            # Simple yield sleep to prevent loop blocking
            import asyncio
            await asyncio.sleep(0.001)
            
# Instantiate service
langgraph_service = LangGraphService()
