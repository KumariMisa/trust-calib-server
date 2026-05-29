import json
import httpx
from datetime import datetime
from app.core.config import settings
from app.graph.state import AgentState
from app.models.message import Message as DBMessage
from app.models.conversation import Conversation as DBConversation

async def load_conversation_node(state: AgentState, db) -> AgentState:
    # Fetch all historical messages
    db_messages = db.query(DBMessage).filter(
        DBMessage.conversation_id == state.conversation_id
    ).order_by(DBMessage.created_at.asc())
    
    state.messages = []
    for msg in db_messages.all():
        state.messages.append({
            "role": msg.role,
            "content": msg.content
        })
    return state

async def context_builder_node(state: AgentState) -> AgentState:
    # Append the new user message
    state.messages.append({
        "role": "user",
        "content": state.user_message
    })
    return state

async def llm_generation_node(state: AgentState):
    """
    Asynchronous generator node that streams tokens from Gemini API
    and accumulates the full response in the state.
    """
    selected_model = state.metadata.get("model", "") if state.metadata else ""
    gemini_model = "gemini-2.5-flash"
    if "Opus" in selected_model or "opus" in selected_model.lower():
        gemini_model = "gemini-2.5-pro"

    if not settings.GEMINI_API_KEY:
        # Fallback simulation if no API key is provided
        model_display = selected_model or "Sonnet 4.6"
        mock_response = (
            f"Hello! I am Claude (simulated via **{model_display}**). It looks like the GEMINI_API_KEY environment variable "
            "is not set in your .env file.\n\n"
            "To connect me to the real model, please set your GEMINI_API_KEY.\n\n"
            "Here is the text you wrote: " + state.user_message
        )
        # Yield words slowly to simulate streaming
        import asyncio
        words = mock_response.split(" ")
        for i, word in enumerate(words):
            token = word + " " if i < len(words) - 1 else word
            state.assistant_response += token
            yield token
            await asyncio.sleep(0.04)
        return

    # Map message history to Gemini API formats
    # Gemini roles: 'user' or 'model'
    contents = []
    for msg in state.messages:
        role = "user" if msg["role"] == "user" else "model"
        contents.append({
            "role": role,
            "parts": [{"text": msg["content"]}]
        })

    # Prepare streaming request
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{gemini_model}:streamGenerateContent?key={settings.GEMINI_API_KEY}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": contents,
        "systemInstruction": {
            "parts": [{"text": "You are Claude, a helpful, honest, and harmless assistant. Replicate Claude's tone: thoughtful, polite, structured, and editorial."}]
        }
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            async with client.stream("POST", url, headers=headers, json=payload) as response:
                if response.status_code != 200:
                    error_text = await response.aread()
                    yield f"Error calling Gemini API: {response.status_code} - {error_text.decode()}"
                    return

                # Read JSON stream using brace-matching parser
                buffer = ""
                async for chunk in response.aiter_text():
                    buffer += chunk
                    while True:
                        start = buffer.find('{')
                        if start == -1:
                            break
                        
                        depth = 0
                        end = -1
                        for i in range(start, len(buffer)):
                            char = buffer[i]
                            if char == '{':
                                depth += 1
                            elif char == '}':
                                depth -= 1
                                if depth == 0:
                                    end = i
                                    break
                        
                        if end != -1:
                            obj_text = buffer[start:end+1]
                            buffer = buffer[end+1:]
                            
                            try:
                                chunk_data = json.loads(obj_text)
                                candidates = chunk_data.get("candidates", [])
                                if candidates:
                                    parts = candidates[0].get("content", {}).get("parts", [])
                                    if parts and "text" in parts[0]:
                                        token = parts[0]["text"]
                                        state.assistant_response += token
                                        yield token
                            except Exception:
                                pass
                        else:
                            break
        except Exception as e:
            yield f"\n[Stream connection error: {str(e)}]"

async def persistence_node(state: AgentState, db) -> AgentState:
    # Save user message
    user_db_msg = DBMessage(
        conversation_id=state.conversation_id,
        role="user",
        content=state.user_message
    )
    db.add(user_db_msg)
    
    # Save assistant response
    assistant_db_msg = DBMessage(
        conversation_id=state.conversation_id,
        role="assistant",
        content=state.assistant_response
    )
    db.add(assistant_db_msg)
    
    # Update conversation updated_at timestamp
    db.query(DBConversation).filter(
        DBConversation.id == state.conversation_id
    ).update({
        "updated_at": datetime.utcnow()
    })
    
    db.commit()
    return state
