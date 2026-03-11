from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel
from typing import Optional, Any


from shared.utils.llm import LLMClient
from app.services.opponent_analyzer import OpponentAnalyzer
from app.services.prompts import COACH_SYSTEM_PROMPT
from app.models.schemas import GameType

router = APIRouter()

class ChatRequest(BaseModel):
    message: str
    team_id: Optional[str] = None
    game: Optional[GameType] = None
    context_data: Optional[dict[str, Any]] = None

class ChatResponse(BaseModel):
    response: str

@router.post("/chat", response_model=ChatResponse)
async def chat_with_coach(request: ChatRequest):
    """Chat with the AI coach about a specific team or general questions."""
    llm = LLMClient()
    
    context_str = "No specific team selected."
    
    # If team_id is provided, we could fetch fresh data, 
    # but to save time/API calls, we accept context_data from frontend 
    # (which might be the report they are looking at)
    if request.context_data:
        # Format context data for the prompt
        import json
        try:
            context_str = json.dumps(request.context_data, indent=2)
        except:
            context_str = str(request.context_data)
    elif request.team_id and request.game:
        # Fallback: Fetch basic profile if context not provided but ID is
        analyzer = OpponentAnalyzer()
        try:
            profile = await analyzer.analyze_team(request.team_id, 5, request.game)
            context_str = profile.model_dump_json(indent=2)
        except Exception as e:
            print(f"Failed to fetch profile for context: {e}")
            context_str = "Could not fetch specific team data."

    system_prompt = COACH_SYSTEM_PROMPT.format(context=context_str)
    
    try:
        response = await llm.generate(
            prompt=request.message,
            system_prompt=system_prompt,
            max_tokens=500
        )
        return ChatResponse(response=response)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
