from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

class AgentState(BaseModel):
    messages: List[Dict[str, Any]] = Field(default_factory=list)
    user_id: str
    conversation_id: str
    user_message: str
    assistant_response: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)
