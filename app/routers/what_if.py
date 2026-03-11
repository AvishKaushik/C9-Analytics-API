"""What-if router for hypothetical scenario analysis."""

from datetime import datetime
from fastapi import APIRouter, HTTPException

from app.models.schemas import (
    WhatIfRequest,
    WhatIfResponse,
)
from app.services.scenario_predictor import ScenarioPredictor

router = APIRouter()
scenario_predictor = ScenarioPredictor()


@router.post("", response_model=WhatIfResponse)
async def analyze_what_if(request: WhatIfRequest) -> WhatIfResponse:
    """Analyze a hypothetical scenario and predict outcomes.

    Takes a game state (identified by match_id and optional timestamp)
    and a scenario description to predict what would have happened
    with an alternative decision.
    """
    try:
        original_outcome, prediction, alternatives = await scenario_predictor.predict_scenario(
            match_id=request.match_id,
            game=request.game,
            scenario_description=request.scenario_description,
            timestamp=request.timestamp,
            game_number=request.game_number,
        )

        return WhatIfResponse(
            match_id=request.match_id,
            game=request.game,
            original_outcome=original_outcome,
            prediction=prediction,
            alternative_scenarios=alternatives,
            generated_at=datetime.utcnow(),
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/quick")
async def quick_scenario_analysis(
    scenario: str,
    game: str = "lol",
    context: str = "",
):
    """Quick scenario analysis without specific match data.

    Provides general analysis of a described scenario based on
    typical professional play patterns.
    """
    from app.models.schemas import GameType

    try:
        game_type = GameType(game.lower())
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid game type: {game}")

    # Provide general guidance without specific match data
    return {
        "scenario": scenario,
        "game": game_type,
        "context": context,
        "analysis": {
            "general_assessment": (
                "Without specific match context, analysis is based on typical "
                "professional play patterns and game theory principles."
            ),
            "key_considerations": [
                "Current game state (gold/round lead)",
                "Team composition strengths",
                "Available resources (cooldowns, economy)",
                "Map state and vision",
                "Risk vs reward calculation",
            ],
            "recommendation": (
                "For detailed analysis, provide a match_id and timestamp "
                "to evaluate the specific game state."
            ),
        },
        "generated_at": datetime.utcnow().isoformat(),
    }
