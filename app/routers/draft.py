"""Draft router for real-time draft session management."""

import uuid
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query
from typing import Optional


from shared.grid_client import GridClient
from shared.grid_client.lol import LoLMatchQueries, LoLTeamQueries

from app.models.schemas import (
    Side,
    Role,
    DraftAction,
    DraftState,
    DraftSession,
    DraftStartRequest,
    DraftStartResponse,
    DraftUpdateRequest,
    DraftUpdateResponse,
    DraftPick,
    DraftBan,
    OpponentPrediction,
    LoLTeamResult,
    LoLTeamsResponse,
    DraftHistoryEntry,
    DraftHistoryResponse,
    DraftSimulateRequest,
    DraftSimulateResponse,
    ChampionSearchResult,
    ChampionSearchResponse,
    CompositionAnalyzeRequest,
    CompositionAnalyzeResponse,
    WinProbability,
)
from app.services.champion_analyzer import ChampionAnalyzer
from app.services.synergy_engine import SynergyEngine
from app.services.counter_engine import CounterEngine
from app.services.winrate_predictor import WinratePredictor

# Grid client for API access
grid_client = GridClient()

router = APIRouter()

# Service instances
champion_analyzer = ChampionAnalyzer()
synergy_engine = SynergyEngine()
counter_engine = CounterEngine()
winrate_predictor = WinratePredictor(synergy_engine, counter_engine)

# Session storage (would use Redis/database in production)
draft_sessions: dict[str, DraftSession] = {}


@router.post("/start", response_model=DraftStartResponse)
async def start_draft(request: DraftStartRequest) -> DraftStartResponse:
    """Start a new draft session.

    Initializes a draft session with team data and provides
    initial recommendations for the first ban phase.
    """
    try:
        session_id = str(uuid.uuid4())

        # Fetch champion pools for both teams
        our_pools = await champion_analyzer.get_team_champion_pools(request.our_team_id)
        opponent_pools = await champion_analyzer.get_team_champion_pools(request.opponent_team_id)

        # Analyze opponent tendencies
        opponent_tendencies = await champion_analyzer.analyze_draft_tendencies(
            request.opponent_team_id
        )

        # Create session
        session = DraftSession(
            session_id=session_id,
            our_team_id=request.our_team_id,
            opponent_team_id=request.opponent_team_id,
            our_side=request.our_side,
            state=DraftState(),
            our_champion_pools=our_pools,
            opponent_champion_pools=opponent_pools,
        )

        draft_sessions[session_id] = session

        # Generate initial recommendations
        initial_recs = _generate_initial_recommendations(
            request.our_side,
            our_pools,
            opponent_pools,
            opponent_tendencies,
        )

        # Priority bans based on opponent tendencies
        priority_bans = [
            champ for champ, count in opponent_tendencies.get("first_pick_priority", [])[:3]
        ]

        # Format opponent tendencies
        tendency_strings = []
        for champ, count in opponent_tendencies.get("first_pick_priority", [])[:3]:
            tendency_strings.append(f"Frequently first-picks {champ}")
        for champ, count in opponent_tendencies.get("first_ban_priority", [])[:2]:
            tendency_strings.append(f"Prioritizes banning {champ}")

        return DraftStartResponse(
            session_id=session_id,
            our_side=request.our_side,
            state=session.state,
            win_probability=WinProbability(probability=0.5, factors=["Initial State"]),
            initial_recommendations=initial_recs,
            opponent_tendencies=tendency_strings,
            priority_bans=priority_bans,
            created_at=datetime.utcnow(),
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/update", response_model=DraftUpdateResponse)
async def update_draft(request: DraftUpdateRequest) -> DraftUpdateResponse:
    """Update draft state with a new pick or ban.

    Processes the action and returns updated recommendations,
    win probability, and opponent predictions.
    """
    if request.session_id not in draft_sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = draft_sessions[request.session_id]

    try:
        # Get champion info
        champion_info = champion_analyzer.get_champion_info(request.champion_name)

        # Update draft state
        if request.action == DraftAction.PICK:
            pick = DraftPick(
                champion=champion_info,
                team=request.team,
                role=request.role,
                player_id=request.player_id,
                pick_order=len(session.state.blue_picks) + len(session.state.red_picks) + 1,
            )

            if request.team == Side.BLUE:
                session.state.blue_picks.append(pick)
            else:
                session.state.red_picks.append(pick)

        else:  # Ban
            ban = DraftBan(
                champion=champion_info,
                team=request.team,
                ban_order=len(session.state.blue_bans) + len(session.state.red_bans) + 1,
            )

            if request.team == Side.BLUE:
                session.state.blue_bans.append(ban)
            else:
                session.state.red_bans.append(ban)

        # Update phase
        _update_draft_phase(session.state)
        session.updated_at = datetime.utcnow()

        # Generate recommendations
        recommendations = _generate_recommendations(session)

        # Calculate win probability
        win_prob = winrate_predictor.predict_win_probability(
            session.state,
            session.our_side.value,
        )

        # Predict opponent's next move
        opponent_predictions = _predict_opponent_picks(session)

        # Generate analysis text
        analysis = _generate_analysis(session, recommendations, win_prob)

        return DraftUpdateResponse(
            session_id=request.session_id,
            state=session.state,
            recommendations=recommendations,
            win_probability=win_prob,
            opponent_predictions=opponent_predictions,
            analysis=analysis,
            updated_at=datetime.utcnow(),
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{session_id}/state")
async def get_draft_state(session_id: str):
    """Get current draft state and analysis."""
    if session_id not in draft_sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = draft_sessions[session_id]

    win_prob = winrate_predictor.predict_win_probability(
        session.state,
        session.our_side.value,
    )

    power_curve = winrate_predictor.get_draft_power_curve(
        session.state,
        session.our_side.value,
    )

    our_picks = session.state.blue_picks if session.our_side == Side.BLUE else session.state.red_picks
    comp_analysis = synergy_engine.analyze_composition_strengths(our_picks)
    comp_type, comp_desc, win_condition = synergy_engine.identify_composition_type(our_picks)

    return {
        "session_id": session_id,
        "state": session.state,
        "our_side": session.our_side,
        "win_probability": win_prob,
        "power_curve": power_curve,
        "composition": {
            "type": comp_type,
            "description": comp_desc,
            "win_condition": win_condition,
            "strengths": comp_analysis.get("strengths", []),
            "weaknesses": comp_analysis.get("weaknesses", []),
        },
        "updated_at": session.updated_at,
    }


@router.post("/predict-opponent")
async def predict_opponent_action(session_id: str):
    """Predict opponent's next pick or ban."""
    if session_id not in draft_sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = draft_sessions[session_id]
    predictions = _predict_opponent_picks(session)

    return {
        "session_id": session_id,
        "predictions": predictions,
        "current_phase": session.state.current_phase,
    }


@router.delete("/{session_id}")
async def end_draft(session_id: str):
    """End and delete a draft session."""
    if session_id not in draft_sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    del draft_sessions[session_id]
    return {"status": "deleted", "session_id": session_id}


def _generate_initial_recommendations(
    our_side: Side,
    our_pools: list,
    opponent_pools: list,
    opponent_tendencies: dict,
) -> list:
    """Generate initial ban recommendations."""
    from app.models.schemas import DraftRecommendation

    recommendations = []

    # Ban opponent's signature picks
    for pool in opponent_pools:
        for sig_pick in pool.signature_picks[:1]:
            champ_info = champion_analyzer.get_champion_info(sig_pick)
            recommendations.append(DraftRecommendation(
                champion=champ_info,
                action=DraftAction.BAN,
                priority=1,
                reasoning=[
                    f"Signature pick for {pool.player_name}",
                    f"Player has high win rate on this champion",
                ],
                target_player=pool.player_name,
            ))

    # Ban meta picks that counter our pools
    meta_champs = champion_analyzer.get_meta_champions()
    for meta in meta_champs[:5]:
        if meta.tier == "S" and meta.name not in [r.champion.name for r in recommendations]:
            recommendations.append(DraftRecommendation(
                champion=meta,
                action=DraftAction.BAN,
                priority=2,
                reasoning=[
                    f"S-tier meta pick",
                    "High priority in current patch",
                ],
            ))

    return recommendations[:5]


def _generate_recommendations(session: DraftSession) -> list:
    """Generate pick/ban recommendations for current phase."""
    from app.models.schemas import DraftRecommendation

    recommendations = []
    state = session.state
    our_side = session.our_side

    our_picks = state.blue_picks if our_side == Side.BLUE else state.red_picks
    enemy_picks = state.red_picks if our_side == Side.BLUE else state.blue_picks

    # Get available champions
    unavailable = state.unavailable_champions
    all_champs = champion_analyzer.get_meta_champions()
    available = [c for c in all_champs if c.name not in unavailable]

    if state.current_action == DraftAction.PICK:
        # Get synergy recommendations
        synergy_recs = synergy_engine.get_synergy_recommendations(our_picks, available)
        for champ, score, reasons in synergy_recs[:3]:
            recommendations.append(DraftRecommendation(
                champion=champ,
                action=DraftAction.PICK,
                priority=len(recommendations) + 1,
                reasoning=reasons or [f"Synergy score: {score:.0%}"],
                synergy_score=score,
            ))

        # Get counter recommendations
        if enemy_picks:
            counter_recs = counter_engine.get_counter_recommendations(enemy_picks, available)
            for champ, score, reasons in counter_recs[:2]:
                if champ.name not in [r.champion.name for r in recommendations]:
                    recommendations.append(DraftRecommendation(
                        champion=champ,
                        action=DraftAction.PICK,
                        priority=len(recommendations) + 1,
                        reasoning=reasons or [f"Counter score: {score:.0%}"],
                        counter_score=score,
                    ))

    else:  # Ban phase
        # Ban champions that counter our current picks
        if our_picks:
            our_names = [p.champion.name for p in our_picks]
            ban_recs = counter_engine.get_ban_recommendations(our_names, [])
            for champ_name, reason in ban_recs[:3]:
                champ_info = champion_analyzer.get_champion_info(champ_name)
                if champ_info.name not in unavailable:
                    recommendations.append(DraftRecommendation(
                        champion=champ_info,
                        action=DraftAction.BAN,
                        priority=len(recommendations) + 1,
                        reasoning=[reason],
                    ))

        # Ban remaining meta picks
        for meta in available[:3]:
            if meta.name not in [r.champion.name for r in recommendations]:
                recommendations.append(DraftRecommendation(
                    champion=meta,
                    action=DraftAction.BAN,
                    priority=len(recommendations) + 1,
                    reasoning=[f"{meta.tier}-tier meta pick"],
                ))

    return recommendations[:5]


def _predict_opponent_picks(session: DraftSession) -> list[OpponentPrediction]:
    """Predict opponent's next picks based on tendencies."""
    predictions = []
    state = session.state
    our_side = session.our_side

    enemy_pools = session.opponent_champion_pools
    unavailable = state.unavailable_champions

    for pool in enemy_pools:
        for champ in pool.champions[:3]:
            if champ.name not in unavailable:
                probability = 0.3
                if champ.name in pool.signature_picks:
                    probability = 0.6
                elif champ.name in pool.comfort_picks:
                    probability = 0.45

                predictions.append(OpponentPrediction(
                    champion=champ,
                    probability=probability,
                    likely_role=pool.role,
                    reasoning=f"{pool.player_name}'s comfort pick",
                ))

    # Sort by probability
    predictions.sort(key=lambda p: p.probability, reverse=True)
    return predictions[:5]


def _update_draft_phase(state: DraftState):
    """Update draft phase based on picks/bans made."""
    total_bans = len(state.blue_bans) + len(state.red_bans)
    total_picks = len(state.blue_picks) + len(state.red_picks)

    # Standard draft order
    if total_bans < 6:
        state.current_action = DraftAction.BAN
        state.current_phase = 1
    elif total_picks < 6:
        state.current_action = DraftAction.PICK
        state.current_phase = 2
    elif total_bans < 10:
        state.current_action = DraftAction.BAN
        state.current_phase = 3
    elif total_picks < 10:
        state.current_action = DraftAction.PICK
        state.current_phase = 4
    else:
        state.current_phase = 5
        state.is_complete = True

    # Determine current team (Tournament Draft)
    if state.current_action == DraftAction.BAN:
        # Phase 1 Bans (0-5): Blue, Red, Blue, Red, Blue, Red
        if total_bans < 6:
            state.current_team = Side.BLUE if total_bans % 2 == 0 else Side.RED
        # Phase 2 Bans (6-9): Red, Blue, Red, Blue
        else:
            state.current_team = Side.RED if total_bans % 2 == 0 else Side.BLUE
    else:
        # Phase 1 Picks (0-5): Blue, Red, Red, Blue, Blue, Red
        if total_picks < 6:
            if total_picks in [0, 3, 4]:
                state.current_team = Side.BLUE
            else:
                state.current_team = Side.RED
        # Phase 2 Picks (6-9): Red, Blue, Blue, Red
        else:
            if total_picks in [6, 9]:
                state.current_team = Side.RED
            else:
                state.current_team = Side.BLUE


def _generate_analysis(session: DraftSession, recommendations: list, win_prob) -> str:
    """Generate analysis text for current draft state."""
    our_side = session.our_side
    our_picks = session.state.blue_picks if our_side == Side.BLUE else session.state.red_picks

    parts = []

    # Win probability assessment
    if win_prob.probability >= 0.55:
        parts.append("Draft advantage secured.")
    elif win_prob.probability <= 0.45:
        parts.append("Draft currently unfavorable.")
    else:
        parts.append("Draft is even.")

    # Composition assessment
    if our_picks:
        comp_type, _, win_condition = synergy_engine.identify_composition_type(our_picks)
        parts.append(f"Composition trending toward {comp_type}.")
        parts.append(f"Win condition: {win_condition}")

    # Top recommendation
    if recommendations:
        top_rec = recommendations[0]
        parts.append(
            f"Recommended: {top_rec.action.value} {top_rec.champion.name} - "
            f"{top_rec.reasoning[0] if top_rec.reasoning else ''}"
        )

    return " ".join(parts)


# ============== NEW ENDPOINTS ==============


@router.get("/teams/lol", response_model=LoLTeamsResponse)
async def get_lol_teams(
    search: Optional[str] = Query(None, description="Search by team name"),
    limit: int = Query(default=20, ge=1, le=100),
) -> LoLTeamsResponse:
    """Get list of LoL teams for draft session setup.

    Returns teams matching the search query.
    """
    try:
        queries = LoLTeamQueries(grid_client)

        result = await queries.get_teams(
            limit=limit,
            name_contains=search,
        )

        edges = result.get("teams", {}).get("edges", [])
        teams = []

        for edge in edges:
            node = edge.get("node", {})
            if node:
                teams.append(LoLTeamResult(
                    team_id=node.get("id", ""),
                    team_name=node.get("name", "Unknown"),
                    name_shortened=node.get("nameShortened"),
                    logo_url=node.get("logoUrl"),
                ))
        
        # Sort by team_id descending to prioritize recent/active IDs (e.g. 47380 vs 96)
        def get_id_int(t):
            try:
                return int(t.team_id)
            except ValueError:
                return 0
                
        teams.sort(key=get_id_int, reverse=True)

        return LoLTeamsResponse(
            query=search,
            teams=teams,
            total_count=len(teams),
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history/{team_id}", response_model=DraftHistoryResponse)
async def get_draft_history(
    team_id: str,
    limit: int = Query(default=20, ge=1, le=50),
) -> DraftHistoryResponse:
    """Get draft history for a team.

    Returns past drafts with pick/ban patterns.
    """
    try:
        queries = LoLMatchQueries(grid_client)

        # Fetch matches
        match_result = await queries.get_matches_by_team(team_id, limit=limit)
        edges = match_result.get("allSeries", {}).get("edges", [])

        # Get team name
        team_queries = LoLTeamQueries(grid_client)
        team_info = await team_queries.get_team_info(team_id)
        team_name = team_info.get("team", {}).get("name", f"Team {team_id}")

        drafts = []
        pick_counts: dict[str, int] = {}
        ban_counts: dict[str, int] = {}
        first_picks: dict[str, int] = {}

        for edge in edges:
            node = edge.get("node", {})
            series_id = node.get("id")
            if not series_id:
                continue

            try:
                # Use inline query to ensure we don't use stale cached version from matches.py
                # This query excludes 'bans' which was causing crashes
                SAFE_STATE_QUERY = """
                query GetSeriesStateSafe($seriesId: ID!) {
                    seriesState(id: $seriesId) {
                        teams {
                            id
                            name
                            score
                            players {
                                id
                                name
                            }
                        }
                        games {
                            id
                            finished
                            teams {
                                id
                                name
                                score
                                players {
                                    character {
                                        name
                                    }
                                }
                            }
                        }
                    }
                }
                """
                
                state_result = await grid_client.execute(
                    SAFE_STATE_QUERY,
                    variables={"seriesId": series_id},
                    use_series_state=True
                )
                series_state = state_result.get("seriesState")
                
                if not series_state:
                    continue

                games = series_state.get("games", [])
                teams = series_state.get("teams", [])
                
                # Identify our team
                our_team_idx = None
                opponent_name = "Unknown"
                for idx, t in enumerate(teams):
                    if str(t.get("id")) == str(team_id):
                        our_team_idx = idx
                    else:
                        opponent_name = t.get("name", "Unknown")

                if our_team_idx is None:
                    continue

                for game in games:
                    if not game.get("finished"):
                        continue

                    game_teams = game.get("teams", [])
                    if our_team_idx >= len(game_teams):
                        continue

                    our_team = game_teams[our_team_idx]
                    opp_team = game_teams[1 - our_team_idx] if len(game_teams) > 1 else {}

                    # Extract picks
                    our_picks = []
                    for player in our_team.get("players", []):
                        champ = player.get("character", {}).get("name")
                        if champ:
                            our_picks.append(champ)
                            pick_counts[champ] = pick_counts.get(champ, 0) + 1

                    enemy_picks = []
                    for player in opp_team.get("players", []):
                        champ = player.get("character", {}).get("name")
                        if champ:
                            enemy_picks.append(champ)

                    # Track first pick
                    if our_picks:
                        first_picks[our_picks[0]] = first_picks.get(our_picks[0], 0) + 1

                    # Determine result
                    our_score = our_team.get("score", 0)
                    opp_score = opp_team.get("score", 0)
                    result = "Win" if our_score > opp_score else "Loss"

                    drafts.append(DraftHistoryEntry(
                        series_id=series_id,
                        opponent_name=opponent_name,
                        date=node.get("startTimeScheduled"),
                        result=result,
                        our_picks=our_picks,
                        our_bans=[], # Bans not available in current API
                        enemy_picks=enemy_picks,
                        enemy_bans=[],
                    ))

            except Exception:
                continue

        # Calculate patterns
        most_picked = sorted(pick_counts.keys(), key=lambda x: pick_counts[x], reverse=True)[:5]
        most_banned = sorted(ban_counts.keys(), key=lambda x: ban_counts[x], reverse=True)[:5]
        first_pick_priority = sorted(first_picks.keys(), key=lambda x: first_picks[x], reverse=True)[:3]

        return DraftHistoryResponse(
            team_id=team_id,
            team_name=team_name,
            drafts=drafts[:20],  # Limit to 20
            most_picked=most_picked,
            most_banned=most_banned,
            first_pick_priority=first_pick_priority,
            generated_at=datetime.utcnow(),
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/simulate", response_model=DraftSimulateResponse)
async def simulate_draft(request: DraftSimulateRequest) -> DraftSimulateResponse:
    """Simulate a complete draft with AI making opponent picks.

    Returns the final draft state with analysis.
    """
    try:
        session_id = str(uuid.uuid4())

        # Fetch champion pools
        our_pools = await champion_analyzer.get_team_champion_pools(request.our_team_id)
        opponent_pools = await champion_analyzer.get_team_champion_pools(request.opponent_team_id)

        # Create session
        state = DraftState()

        # Simulate ban phase 1 (3 bans each)
        meta = champion_analyzer.get_meta_champions()
        banned = []

        # Blue bans first
        for i in range(3):
            # Our side bans
            if request.our_side == Side.BLUE:
                # Ban opponent's signature picks
                for pool in opponent_pools:
                    for sig in pool.signature_picks:
                        if sig not in banned:
                            champ_info = champion_analyzer.get_champion_info(sig)
                            state.blue_bans.append(DraftBan(champion=champ_info, team=Side.BLUE, ban_order=len(state.blue_bans) + 1))
                            banned.append(sig)
                            break
                    if len(state.blue_bans) > i:
                        break
                # Fallback to meta bans
                if len(state.blue_bans) <= i:
                    for m in meta:
                        if m.name not in banned:
                            state.blue_bans.append(DraftBan(champion=m, team=Side.BLUE, ban_order=len(state.blue_bans) + 1))
                            banned.append(m.name)
                            break
            else:
                # Opponent bans
                for m in meta:
                    if m.name not in banned:
                        state.blue_bans.append(DraftBan(champion=m, team=Side.BLUE, ban_order=len(state.blue_bans) + 1))
                        banned.append(m.name)
                        break

            # Red bans
            if request.our_side == Side.RED:
                for pool in opponent_pools:
                    for sig in pool.signature_picks:
                        if sig not in banned:
                            champ_info = champion_analyzer.get_champion_info(sig)
                            state.red_bans.append(DraftBan(champion=champ_info, team=Side.RED, ban_order=len(state.red_bans) + 1))
                            banned.append(sig)
                            break
                    if len(state.red_bans) > i:
                        break
                if len(state.red_bans) <= i:
                    for m in meta:
                        if m.name not in banned:
                            state.red_bans.append(DraftBan(champion=m, team=Side.RED, ban_order=len(state.red_bans) + 1))
                            banned.append(m.name)
                            break
            else:
                for m in meta:
                    if m.name not in banned:
                        state.red_bans.append(DraftBan(champion=m, team=Side.RED, ban_order=len(state.red_bans) + 1))
                        banned.append(m.name)
                        break

        # Simulate picks (simplified - pick from pools/meta)
        picked = []
        roles_filled = {Side.BLUE: [], Side.RED: []}

        # Simulate Bans (5 per team)
        # Ensure we have 5 bans each
        while len(state.blue_bans) < 5 or len(state.red_bans) < 5:
            # Alternating bans: Blue, Red, Blue, Red...
            total_bans = len(state.blue_bans) + len(state.red_bans)
            # Snake or alternate? Standard is alternating for first phase, then alternating for second.
            # Simplified: Just alternate.
            is_blue_ban = total_bans % 2 == 0
            ban_side = Side.BLUE if is_blue_ban else Side.RED
            
            # Skip if this side already has 5 bans (e.g. if we started with uneven bans)
            if (ban_side == Side.BLUE and len(state.blue_bans) >= 5) or \
               (ban_side == Side.RED and len(state.red_bans) >= 5):
               # Force switch to other side if they need bans
               if len(state.blue_bans) < 5: ban_side = Side.BLUE
               else: ban_side = Side.RED

            # Pick a ban
            ban_target = None
            # 1. Ban counters to our likely picks (if any) or just high winrate meta
            # Simple simulation: Ban random high tier meta champ not already banned/picked
            for m in meta:
                if m.name not in banned and m.name not in picked:
                    ban_target = m
                    break
            
            if ban_target:
                banned.append(ban_target.name)
                ban_obj = DraftPick(
                    champion=ban_target,
                    team=ban_side,
                    pick_order=total_bans + 1, # Using pick_order field for ban order
                    is_ban=True
                )
                if ban_side == Side.BLUE:
                    state.blue_bans.append(ban_obj)
                else:
                    state.red_bans.append(ban_obj)

        # Pick phase (Simon says 5 picks)
        # Simulate remaining picks until both teams have 5 champions
        # Standard draft has 6 bans (3 each), 6 picks (3 each), 4 bans (2 each), 4 picks (2 each)
        # For simulation simplicity, we ensure 5 picks per team.
        
        while len(state.blue_picks) < 5 or len(state.red_picks) < 5:
            # Determine turn
            total_picks = len(state.blue_picks) + len(state.red_picks)
            # Simple alternating for simulation speed, or map to snake draft if needed
            # Snake draft order: B R R B B R R B B R (0, 1, 2, 3, 4, 5, 6, 7, 8, 9)
            # But the structure below calculates side dynamically.
            
            # Snake draft indices (0-indexed):
            # Blue: 0, 3, 4, 7, 8
            # Red: 1, 2, 5, 6, 9
            is_blue_turn = total_picks in [0, 3, 4, 7, 8]
            side = Side.BLUE if is_blue_turn else Side.RED

            is_our_pick = (side == request.our_side)
            pools = our_pools if is_our_pick else opponent_pools
            
            # Determine current team's existing picks
            current_team_picks = state.blue_picks if side == Side.BLUE else state.red_picks
            enemy_team_picks = state.red_picks if side == Side.BLUE else state.blue_picks

            picked_champ = None
            role = None

            # 1. Smart Pick Logic
            # Get available champions
            available = [c for c in meta if c.name not in banned and c.name not in picked]
            
            # A. Check for High Synergy with existing picks
            synergy_recs = synergy_engine.get_synergy_recommendations(current_team_picks, available)
            if synergy_recs:
                 # Top synergy pick
                 picked_champ = synergy_recs[0][0]
                 # Find role for this champ from pools if possible
                 for pool in pools:
                     if picked_champ.name in pool.comfort_picks:
                         role = pool.role
                         break
            
            # B. Check for Counters if enemy has picked
            if not picked_champ and enemy_team_picks:
                counter_recs = counter_engine.get_counter_recommendations(enemy_team_picks, available)
                if counter_recs:
                    picked_champ = counter_recs[0][0]
                    for pool in pools:
                     if picked_champ.name in pool.comfort_picks:
                         role = pool.role
                         break

            # C. Fallback to Comfort/Signature picks
            if not picked_champ:
                for pool in pools:
                    if pool.role.value not in [r.value for r in roles_filled[side]]:
                        for champ in pool.comfort_picks:
                            if champ not in banned and champ not in picked:
                                picked_champ = champion_analyzer.get_champion_info(champ)
                                role = pool.role
                                break
                    if picked_champ:
                        break

            # D. Fallback to Meta
            if not picked_champ:
                for m in meta:
                    if m.name not in banned and m.name not in picked:
                        picked_champ = m
                        break

            if picked_champ:
                picked.append(picked_champ.name)
                # Assign role if not found (simplified)
                if not role:
                     role = Role.MID  # Default fallback
                     if picked_champ.roles:
                         try:
                             role = Role(picked_champ.roles[0].upper()) 
                         except:
                             pass

                pick_obj = DraftPick(
                    champion=picked_champ,
                    team=side,
                    role=role,
                    pick_order=len(state.blue_picks) + len(state.red_picks) + 1,
                )

                if side == Side.BLUE:
                    state.blue_picks.append(pick_obj)
                else:
                    state.red_picks.append(pick_obj)
                
                if role:
                    roles_filled[side].append(role)

        # Update phase
        state.is_complete = True
        state.current_phase = 6 # Game start phase (virtually)

        # Calculate win probability
        win_prob = winrate_predictor.predict_win_probability(
            state,
            request.our_side.value,
        )

        # Get composition analysis
        our_picks = state.blue_picks if request.our_side == Side.BLUE else state.red_picks
        comp_type, comp_desc, win_condition = synergy_engine.identify_composition_type(our_picks)

        # Generate power spikes
        power_spikes = [
            "Level 6 power spike",
            "2-item power spike (~20 min)",
            "Late game teamfight strength",
        ]

        # Warnings
        warnings = []
        if len(our_picks) < 5:
            warnings.append("Draft incomplete - some roles unfilled")
        if win_prob.probability < 0.45:
            warnings.append("Draft disadvantage detected - consider adjustments")

        return DraftSimulateResponse(
            session_id=session_id,
            our_side=request.our_side,
            final_state=state,
            win_probability=win_prob,
            composition_type=comp_type,
            win_condition=win_condition,
            power_spikes=power_spikes,
            warnings=warnings,
            generated_at=datetime.utcnow(),
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/champions/search", response_model=ChampionSearchResponse)
async def search_champions(
    name: str = Query(..., min_length=1),
    session_id: Optional[str] = Query(None),
) -> ChampionSearchResponse:
    """Search for champions by name.

    Returns champion info with counters and synergies.
    If session_id is provided, excludes unavailable champions.
    """
    try:
        # Get all meta champions
        meta = champion_analyzer.get_meta_champions()

        # Get unavailable champions if session exists
        unavailable = []
        if session_id and session_id in draft_sessions:
            unavailable = draft_sessions[session_id].state.unavailable_champions

        # Filter by name (case-insensitive, ignore special chars)
        def normalize(s):
            return s.lower().replace("'", "").replace(".", "").replace(" ", "")

        name_norm = normalize(name)
        results = []

        for champ in meta:
            if name_norm in normalize(champ.name) and champ.name not in unavailable:
                # Get counter/synergy info
                counters = list(champ.counters.keys())[:3]
                countered_by = list(champ.countered_by.keys())[:3]
                synergies = list(champ.synergies.keys())[:3]

                results.append(ChampionSearchResult(
                    id=champ.id,
                    name=champ.name,
                    roles=champ.roles,
                    tier=champ.tier,
                    win_rate=champ.win_rate,
                    counters=counters,
                    countered_by=countered_by,
                    synergies=synergies,
                ))

        return ChampionSearchResponse(
            query=name,
            results=results,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/composition/analyze", response_model=CompositionAnalyzeResponse)
async def analyze_composition(request: CompositionAnalyzeRequest) -> CompositionAnalyzeResponse:
    """Analyze a team composition.

    Returns composition type, strengths, weaknesses, and win conditions.
    """
    try:
        # Build mock picks for analysis
        picks = []
        for champ_name in request.champions:
            champ_info = champion_analyzer.get_champion_info(champ_name)
            picks.append(DraftPick(
                champion=champ_info,
                team=Side.BLUE,
                pick_order=len(picks) + 1,
            ))

        # Analyze composition
        comp_type, comp_desc, win_condition = synergy_engine.identify_composition_type(picks)
        analysis = synergy_engine.analyze_composition_strengths(picks)

        # Get synergy score
        synergy_score = 0.5
        if len(picks) >= 2:
            total_synergy = 0
            pairs = 0
            for i, p1 in enumerate(picks):
                for p2 in picks[i+1:]:
                    score = p1.champion.synergies.get(p2.champion.name, 0.5)
                    total_synergy += score
                    pairs += 1
            if pairs > 0:
                synergy_score = total_synergy / pairs

        # Generate power spikes based on champions
        power_spikes = [
            "Level 6 - Ultimate abilities unlocked",
            "1-item spike - Core item completion",
            "2-item spike - Mid-game power",
        ]

        # Get suggested counters
        suggested_counters = []
        for champ_name in request.champions[:2]:
            champ = champion_analyzer.get_champion_info(champ_name)
            for counter in list(champ.countered_by.keys())[:2]:
                if counter not in suggested_counters:
                    suggested_counters.append(counter)

        return CompositionAnalyzeResponse(
            champions=request.champions,
            composition_type=comp_type,
            composition_description=comp_desc,
            win_condition=win_condition,
            power_spikes=power_spikes,
            strengths=analysis.get("strengths", []),
            weaknesses=analysis.get("weaknesses", []),
            suggested_counters=suggested_counters[:5],
            synergy_score=round(synergy_score, 2),
            generated_at=datetime.utcnow(),
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
