"""Macro review router for game review generation."""

from datetime import datetime
from fastapi import APIRouter, HTTPException

from app.models.schemas import (
    MacroReviewRequest,
    MacroReviewResponse,
)
from app.services.review_generator import ReviewGenerator

router = APIRouter()
review_generator = ReviewGenerator()


@router.post("", response_model=MacroReviewResponse)
async def generate_macro_review(request: MacroReviewRequest) -> MacroReviewResponse:
    """Generate a structured macro review agenda for a match.

    Creates a comprehensive review agenda with key moments, timestamps,
    discussion points, and priority topics for team review sessions.
    """
    try:
        agenda = await review_generator.generate_review(
            match_id=request.match_id,
            game=request.game,
            game_number=request.game_number,
            team_id=request.team_id,
            review_duration_minutes=request.review_duration_minutes,
        )

        return MacroReviewResponse(
            agenda=agenda,
            generated_at=datetime.utcnow(),
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{match_id}")
async def get_review_template(match_id: str, game: str = "lol"):
    """Get a basic review template for a match.

    Returns a simplified template without fetching full match data.
    Useful for quick review structure generation.
    """
    from app.models.schemas import GameType

    try:
        game_type = GameType(game.lower())
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid game type: {game}")

    return {
        "match_id": match_id,
        "game": game_type,
        "template": {
            "sections": [
                {"name": "Pre-Game", "topics": ["Draft review", "Win conditions", "Strategy alignment"]},
                {"name": "Early Game", "topics": ["Lane states", "Jungle pathing", "First objectives"]},
                {"name": "Mid Game", "topics": ["Rotations", "Vision control", "Objective priority"]},
                {"name": "Late Game", "topics": ["Teamfights", "Closing execution", "Macro decisions"]},
                {"name": "Individual Notes", "topics": ["Player-specific feedback"]},
            ],
            "suggested_duration_minutes": 30,
        },
    }
