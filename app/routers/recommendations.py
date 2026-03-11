"""Recommendations router for standalone draft advice."""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from app.models.schemas import (
    Role,
    Side,
    DraftAction,
    ChampionInfo,
    DraftRecommendation,
)
from app.services.champion_analyzer import ChampionAnalyzer
from app.services.synergy_engine import SynergyEngine
from app.services.counter_engine import CounterEngine

router = APIRouter()

champion_analyzer = ChampionAnalyzer()
synergy_engine = SynergyEngine()
counter_engine = CounterEngine()


@router.get("/meta")
async def get_meta_champions(role: Optional[str] = None):
    """Get current meta champions, optionally filtered by role."""
    role_enum = None
    if role:
        try:
            role_enum = Role(role.lower())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid role: {role}")

    champions = champion_analyzer.get_meta_champions(role_enum)

    return {
        "champions": [
            {
                "name": c.name,
                "tier": c.tier,
                "roles": [r.value for r in c.roles],
                "win_rate": c.win_rate,
            }
            for c in champions
        ],
        "patch": "14.1",  # Would be dynamic in production
        "filtered_role": role,
    }


@router.get("/flex-picks")
async def get_flex_picks():
    """Get champions that can flex between multiple roles."""
    flex = champion_analyzer.get_flex_picks()

    return {
        "flex_picks": [
            {
                "name": c.name,
                "roles": [r.value for r in c.roles],
                "tier": c.tier,
            }
            for c in flex
        ],
    }


@router.post("/synergy")
async def get_synergy_recommendations(
    current_picks: list[str] = Query(...),
    role: Optional[str] = None,
):
    """Get champion recommendations based on synergy with current picks."""
    from app.models.schemas import DraftPick

    # Convert to DraftPick objects
    picks = []
    for champ_name in current_picks:
        champ_info = champion_analyzer.get_champion_info(champ_name)
        picks.append(DraftPick(
            champion=champ_info,
            team=Side.BLUE,
            pick_order=len(picks) + 1,
        ))

    # Get available champions
    all_champs = champion_analyzer.get_meta_champions()
    available = [c for c in all_champs if c.name not in current_picks]

    role_enum = None
    if role:
        try:
            role_enum = Role(role.lower())
        except ValueError:
            pass

    recommendations = synergy_engine.get_synergy_recommendations(picks, available, role_enum)

    return {
        "current_picks": current_picks,
        "recommendations": [
            {
                "champion": rec[0].name,
                "synergy_score": rec[1],
                "reasons": rec[2],
            }
            for rec in recommendations[:10]
        ],
    }


@router.post("/counter")
async def get_counter_recommendations(
    enemy_picks: list[str] = Query(...),
    role: Optional[str] = None,
):
    """Get counter-pick recommendations against enemy team."""
    from app.models.schemas import DraftPick

    # Convert to DraftPick objects
    picks = []
    for champ_name in enemy_picks:
        champ_info = champion_analyzer.get_champion_info(champ_name)
        picks.append(DraftPick(
            champion=champ_info,
            team=Side.RED,
            pick_order=len(picks) + 1,
        ))

    # Get available champions
    all_champs = champion_analyzer.get_meta_champions()
    available = [c for c in all_champs if c.name not in enemy_picks]

    role_enum = None
    if role:
        try:
            role_enum = Role(role.lower())
        except ValueError:
            pass

    recommendations = counter_engine.get_counter_recommendations(picks, available, role_enum)

    return {
        "enemy_picks": enemy_picks,
        "recommendations": [
            {
                "champion": rec[0].name,
                "counter_score": rec[1],
                "reasons": rec[2],
            }
            for rec in recommendations[:10]
        ],
    }


@router.get("/champion/{champion_name}")
async def get_champion_details(champion_name: str):
    """Get detailed information about a champion."""
    champ = champion_analyzer.get_champion_info(champion_name)

    counters = counter_engine.get_counters(champion_name)
    countered_by = counter_engine.get_countered_by(champion_name)

    return {
        "champion": {
            "name": champ.name,
            "id": champ.id,
            "roles": [r.value for r in champ.roles],
            "tier": champ.tier,
            "win_rate": champ.win_rate,
            "pick_rate": champ.pick_rate,
            "ban_rate": champ.ban_rate,
        },
        "counters": [
            {"champion": c[0], "effectiveness": c[1]}
            for c in counters
        ],
        "countered_by": [
            {"champion": c[0], "effectiveness": c[1]}
            for c in countered_by
        ],
    }


@router.post("/analyze-composition")
async def analyze_composition(picks: list[str] = Query(...)):
    """Analyze a team composition."""
    from app.models.schemas import DraftPick

    # Convert to DraftPick objects
    draft_picks = []
    for champ_name in picks:
        champ_info = champion_analyzer.get_champion_info(champ_name)
        draft_picks.append(DraftPick(
            champion=champ_info,
            team=Side.BLUE,
            pick_order=len(draft_picks) + 1,
        ))

    synergy_score = synergy_engine.calculate_synergy_score(draft_picks)
    comp_type, comp_desc, win_condition = synergy_engine.identify_composition_type(draft_picks)
    analysis = synergy_engine.analyze_composition_strengths(draft_picks)
    identity = synergy_engine.get_team_identity(draft_picks)

    return {
        "composition": picks,
        "synergy_score": synergy_score,
        "type": comp_type,
        "description": comp_desc,
        "win_condition": win_condition,
        "identity": identity,
        "strengths": analysis.get("strengths", []),
        "weaknesses": analysis.get("weaknesses", []),
    }


@router.post("/compare-drafts")
async def compare_drafts(
    blue_picks: list[str] = Query(...),
    red_picks: list[str] = Query(...),
):
    """Compare two draft compositions."""
    from app.models.schemas import DraftPick, DraftState

    # Build draft states
    blue_draft_picks = []
    for champ_name in blue_picks:
        champ_info = champion_analyzer.get_champion_info(champ_name)
        blue_draft_picks.append(DraftPick(
            champion=champ_info,
            team=Side.BLUE,
            pick_order=len(blue_draft_picks) + 1,
        ))

    red_draft_picks = []
    for champ_name in red_picks:
        champ_info = champion_analyzer.get_champion_info(champ_name)
        red_draft_picks.append(DraftPick(
            champion=champ_info,
            team=Side.RED,
            pick_order=len(red_draft_picks) + 1,
        ))

    state = DraftState(
        blue_picks=blue_draft_picks,
        red_picks=red_draft_picks,
    )

    # Analyze both sides
    from app.services.winrate_predictor import WinratePredictor
    predictor = WinratePredictor(synergy_engine, counter_engine)

    blue_prob = predictor.predict_win_probability(state, "blue")
    red_prob = predictor.predict_win_probability(state, "red")

    blue_analysis = synergy_engine.analyze_composition_strengths(blue_draft_picks)
    red_analysis = synergy_engine.analyze_composition_strengths(red_draft_picks)

    matchup_score = counter_engine.calculate_matchup_score(blue_draft_picks, red_draft_picks)

    return {
        "blue_side": {
            "picks": blue_picks,
            "win_probability": blue_prob.probability,
            "strengths": blue_analysis.get("strengths", []),
            "weaknesses": blue_analysis.get("weaknesses", []),
        },
        "red_side": {
            "picks": red_picks,
            "win_probability": red_prob.probability,
            "strengths": red_analysis.get("strengths", []),
            "weaknesses": red_analysis.get("weaknesses", []),
        },
        "matchup_advantage": "blue" if matchup_score > 0.5 else "red" if matchup_score < 0.5 else "even",
        "matchup_score": matchup_score,
    }
