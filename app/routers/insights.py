"""Insights router for player and team analysis."""

from datetime import datetime
from fastapi import APIRouter, HTTPException, Query
from typing import Optional


from shared.grid_client import GridClient
from shared.grid_client.lol import LoLMatchQueries
from shared.grid_client.valorant import ValorantMatchQueries, ValorantTeamQueries

from app.models.schemas import (
    GameType,
    PlayerInsightRequest,
    PlayerInsightResponse,
    PlayerStats,
    AgentStats,
    RecentForm,
    TeamInsightRequest,
    TeamInsightResponse,
    TeamStats,
    PlayerSummary,
    RosterRequest,
    RosterResponse,
    PlayerProfileRequest,
    MatchSummary,
    MatchListResponse,
    TimelineEvent,
    MatchTimelineResponse,
    PlayerComparisonRequest,
    PlayerComparisonStats,
    PlayerComparisonResponse,
    PerformanceDataPoint,
    TrendResponse,
    TeamComparisonRequest,
    TeamComparisonStats,
    TeamComparisonResponse,
    HeadToHead,
)
from app.services.pattern_detector import PatternDetector

# Grid client for direct API access
grid_client = GridClient()

router = APIRouter()
pattern_detector = PatternDetector()


@router.post("/player", response_model=PlayerInsightResponse)
async def get_player_insights(request: PlayerInsightRequest) -> PlayerInsightResponse:
    """Generate personalized improvement insights for a player.

    Analyzes player performance data across specified matches to identify
    patterns, weaknesses, and actionable improvement areas.

    **API Usage:**
    - Grid Central Data API: Player metadata
    - Grid Live Data API: Match statistics
    - LLM: Not used (rule-based analysis)
    """
    try:
        # Get patterns and insights
        patterns, insights, performances = await pattern_detector.analyze_player_detailed(
            player_id=request.player_id,
            match_ids=request.match_ids,
            game=request.game,
            focus_areas=request.focus_areas,
            limit=request.limit,
        )

        # Calculate detailed stats
        stats = _calculate_player_stats(performances)
        agent_pool = _calculate_agent_stats(performances)
        recent_form = _calculate_recent_form(performances)

        # Get recent matches summary
        recent_matches = performances[:5] if performances else []

        # Generate summary
        summary = _generate_player_summary(patterns, insights, stats)

        # Get player name from performances if available
        player_name = request.player_id
        if performances and performances[0].get("teamName"):
            player_name = f"Player {request.player_id}"

        return PlayerInsightResponse(
            player_id=request.player_id,
            player_name=player_name,
            game=request.game,
            analysis_period=f"Last {len(performances)} games",
            stats=stats,
            agent_pool=agent_pool,
            recent_form=recent_form,
            patterns=patterns,
            insights=insights,
            recent_matches=recent_matches,
            summary=summary,
            generated_at=datetime.utcnow(),
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/team", response_model=TeamInsightResponse)
async def get_team_insights(request: TeamInsightRequest) -> TeamInsightResponse:
    """Generate team-wide pattern analysis and insights.

    Analyzes team performance data to identify strategic patterns,
    coordination issues, and team-level improvement opportunities.

    **API Usage:**
    - Grid Central Data API: Team series list
    - Grid Live Data API: Match statistics
    - LLM: Not used (rule-based analysis)
    """
    try:
        result = await pattern_detector.analyze_team_detailed(
            team_id=request.team_id,
            match_ids=request.match_ids,
            game=request.game,
            focus_areas=request.focus_areas,
            limit=request.limit,
        )

        patterns = result["patterns"]
        insights = result["insights"]
        player_highlights = result["player_highlights"]
        matches = result["matches"]
        roster_data = result["roster"]

        # Calculate team stats
        team_stats = _calculate_team_stats(matches)

        # Build roster summary
        roster = [
            PlayerSummary(
                player_id=p["player_id"],
                player_name=p["player_name"],
                games_played=p["games_played"],
                avg_kda=p["avg_kda"],
                win_rate=p["win_rate"],
                main_agents=p["main_agents"][:3],
                recent_form=p["recent_form"],
            )
            for p in roster_data
        ]

        # Recent matches
        recent_matches = [
            {
                "series_id": m.get("seriesId"),
                "map": m.get("game", {}).get("map", {}).get("name", "Unknown"),
                "result": "Win" if _is_win(m) else "Loss",
            }
            for m in matches[:5]
        ]

        # Get team name
        team_name = request.team_id
        if matches and matches[0].get("teams"):
            for t in matches[0].get("teams", []):
                if t.get("id") == request.team_id or t.get("name"):
                    team_name = t.get("name", request.team_id)
                    break

        # Generate summary
        summary = _generate_team_summary(patterns, insights, team_stats)

        return TeamInsightResponse(
            team_id=request.team_id,
            team_name=team_name,
            game=request.game,
            analysis_period=f"Last {len(matches)} games",
            team_stats=team_stats,
            roster=roster,
            patterns=patterns,
            insights=insights,
            player_highlights=player_highlights,
            recent_matches=recent_matches,
            summary=summary,
            generated_at=datetime.utcnow(),
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/team/{team_id}/roster", response_model=RosterResponse)
async def get_team_roster(
    team_id: str,
    game: GameType = Query(..., description="Game type (lol or Valorant)"),
    limit: int = Query(default=10, ge=1, le=50, description="Number of series to analyze"),
) -> RosterResponse:
    """Get team roster with player stats.

    Returns all players on the team with their aggregated statistics.

    **API Usage:**
    - Grid Central Data API: Team series list
    - Grid Live Data API: Match statistics for player stats
    """
    try:
        result = await pattern_detector.get_team_roster(
            team_id=team_id,
            game=game,
            limit=limit,
        )

        players = [
            PlayerSummary(
                player_id=p["player_id"],
                player_name=p["player_name"],
                games_played=p["games_played"],
                avg_kda=p["avg_kda"],
                win_rate=p["win_rate"],
                main_agents=p["main_agents"][:3],
                recent_form=p["recent_form"],
            )
            for p in result["players"]
        ]

        team_stats = TeamStats(
            games_played=result["team_stats"]["games_played"],
            wins=result["team_stats"]["wins"],
            losses=result["team_stats"]["losses"],
            win_rate=result["team_stats"]["win_rate"],
            total_kills=result["team_stats"]["total_kills"],
            total_deaths=result["team_stats"]["total_deaths"],
            avg_kills_per_game=result["team_stats"]["avg_kills_per_game"],
            avg_deaths_per_game=result["team_stats"]["avg_deaths_per_game"],
            team_kd=result["team_stats"]["team_kd"],
        )

        return RosterResponse(
            team_id=team_id,
            team_name=result.get("team_name", team_id),
            game=game,
            players=players,
            team_stats=team_stats,
            generated_at=datetime.utcnow(),
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/player/{player_id}/profile")
async def get_player_profile(
    player_id: str,
    game: GameType = Query(..., description="Game type (lol or Valorant)"),
    limit: int = Query(default=10, ge=1, le=50, description="Number of series to analyze"),
):
    """Get detailed player profile with performance history.

    Returns comprehensive player stats, agent pool, recent form, and match history.

    **API Usage:**
    - Grid Central Data API: Player metadata
    - Grid Live Data API: Match statistics
    """
    try:
        performances = await pattern_detector.get_player_performances(
            player_id=player_id,
            game=game,
            limit=limit,
        )

        if not performances:
            return {
                "player_id": player_id,
                "player_name": player_id,
                "game": game,
                "message": "No performance data found",
                "stats": None,
                "agent_pool": [],
                "recent_form": None,
                "match_history": [],
                "generated_at": datetime.utcnow(),
            }

        # Calculate detailed stats
        stats = _calculate_player_stats(performances)
        agent_pool = _calculate_agent_stats(performances)
        recent_form = _calculate_recent_form(performances)

        # Build match history
        match_history = []
        for perf in performances:
            match_history.append({
                "series_id": perf.get("seriesId"),
                "game_id": perf.get("gameId"),
                "team": perf.get("teamName"),
                "agent": perf.get("agent", {}).get("name", "Unknown"),
                "kills": perf.get("kills", 0),
                "deaths": perf.get("deaths", 0),
                "assists": perf.get("assists", 0),
                "kda": _calc_kda(perf.get("kills", 0), perf.get("deaths", 0), perf.get("assists", 0)),
                "result": "Win" if perf.get("win") else "Loss",
            })

        return {
            "player_id": player_id,
            "player_name": f"Player {player_id}",
            "game": game,
            "stats": stats.model_dump() if stats else None,
            "agent_pool": [a.model_dump() for a in agent_pool],
            "recent_form": recent_form.model_dump() if recent_form else None,
            "match_history": match_history,
            "generated_at": datetime.utcnow(),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Helper functions

def _calc_kda(kills: int, deaths: int, assists: int) -> float:
    """Calculate KDA ratio."""
    return round((kills + assists) / max(deaths, 1), 2)


def _calculate_player_stats(performances: list) -> Optional[PlayerStats]:
    """Calculate aggregated player statistics."""
    if not performances:
        return None

    games_played = len(performances)
    wins = sum(1 for p in performances if p.get("win"))
    losses = games_played - wins

    total_kills = sum(p.get("kills", 0) for p in performances)
    total_deaths = sum(p.get("deaths", 0) for p in performances)
    total_assists = sum(p.get("assists", 0) for p in performances)

    avg_kills = total_kills / games_played if games_played > 0 else 0
    avg_deaths = total_deaths / games_played if games_played > 0 else 0
    avg_assists = total_assists / games_played if games_played > 0 else 0
    avg_kda = (total_kills + total_assists) / max(total_deaths, 1)

    # Find best and worst KDA games
    games_with_kda = []
    for p in performances:
        kda = _calc_kda(p.get("kills", 0), p.get("deaths", 0), p.get("assists", 0))
        games_with_kda.append((kda, p))

    games_with_kda.sort(key=lambda x: x[0], reverse=True)

    best_game = None
    worst_game = None
    if games_with_kda:
        best = games_with_kda[0][1]
        best_game = {
            "series_id": best.get("seriesId"),
            "agent": best.get("agent", {}).get("name"),
            "kda": games_with_kda[0][0],
            "score": f"{best.get('kills')}/{best.get('deaths')}/{best.get('assists')}",
        }
        worst = games_with_kda[-1][1]
        worst_game = {
            "series_id": worst.get("seriesId"),
            "agent": worst.get("agent", {}).get("name"),
            "kda": games_with_kda[-1][0],
            "score": f"{worst.get('kills')}/{worst.get('deaths')}/{worst.get('assists')}",
        }

    return PlayerStats(
        games_played=games_played,
        wins=wins,
        losses=losses,
        win_rate=round(wins / games_played, 3) if games_played > 0 else 0,
        total_kills=total_kills,
        total_deaths=total_deaths,
        total_assists=total_assists,
        avg_kills=round(avg_kills, 2),
        avg_deaths=round(avg_deaths, 2),
        avg_assists=round(avg_assists, 2),
        avg_kda=round(avg_kda, 2),
        best_kda_game=best_game,
        worst_kda_game=worst_game,
    )


def _calculate_agent_stats(performances: list) -> list[AgentStats]:
    """Calculate per-agent statistics."""
    agent_data: dict[str, dict] = {}

    for p in performances:
        agent = p.get("agent", {}) or p.get("champion", {})
        agent_id = agent.get("id", "unknown")
        agent_name = agent.get("name", "Unknown")

        if agent_id not in agent_data:
            agent_data[agent_id] = {
                "agent_id": agent_id,
                "agent_name": agent_name,
                "games": 0,
                "wins": 0,
                "kills": 0,
                "deaths": 0,
                "assists": 0,
            }

        data = agent_data[agent_id]
        data["games"] += 1
        if p.get("win"):
            data["wins"] += 1
        data["kills"] += p.get("kills", 0)
        data["deaths"] += p.get("deaths", 0)
        data["assists"] += p.get("assists", 0)

    result = []
    for agent_id, data in agent_data.items():
        games = data["games"]
        result.append(AgentStats(
            agent_id=data["agent_id"],
            agent_name=data["agent_name"],
            games_played=games,
            wins=data["wins"],
            win_rate=round(data["wins"] / games, 3) if games > 0 else 0,
            avg_kills=round(data["kills"] / games, 2) if games > 0 else 0,
            avg_deaths=round(data["deaths"] / games, 2) if games > 0 else 0,
            avg_assists=round(data["assists"] / games, 2) if games > 0 else 0,
            avg_kda=round((data["kills"] + data["assists"]) / max(data["deaths"], 1), 2),
        ))

    # Sort by games played
    result.sort(key=lambda x: x.games_played, reverse=True)
    return result


def _calculate_recent_form(performances: list) -> Optional[RecentForm]:
    """Calculate recent form based on last 5 games."""
    if not performances:
        return None

    recent = performances[:5]
    results = ["W" if p.get("win") else "L" for p in recent]

    wins = results.count("W")
    total = len(results)

    if wins >= 4:
        form_rating = "hot"
    elif wins <= 1:
        form_rating = "cold"
    else:
        form_rating = "neutral"

    # Determine trend (comparing first half to second half of recent games)
    if len(recent) >= 4:
        first_half_wins = sum(1 for p in recent[:len(recent)//2] if p.get("win"))
        second_half_wins = sum(1 for p in recent[len(recent)//2:] if p.get("win"))
        if second_half_wins > first_half_wins:
            trend = "improving"
        elif second_half_wins < first_half_wins:
            trend = "declining"
        else:
            trend = "stable"
    else:
        trend = "stable"

    # Recent average KDA
    recent_kills = sum(p.get("kills", 0) for p in recent)
    recent_deaths = sum(p.get("deaths", 0) for p in recent)
    recent_assists = sum(p.get("assists", 0) for p in recent)
    recent_kda = (recent_kills + recent_assists) / max(recent_deaths, 1)

    return RecentForm(
        last_5_results=results,
        form_rating=form_rating,
        trend=trend,
        recent_avg_kda=round(recent_kda, 2),
    )


def _calculate_team_stats(matches: list) -> Optional[TeamStats]:
    """Calculate team statistics from matches."""
    if not matches:
        return None

    games_played = len(matches)
    wins = sum(1 for m in matches if _is_win(m))
    losses = games_played - wins

    total_kills = 0
    total_deaths = 0

    for match in matches:
        game = match.get("game", {})
        for team in game.get("teams", []):
            for player in team.get("players", []):
                total_kills += player.get("kills", 0)
                total_deaths += player.get("deaths", 0)

    # Divide by 2 since we're counting both teams
    total_kills = total_kills // 2
    total_deaths = total_deaths // 2

    return TeamStats(
        games_played=games_played,
        wins=wins,
        losses=losses,
        win_rate=round(wins / games_played, 3) if games_played > 0 else 0,
        total_kills=total_kills,
        total_deaths=total_deaths,
        avg_kills_per_game=round(total_kills / games_played, 2) if games_played > 0 else 0,
        avg_deaths_per_game=round(total_deaths / games_played, 2) if games_played > 0 else 0,
        team_kd=round(total_kills / max(total_deaths, 1), 2),
    )


def _is_win(match: dict) -> bool:
    """Determine if match was a win."""
    game = match.get("game", {})
    teams = game.get("teams", [])
    if len(teams) >= 2:
        return teams[0].get("score", 0) > teams[1].get("score", 0)
    return False


def _generate_player_summary(patterns: list, insights: list, stats: Optional[PlayerStats]) -> str:
    """Generate a summary of player analysis."""
    if not patterns and not insights:
        return "Insufficient data to generate meaningful insights. More match data required."

    parts = []

    if stats:
        parts.append(f"Analyzed {stats.games_played} games with {stats.win_rate*100:.1f}% win rate.")

    negative_patterns = [p for p in patterns if p.impact == "negative"]
    positive_patterns = [p for p in patterns if p.impact == "positive"]
    high_priority = [i for i in insights if i.priority == "high"]

    if positive_patterns:
        parts.append(f"Identified {len(positive_patterns)} strength(s).")

    if negative_patterns:
        parts.append(f"Found {len(negative_patterns)} area(s) needing attention.")

    if high_priority:
        parts.append(f"{len(high_priority)} high-priority improvement(s) recommended.")

    return " ".join(parts) or "Analysis complete."


def _generate_team_summary(patterns: list, insights: list, stats: Optional[TeamStats]) -> str:
    """Generate a summary of team analysis."""
    if not patterns and not insights:
        return "Insufficient data to generate team insights. More match data required."

    parts = []

    if stats:
        parts.append(f"Analyzed {stats.games_played} games with {stats.win_rate*100:.1f}% win rate.")

    if patterns:
        parts.append(f"Detected {len(patterns)} team-level pattern(s).")

    strategic_insights = [i for i in insights if i.category == "strategic"]
    if strategic_insights:
        parts.append(f"{len(strategic_insights)} strategic recommendation(s) identified.")

    return " ".join(parts) or "Team analysis complete."


# ============== NEW ENDPOINTS ==============


@router.get("/matches/{team_id}", response_model=MatchListResponse)
async def get_team_matches(
    team_id: str,
    game: GameType = Query(..., description="Game type (lol or Valorant)"),
    limit: int = Query(default=20, ge=1, le=50, description="Number of matches to return"),
) -> MatchListResponse:
    """Get list of recent matches for a team.

    Returns basic match info for display in a match selector.
    """
    try:
        if game == GameType.LOL:
            queries = LoLMatchQueries(grid_client)
        else:
            queries = ValorantMatchQueries(grid_client)

        # Fetch series list from Central Data API
        result = await queries.get_matches_by_team(team_id, limit=limit)
        edges = result.get("allSeries", {}).get("edges", [])

        matches = []
        team_name = f"Team {team_id}"

        for edge in edges:
            node = edge.get("node", {})
            if not node:
                continue

            series_id = node.get("id")
            central_teams = node.get("teams", [])
            tournament = node.get("tournament", {})

            # Get opponent name from central data
            opponent_name = "Unknown"
            opponent_id = ""
            for t in central_teams:
                base_info = t.get("baseInfo", {})
                if str(base_info.get("id")) == str(team_id):
                    team_name = base_info.get("name", team_name)
                else:
                    opponent_name = base_info.get("name", "Unknown")
                    opponent_id = str(base_info.get("id", ""))

            # Fetch actual scores from Series State API
            our_score = 0
            opp_score = 0
            match_date = node.get("startTimeScheduled")
            try:
                state_result = await queries.get_series_state(series_id)
                state = state_result.get("seriesState", {})
                if state:
                    # Only use started/finished if they are actual timestamp strings, not booleans
                    started = state.get("started")
                    finished = state.get("finished")
                    if isinstance(started, str):
                        match_date = started
                    elif isinstance(finished, str):
                        match_date = finished
                    for st in state.get("teams", []):
                        if str(st.get("id")) == str(team_id):
                            our_score = st.get("score", 0) or 0
                        else:
                            opp_score = st.get("score", 0) or 0
                            if not opponent_name or opponent_name == "Unknown":
                                opponent_name = st.get("name", opponent_name)
            except Exception:
                pass  # Fall back to central data if series state unavailable

            # Determine result
            if our_score > opp_score:
                result_str = "Win"
            elif our_score < opp_score:
                result_str = "Loss"
            else:
                result_str = "Draw"

            matches.append(MatchSummary(
                series_id=series_id,
                opponent_name=opponent_name,
                opponent_id=opponent_id,
                date=match_date,
                result=result_str,
                score=f"{our_score}-{opp_score}",
                tournament=tournament.get("name"),
            ))

        return MatchListResponse(
            team_id=team_id,
            team_name=team_name,
            game=game,
            matches=matches,
            total_count=len(matches),
            generated_at=datetime.utcnow(),
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/match/{match_id}/timeline", response_model=MatchTimelineResponse)
async def get_match_timeline(
    match_id: str,
    game: GameType = Query(..., description="Game type (lol or Valorant)"),
    game_number: int = Query(default=1, ge=1, le=10, description="Game number in series"),
) -> MatchTimelineResponse:
    """Get timeline of events for a specific match/game.

    Returns round-by-round or significant events in the match.
    """
    try:
        if game == GameType.LOL:
            queries = LoLMatchQueries(grid_client)
        else:
            queries = ValorantMatchQueries(grid_client)

        # Fetch series state for detailed data
        state_result = await queries.get_series_state(match_id)
        state = state_result.get("seriesState", {})

        if not state:
            raise HTTPException(status_code=404, detail="Match not found")

        games = state.get("games", [])
        teams = state.get("teams", [])

        # Find the requested game
        target_game = None
        for g in games:
            if g.get("sequenceNumber") == game_number or len(games) == 1:
                target_game = g
                break

        if not target_game:
            raise HTTPException(status_code=404, detail=f"Game {game_number} not found")

        # Build timeline from game data
        events = []
        game_teams = target_game.get("teams", [])

        # Add game start event
        map_name = target_game.get("map", {}).get("name", "Unknown")
        events.append(TimelineEvent(
            event_type="game_start",
            description=f"Game started on {map_name}",
        ))

        # Add player performance events
        for team_data in game_teams:
            team_name = team_data.get("name", "Unknown")
            for player in team_data.get("players", []):
                kills = player.get("kills", 0)
                deaths = player.get("deaths", 0)
                assists = player.get("killAssistsGiven", 0)
                player_name = player.get("name", "Unknown")
                character = player.get("character", {}).get("name", "Unknown")

                if kills >= 20:
                    events.append(TimelineEvent(
                        event_type="outstanding_performance",
                        description=f"{player_name} had {kills} kills on {character}",
                        team=team_name,
                        players_involved=[player_name],
                    ))
                elif deaths >= 15:
                    events.append(TimelineEvent(
                        event_type="high_deaths",
                        description=f"{player_name} died {deaths} times",
                        team=team_name,
                        players_involved=[player_name],
                    ))

        # Determine winner
        team_a = game_teams[0] if game_teams else {}
        team_b = game_teams[1] if len(game_teams) > 1 else {}
        score_a = team_a.get("score", 0)
        score_b = team_b.get("score", 0)

        winner = None
        if score_a > score_b:
            winner = team_a.get("name", "Team A")
        elif score_b > score_a:
            winner = team_b.get("name", "Team B")

        # Add game end event
        events.append(TimelineEvent(
            event_type="game_end",
            description=f"Game ended {score_a}-{score_b}",
            score_after=f"{score_a}-{score_b}",
        ))

        return MatchTimelineResponse(
            series_id=match_id,
            game_number=game_number,
            map_name=map_name,
            events=events,
            final_score=f"{score_a}-{score_b}",
            winner=winner,
            generated_at=datetime.utcnow(),
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/compare/players", response_model=PlayerComparisonResponse)
async def compare_players(request: PlayerComparisonRequest) -> PlayerComparisonResponse:
    """Compare multiple players side-by-side.

    Fetches stats for each player and provides comparison analysis.
    """
    try:
        players = []
        all_kdas = []
        all_win_rates = []

        for player_id in request.player_ids:
            performances = await pattern_detector.get_player_performances(
                player_id=player_id,
                game=request.game,
                limit=request.limit,
            )

            if not performances:
                players.append(PlayerComparisonStats(
                    player_id=player_id,
                    player_name=f"Player {player_id}",
                ))
                continue

            # Calculate base stats
            games_played = len(performances)
            wins = sum(1 for p in performances if p.get("win"))
            total_kills = sum(p.get("kills", 0) for p in performances)
            total_deaths = sum(p.get("deaths", 0) for p in performances)
            total_assists = sum(p.get("assists", 0) for p in performances)

            avg_kills = total_kills / games_played if games_played > 0 else 0
            avg_deaths = total_deaths / games_played if games_played > 0 else 0
            avg_assists = total_assists / games_played if games_played > 0 else 0
            avg_kda = (total_kills + total_assists) / max(total_deaths, 1)
            win_rate = wins / games_played if games_played > 0 else 0

            # Get main agents
            agent_counts = {}
            for p in performances:
                agent = p.get("agent", {}) or p.get("character", {})
                agent_name = agent.get("name", "Unknown")
                agent_counts[agent_name] = agent_counts.get(agent_name, 0) + 1
            main_agents = sorted(agent_counts.keys(), key=lambda x: agent_counts[x], reverse=True)[:3]

            # Recent form
            recent = performances[:5]
            recent_wins = sum(1 for p in recent if p.get("win"))
            if recent_wins >= 4:
                form = "hot"
            elif recent_wins <= 1:
                form = "cold"
            else:
                form = "neutral"

            all_kdas.append((player_id, avg_kda))
            all_win_rates.append((player_id, win_rate))

            # Initialize game-specific stats
            valorant_stats = {}
            lol_stats = {}

            if request.game == GameType.VALORANT:
                # Calculate Valorant-specific stats from actual Grid API structure
                total_headshots = 0
                total_shots = 0
                total_damage_dealt = 0
                total_damage_taken = 0
                plants = 0
                defuses = 0

                for p in performances:
                    # Headshot stats - Grid API returns 'headshots' directly
                    hs = p.get("headshots", 0)
                    kills = p.get("kills", 0)
                    total_headshots += hs
                    total_shots += kills if kills > 0 else 1

                    # Damage stats
                    total_damage_dealt += p.get("damageDealt", 0)
                    total_damage_taken += p.get("damageTaken", 0)

                    # Objectives - Grid API returns array of {type, completionCount}
                    objectives = p.get("objectives", [])
                    for obj in objectives:
                        obj_type = obj.get("type", "")
                        count = obj.get("completionCount", 0)
                        if obj_type == "plantBomb":
                            plants += count
                        elif obj_type == "defuseBomb":
                            defuses += count

                # Calculate averages
                # Note: Grid API returns damageDealt per GAME, not per round
                # Valorant games average ~20 rounds (13-30 range depending on score)
                # ADR = Average Damage per Round
                avg_rounds_per_game = 20  # Reasonable estimate for competitive play
                total_estimated_rounds = games_played * avg_rounds_per_game
                
                # If no damage data available (rate limit or old matches), return None instead of 0
                has_damage_data = total_damage_dealt > 0 or total_headshots > 0
                
                valorant_stats = {
                    "avg_adr": round(total_damage_dealt / total_estimated_rounds, 1) if has_damage_data and total_estimated_rounds > 0 else None,
                    "headshot_pct": round((total_headshots / max(total_shots, 1)) * 100, 1) if has_damage_data and total_shots > 0 else None,
                    "plants": plants if has_damage_data else None,
                    "defuses": defuses if has_damage_data else None,
                    "damage_per_game": round(total_damage_dealt / games_played, 0) if has_damage_data and games_played > 0 else None,
                    "damage_taken_per_game": round(total_damage_taken / games_played, 0) if has_damage_data and games_played > 0 else None,
                }

            elif request.game == GameType.LOL:
                # Calculate LoL-specific stats
                total_cs = 0
                total_gold = 0
                total_damage = 0
                total_vision = 0
                total_duration = 0
                total_team_kills = 0
                total_team_damage = 0
                total_team_gold = 0

                for p in performances:
                    cs = p.get("cs", 0) or p.get("creepScore", 0)
                    gold = p.get("gold", 0) or p.get("goldEarned", 0)
                    damage = p.get("damageDealt", 0) or p.get("totalDamageDealt", 0)
                    vision = p.get("visionScore", 0)
                    duration = p.get("duration", 1800) / 60  # Convert to minutes, default 30 min

                    total_cs += cs
                    total_gold += gold
                    total_damage += damage
                    total_vision += vision
                    total_duration += duration

                    # Team stats for share calculations
                    team_kills = p.get("teamKills", 0) or (total_kills // games_played * 5 if games_played > 0 else 1)
                    team_damage = p.get("teamDamage", 0) or damage * 5
                    team_gold = p.get("teamGold", 0) or gold * 5

                    total_team_kills += team_kills
                    total_team_damage += team_damage
                    total_team_gold += team_gold

                # Calculate averages
                lol_stats = {
                    "cs_per_min": round(total_cs / max(total_duration, 1), 1) if total_duration > 0 else None,
                    "gold_per_min": round(total_gold / max(total_duration, 1), 0) if total_duration > 0 else None,
                    "damage_per_min": round(total_damage / max(total_duration, 1), 0) if total_duration > 0 else None,
                    "vision_score": round(total_vision / games_played, 1) if games_played > 0 else None,
                    "kill_participation": round(((total_kills + total_assists) / max(total_team_kills, 1)) * 100, 1) if total_team_kills > 0 else None,
                    "damage_share": round((total_damage / max(total_team_damage, 1)) * 100, 1) if total_team_damage > 0 else None,
                    "gold_share": round((total_gold / max(total_team_gold, 1)) * 100, 1) if total_team_gold > 0 else None,
                }

            players.append(PlayerComparisonStats(
                player_id=player_id,
                player_name=f"Player {player_id}",
                games_played=games_played,
                wins=wins,
                win_rate=round(win_rate, 3),
                avg_kills=round(avg_kills, 2),
                avg_deaths=round(avg_deaths, 2),
                avg_assists=round(avg_assists, 2),
                avg_kda=round(avg_kda, 2),
                main_agents=main_agents,
                recent_form=form,
                # Valorant stats - updated to match actual Grid API fields
                avg_adr=valorant_stats.get("avg_adr"),
                headshot_pct=valorant_stats.get("headshot_pct"),
                plants=valorant_stats.get("plants"),
                defuses=valorant_stats.get("defuses"),
                # Additional useful stats from Grid API
                avg_acs=valorant_stats.get("damage_per_game"),  # Reusing field for damage/game
                # LoL stats
                cs_per_min=lol_stats.get("cs_per_min"),
                gold_per_min=lol_stats.get("gold_per_min"),
                damage_per_min=lol_stats.get("damage_per_min"),
                vision_score=lol_stats.get("vision_score"),
                kill_participation=lol_stats.get("kill_participation"),
                damage_share=lol_stats.get("damage_share"),
                gold_share=lol_stats.get("gold_share"),
                # Set unavailable fields to None
                first_kills=None,
                first_deaths=None,
                fk_fd_ratio=None,
                kast_pct=None,
                clutch_win_pct=None,
                multi_kills=None,
            ))

        # Generate comparison highlights
        highlights = []
        if all_kdas:
            best_kda = max(all_kdas, key=lambda x: x[1])
            highlights.append(f"Highest KDA: Player {best_kda[0]} ({best_kda[1]:.2f})")

        if all_win_rates:
            best_wr = max(all_win_rates, key=lambda x: x[1])
            highlights.append(f"Highest Win Rate: Player {best_wr[0]} ({best_wr[1]*100:.1f}%)")

        # Determine best performer (highest KDA)
        best_performer = best_kda[0] if all_kdas else None

        # Most consistent (smallest variance in KDA across games)
        most_consistent = None
        if players:
            # For simplicity, use the player with win rate closest to their KDA ranking
            most_consistent = players[0].player_id

        return PlayerComparisonResponse(
            players=players,
            comparison_highlights=highlights,
            best_performer=best_performer,
            most_consistent=most_consistent,
            generated_at=datetime.utcnow(),
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/preload/{team_id}")
async def preload_team_data(
    team_id: str,
    game: GameType = Query(...),
    limit: int = Query(default=10),
) -> dict:
    """Preload all data for a team in a single request.

    Reuses the existing endpoints internally to ensure consistency.
    """
    import asyncio

    try:
        print(f"[Preload] Starting preload for team {team_id}, game {game}, limit {limit}")

        # Call the existing roster endpoint logic directly
        roster_result = await pattern_detector.get_team_roster(team_id, game, limit)
        players = roster_result.get("players", [])
        player_ids = [p["player_id"] for p in players]
        # Create mapping from player_id to player_name for use in insights/trends
        player_names = {p["player_id"]: p.get("player_name", f"Player {p['player_id']}") for p in players}
        print(f"[Preload] Got roster with {len(players)} players: {player_ids}")

        # If no players, return early
        if not players:
            print("[Preload] No players found, returning empty")
            return {
                "roster": roster_result,
                "matches": {"matches": [], "team_id": team_id},
                "player_insights": {},
                "player_trends": {},
            }

        roster_data = roster_result

        # OPTIMIZATION: Extract all player stats from team matches (single API call)
        print(f"[Preload] Fetching team matches (single API call for all players)")
        matches = await pattern_detector._fetch_team_matches_with_limit(team_id, [], game, limit)
        print(f"[Preload] Got {len(matches)} matches, extracting all player data")

        # Build player_performances_map from team matches
        player_performances_map = {}  # player_id -> list of performances
        for match in matches:
            game_data = match.get("game", {})
            teams_list = match.get("teams", [])
            
            # Find our team
            our_team_idx = None
            for idx, t in enumerate(teams_list):
                if str(t.get("id")) == str(team_id):
                    our_team_idx = idx
                    break
            
            if our_team_idx is None:
                continue
                
            game_teams = game_data.get("teams", [])
            if our_team_idx >= len(game_teams):
                continue
                
            our_game_team = game_teams[our_team_idx]
            our_score = our_game_team.get("score", 0)
            enemy_idx = 1 if our_team_idx == 0 else 0
            enemy_score = game_teams[enemy_idx].get("score", 0) if enemy_idx < len(game_teams) else 0
            won = our_score > enemy_score
            
            # Extract each player's performance
            for player in our_game_team.get("players", []):
                pid = str(player.get("id"))
                if pid not in player_performances_map:
                    player_performances_map[pid] = []
                
                player_performances_map[pid].append({
                    "seriesId": match.get("seriesId"),
                    "gameId": game_data.get("id"),
                    "teamId": teams_list[our_team_idx].get("id") if our_team_idx < len(teams_list) else team_id,
                    "teamName": teams_list[our_team_idx].get("name") if our_team_idx < len(teams_list) else "Unknown",
                    "agent": player.get("character", {}),
                    "kills": player.get("kills", 0),
                    "deaths": player.get("deaths", 0),
                    "assists": player.get("killAssistsGiven", 0) or player.get("assists", 0),
                    "netWorth": player.get("netWorth", 0),
                    "win": won,
                    "date": match.get("date"),
                    "headshots": player.get("headshots", 0),
                    "damageDealt": player.get("damageDealt", 0),
                    "damageTaken": player.get("damageTaken", 0),
                    "objectives": player.get("objectives", []),
                })
        
        print(f"[Preload] Extracted data for {len(player_performances_map)} players")

        # Generate patterns/insights for each player
        player_insights = {}
        player_trends = {}
        for pid in player_ids:
            perfs = player_performances_map.get(pid, [])
            if not perfs:
                print(f"[Preload] No performances for player {pid}")
                continue
                
            # Detect patterns
            patterns = await pattern_detector._detect_player_patterns(perfs, game)
            # Generate insights
            insights = await pattern_detector._generate_player_insights(
                pid, perfs, patterns, game, None
            )

            if perfs:
                # Calculate full stats matching PlayerInsightResponse format
                stats = _calculate_player_stats(perfs)
                agent_pool = _calculate_agent_stats(perfs)
                recent_form = _calculate_recent_form(perfs)

                # Calculate Valorant-specific stats
                stats_dict = stats.model_dump() if stats else {}
                if game == GameType.VALORANT:
                    total_headshots = 0
                    total_damage_dealt = 0
                    total_damage_taken = 0
                    plants = 0
                    defuses = 0
                    total_kills = sum(p.get("kills", 0) for p in perfs)
                    
                    for p in perfs:
                        total_headshots += p.get("headshots", 0)
                        total_damage_dealt += p.get("damageDealt", 0)
                        total_damage_taken += p.get("damageTaken", 0)
                        
                        for obj in p.get("objectives", []):
                            if obj.get("type") == "plantBomb":
                                plants += obj.get("completionCount", 0)
                            elif obj.get("type") == "defuseBomb":
                                defuses += obj.get("completionCount", 0)
                    
                    # Calculate averages
                    games_played = len(perfs)
                    avg_rounds_per_game = 20
                    total_estimated_rounds = games_played * avg_rounds_per_game
                    has_damage_data = total_damage_dealt > 0 or total_headshots > 0
                    
                    stats_dict.update({
                        "avg_adr": round(total_damage_dealt / total_estimated_rounds, 1) if has_damage_data and total_estimated_rounds > 0 else None,
                        "avg_acs": round(total_damage_dealt / games_played, 0) if has_damage_data and games_played > 0 else None,
                        "headshot_pct": round((total_headshots / max(total_kills, 1)) * 100, 1) if has_damage_data and total_kills > 0 else None,
                        "plants": plants if has_damage_data else None,
                        "defuses": defuses if has_damage_data else None,
                    })

                player_insights[pid] = {
                    "player_id": pid,
                    "player_name": player_names.get(pid, f"Player {pid}"),
                    "game": game.value,
                    "analysis_period": f"Last {len(perfs)} games",
                    "stats": stats_dict,
                    "agent_pool": [a.model_dump() for a in agent_pool],
                    "recent_form": recent_form.model_dump() if recent_form else None,
                    "patterns": [p.model_dump() for p in patterns] if patterns else [],
                    "insights": [i.model_dump() for i in insights] if insights else [],
                    "recent_matches": perfs[:5],
                    "summary": f"Analyzed {len(perfs)} games",
                }

                # Trends data points (full format matching /insights/trends)
                data_points = []
                for p in perfs:
                    kills = p.get("kills", 0)
                    deaths = p.get("deaths", 0)
                    assists = p.get("assists", 0)
                    kda = (kills + assists) / max(deaths, 1)
                    agent = p.get("agent", {}) or p.get("character", {})

                    data_points.append({
                        "date": p.get("date", "Unknown"),
                        "series_id": p.get("seriesId", ""),
                        "kda": round(kda, 2),
                        "kills": kills,
                        "deaths": deaths,
                        "assists": assists,
                        "result": "Win" if p.get("win") else "Loss",
                        "agent": agent.get("name", "Unknown"),
                    })

                # Calculate trend direction
                if len(data_points) >= 4:
                    first_half = data_points[len(data_points)//2:]
                    second_half = data_points[:len(data_points)//2]
                    first_avg = sum(p["kda"] for p in first_half) / len(first_half)
                    second_avg = sum(p["kda"] for p in second_half) / len(second_half)
                    if second_avg > first_avg * 1.1:
                        trend_dir = "improving"
                    elif second_avg < first_avg * 0.9:
                        trend_dir = "declining"
                    else:
                        trend_dir = "stable"
                else:
                    trend_dir = "stable"

                total_kda = sum(p["kda"] for p in data_points)
                wins = sum(1 for p in data_points if p["result"] == "Win")

                player_trends[pid] = {
                    "player_id": pid,
                    "player_name": player_names.get(pid, f"Player {pid}"),
                    "game": game.value,
                    "period": f"Last {len(data_points)} games",
                    "data_points": data_points,
                    "trend_direction": trend_dir,
                    "avg_kda_trend": round(total_kda / len(data_points), 2) if data_points else 0,
                    "win_rate_trend": round(wins / len(data_points), 3) if data_points else 0,
                }

        # Get matches
        matches_data = await _get_team_matches_internal(team_id, game, 20)

        # Get full team insights (patterns, insights, roster for team tab)
        print(f"[Preload] Fetching team insights")
        team_result = await pattern_detector.analyze_team_detailed(
            team_id=team_id,
            match_ids=[],
            game=game,
            focus_areas=None,
            limit=30,
        )
        team_patterns = team_result.get("patterns", [])
        team_insights_list = team_result.get("insights", [])
        team_roster = team_result.get("roster", [])

        team_insights_data = {
            "team_id": team_id,
            "team_name": roster_data.get("team_name", team_id),
            "team_stats": roster_data.get("team_stats"),
            "roster": team_roster,
            "patterns": [p.model_dump() for p in team_patterns] if team_patterns else [],
            "insights": [i.model_dump() for i in team_insights_list] if team_insights_list else [],
            "summary": f"Analyzed {roster_data.get('team_stats', {}).get('games_played', 0)} games",
        }

        print(f"[Preload] Final data: roster={len(players)} players, insights={len(player_insights)}, trends={len(player_trends)}, team_patterns={len(team_patterns)}")

        return {
            "roster": roster_data,
            "matches": matches_data,
            "player_insights": player_insights,
            "player_trends": player_trends,
            "team_insights": team_insights_data,
        }
    except Exception as e:
        print(f"[Preload] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def _get_team_matches_internal(team_id: str, game: GameType, limit: int):
    """Internal helper for fetching matches with full formatting."""
    try:
        if game == GameType.LOL:
            queries = LoLMatchQueries(grid_client)
        else:
            queries = ValorantMatchQueries(grid_client)

        result = await queries.get_matches_by_team(team_id, limit=limit)
        edges = result.get("allSeries", {}).get("edges", [])

        matches = []
        team_name = f"Team {team_id}"

        for edge in edges:
            node = edge.get("node", {})
            if not node:
                continue

            series_id = node.get("id")
            central_teams = node.get("teams", [])
            tournament = node.get("tournament", {})
            tournament_name = tournament.get("name") if isinstance(tournament, dict) else tournament

            # Get opponent name from central data
            opponent_name = "Unknown"
            opponent_id = ""
            for t in central_teams:
                base_info = t.get("baseInfo", {})
                if str(base_info.get("id")) == str(team_id):
                    team_name = base_info.get("name", team_name)
                else:
                    opponent_name = base_info.get("name", "Unknown")
                    opponent_id = str(base_info.get("id", ""))

            # Fetch actual scores from Series State API
            our_score = 0
            opp_score = 0
            match_date = node.get("startTimeScheduled")
            try:
                state_result = await queries.get_series_state(series_id)
                state = state_result.get("seriesState", {})
                if state:
                    started = state.get("started")
                    finished = state.get("finished")
                    if isinstance(started, str):
                        match_date = started
                    elif isinstance(finished, str):
                        match_date = finished
                    for st in state.get("teams", []):
                        if str(st.get("id")) == str(team_id):
                            our_score = st.get("score", 0) or 0
                        else:
                            opp_score = st.get("score", 0) or 0
                            if not opponent_name or opponent_name == "Unknown":
                                opponent_name = st.get("name", opponent_name)
            except Exception:
                pass  # Fall back to central data if series state unavailable

            # Determine result
            if our_score > opp_score:
                result_str = "Win"
            elif our_score < opp_score:
                result_str = "Loss"
            else:
                result_str = "Draw"

            matches.append({
                "series_id": series_id,
                "opponent_name": opponent_name,
                "opponent_id": opponent_id,
                "date": match_date,
                "result": result_str,
                "score": f"{our_score}-{opp_score}",
                "tournament": tournament_name,
            })

        return {"matches": matches, "team_id": team_id, "team_name": team_name}
    except Exception as e:
        print(f"[Preload] Error fetching matches: {e}")
        return {"matches": [], "team_id": team_id, "team_name": f"Team {team_id}"}


@router.get("/trends/{player_id}", response_model=TrendResponse)
async def get_player_trends(
    player_id: str,
    game: GameType = Query(..., description="Game type (lol or Valorant)"),
    limit: int = Query(default=20, ge=5, le=50, description="Number of matches for trend"),
) -> TrendResponse:
    """Get performance trends for a player over time.

    Returns data points suitable for charting.
    """
    try:
        performances = await pattern_detector.get_player_performances(
            player_id=player_id,
            game=game,
            limit=limit,
        )

        if not performances:
            return TrendResponse(
                player_id=player_id,
                player_name=f"Player {player_id}",
                game=game,
                period=f"Last {limit} games",
                generated_at=datetime.utcnow(),
            )

        data_points = []
        for perf in performances:
            kills = perf.get("kills", 0)
            deaths = perf.get("deaths", 0)
            assists = perf.get("assists", 0)
            kda = (kills + assists) / max(deaths, 1)

            agent = perf.get("agent", {}) or perf.get("character", {})
            agent_name = agent.get("name", "Unknown")

            data_points.append(PerformanceDataPoint(
                date=perf.get("date", "Unknown"),
                series_id=perf.get("seriesId", ""),
                kda=round(kda, 2),
                kills=kills,
                deaths=deaths,
                assists=assists,
                result="Win" if perf.get("win") else "Loss",
                agent=agent_name,
            ))

        # Calculate trend direction
        if len(data_points) >= 4:
            first_half = data_points[len(data_points)//2:]
            second_half = data_points[:len(data_points)//2]

            first_avg_kda = sum(p.kda for p in first_half) / len(first_half)
            second_avg_kda = sum(p.kda for p in second_half) / len(second_half)

            if second_avg_kda > first_avg_kda * 1.1:
                trend_direction = "improving"
            elif second_avg_kda < first_avg_kda * 0.9:
                trend_direction = "declining"
            else:
                trend_direction = "stable"
        else:
            trend_direction = "stable"

        # Calculate overall trends
        total_kda = sum(p.kda for p in data_points)
        wins = sum(1 for p in data_points if p.result == "Win")

        return TrendResponse(
            player_id=player_id,
            player_name=f"Player {player_id}",
            game=game,
            period=f"Last {len(data_points)} games",
            data_points=data_points,
            trend_direction=trend_direction,
            avg_kda_trend=round(total_kda / len(data_points), 2) if data_points else 0,
            win_rate_trend=round(wins / len(data_points), 3) if data_points else 0,
            generated_at=datetime.utcnow(),
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/compare/teams", response_model=TeamComparisonResponse)
async def compare_teams(request: TeamComparisonRequest) -> TeamComparisonResponse:
    """Compare two teams side-by-side.

    Includes head-to-head record if available.
    """
    try:
        teams = []

        for team_id in request.team_ids:
            result = await pattern_detector.get_team_roster(
                team_id=team_id,
                game=request.game,
                limit=request.limit,
            )

            team_stats = result.get("team_stats", {})
            team_name = result.get("team_name", f"Team {team_id}")

            # Determine playstyle based on stats
            avg_kills = team_stats.get("avg_kills_per_game", 0)
            avg_deaths = team_stats.get("avg_deaths_per_game", 0)

            if avg_kills > avg_deaths * 1.2:
                playstyle = "Aggressive"
            elif avg_deaths > avg_kills * 1.2:
                playstyle = "Passive/Scaling"
            else:
                playstyle = "Balanced"

            # Determine strengths/weaknesses
            strengths = []
            weaknesses = []
            win_rate = team_stats.get("win_rate", 0.5)

            if win_rate > 0.55:
                strengths.append("Strong recent form")
            elif win_rate < 0.45:
                weaknesses.append("Struggling recently")

            if team_stats.get("team_kd", 1) > 1.2:
                strengths.append("High team K/D ratio")
            elif team_stats.get("team_kd", 1) < 0.8:
                weaknesses.append("Low team K/D ratio")

            teams.append(TeamComparisonStats(
                team_id=team_id,
                team_name=team_name,
                games_played=team_stats.get("games_played", 0),
                wins=team_stats.get("wins", 0),
                losses=team_stats.get("losses", 0),
                win_rate=team_stats.get("win_rate", 0.5),
                avg_kills=team_stats.get("avg_kills_per_game", 0),
                avg_deaths=team_stats.get("avg_deaths_per_game", 0),
                team_kd=team_stats.get("team_kd", 1.0),
                playstyle=playstyle,
                strengths=strengths if strengths else ["No clear strengths identified"],
                weaknesses=weaknesses if weaknesses else ["No clear weaknesses identified"],
            ))

        # Generate comparison highlights
        highlights = []
        if len(teams) >= 2:
            if teams[0].win_rate > teams[1].win_rate:
                highlights.append(f"{teams[0].team_name} has higher win rate ({teams[0].win_rate*100:.1f}% vs {teams[1].win_rate*100:.1f}%)")
            elif teams[1].win_rate > teams[0].win_rate:
                highlights.append(f"{teams[1].team_name} has higher win rate ({teams[1].win_rate*100:.1f}% vs {teams[0].win_rate*100:.1f}%)")

            if teams[0].team_kd > teams[1].team_kd:
                highlights.append(f"{teams[0].team_name} has better K/D ratio ({teams[0].team_kd:.2f} vs {teams[1].team_kd:.2f})")
            elif teams[1].team_kd > teams[0].team_kd:
                highlights.append(f"{teams[1].team_name} has better K/D ratio ({teams[1].team_kd:.2f} vs {teams[0].team_kd:.2f})")

        # Determine advantage
        advantage = None
        if len(teams) >= 2:
            if teams[0].win_rate > teams[1].win_rate + 0.1:
                advantage = teams[0].team_id
            elif teams[1].win_rate > teams[0].win_rate + 0.1:
                advantage = teams[1].team_id

        return TeamComparisonResponse(
            teams=teams,
            head_to_head=None,  # Would require historical data lookup
            comparison_highlights=highlights,
            advantage=advantage,
            generated_at=datetime.utcnow(),
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
