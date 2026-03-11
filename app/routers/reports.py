"""Reports router for scouting report generation."""

import uuid
from datetime import datetime
from fastapi import APIRouter, HTTPException


from shared.grid_client import GridClient
from shared.grid_client.lol import LoLMatchQueries, LoLTeamQueries
from shared.grid_client.valorant import ValorantMatchQueries, ValorantTeamQueries

from app.models.schemas import (
    ScoutingReportRequest,
    ScoutingReportResponse,
    CounterStrategyRequest,
    CounterStrategyResponse,
    GameType,
    TeamSearchResult,
    TeamSearchResponse,
    ReportHistoryItem,
    ReportHistoryResponse,
    TeamCompareRequest,
    TeamCompareResponse,
    DetailedMapStats,
    MapStatsResponse,
    PlayerThreat,
    ThreatRankingResponse,
)
from app.services.opponent_analyzer import OpponentAnalyzer
from app.services.player_profiler import PlayerProfiler
from app.services.composition_tracker import CompositionTracker
from app.services.counter_strategy import CounterStrategyGenerator

router = APIRouter()

# Grid client for fetching match IDs
grid_client = GridClient()

# Service instances
opponent_analyzer = OpponentAnalyzer()
player_profiler = PlayerProfiler()
composition_tracker = CompositionTracker()
counter_strategy_gen = CounterStrategyGenerator()

# In-memory report storage (would use database in production)
report_storage: dict[str, ScoutingReportResponse] = {}


async def _fetch_match_ids(team_id: str, num_matches: int, game: GameType) -> list[str]:
    """Fetch match IDs for a team."""
    if game == GameType.LOL:
        queries = LoLMatchQueries(grid_client)
    else:
        queries = ValorantMatchQueries(grid_client)

    result = await queries.get_matches_by_team(team_id, limit=num_matches)
    # API returns allSeries.edges, not team.matches.edges
    edges = result.get("allSeries", {}).get("edges", [])
    match_ids = [edge.get("node", {}).get("id") for edge in edges if edge.get("node", {}).get("id")]
    return match_ids[:num_matches]


@router.post("/generate", response_model=ScoutingReportResponse)
async def generate_scouting_report(
    request: ScoutingReportRequest,
) -> ScoutingReportResponse:
    """Generate a comprehensive scouting report for an opponent.

    Analyzes opponent team patterns, player tendencies, and compositions
    to create actionable preparation material.
    """
    try:
        # Fetch match IDs for analysis
        match_ids = await _fetch_match_ids(
            request.opponent_team_id,
            request.num_recent_matches,
            request.game,
        )

        # Analyze opponent team
        team_profile = await opponent_analyzer.analyze_team(
            team_id=request.opponent_team_id,
            num_matches=request.num_recent_matches,
            game=request.game,
        )

        # Get player profiles if requested
        player_profiles = []
        if request.include_player_profiles:
            player_profiles = await player_profiler.profile_team_players(
                team_id=request.opponent_team_id,
                match_ids=match_ids,
                game=request.game,
            )

        # Get composition analysis if requested
        compositions = []
        if request.include_composition_analysis:
            compositions = await composition_tracker.analyze_compositions(
                team_id=request.opponent_team_id,
                match_ids=match_ids,
                game=request.game,
            )

        # Generate key findings
        key_findings = _generate_key_findings(team_profile, player_profiles, compositions)

        # Generate preparation priorities
        prep_priorities = _generate_prep_priorities(team_profile, request.game)

        # Generate executive summary
        executive_summary = _generate_executive_summary(
            team_profile, player_profiles, compositions, request.game
        )

        # Create report
        report_id = str(uuid.uuid4())
        report = ScoutingReportResponse(
            report_id=report_id,
            opponent_team=team_profile,
            player_profiles=player_profiles,
            compositions=compositions,
            key_findings=key_findings,
            preparation_priorities=prep_priorities,
            executive_summary=executive_summary,
            generated_at=datetime.utcnow(),
            matches_analyzed=request.num_recent_matches,
        )

        # Store report for retrieval
        report_storage[report_id] = report

        return report

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{report_id}", response_model=ScoutingReportResponse)
async def get_report(report_id: str) -> ScoutingReportResponse:
    """Retrieve a previously generated scouting report."""
    if report_id not in report_storage:
        raise HTTPException(status_code=404, detail="Report not found")

    return report_storage[report_id]


@router.post("/counter-strategy", response_model=CounterStrategyResponse)
async def generate_counter_strategy(
    request: CounterStrategyRequest,
) -> CounterStrategyResponse:
    """Generate counter-strategy recommendations against an opponent.

    Analyzes both teams to identify exploitable weaknesses and
    generate actionable game plans.
    """
    try:
        (
            recommendations,
            win_conditions,
            draft_map_recs,
            key_matchups,
            summary,
        ) = await counter_strategy_gen.generate_counter_strategy(
            opponent_team_id=request.opponent_team_id,
            our_team_id=request.our_team_id,
            game=request.game,
            num_opponent_matches=request.num_opponent_matches,
            num_our_matches=request.num_our_matches,
        )

        # Determine if draft or map recommendations based on game
        from app.models.schemas import GameType
        if request.game == GameType.LOL:
            return CounterStrategyResponse(
                opponent_team_id=request.opponent_team_id,
                our_team_id=request.our_team_id,
                recommendations=recommendations,
                win_conditions=win_conditions,
                draft_recommendations=draft_map_recs,
                map_recommendations=[],
                key_matchups=key_matchups,
                summary=summary,
                generated_at=datetime.utcnow(),
            )
        else:
            return CounterStrategyResponse(
                opponent_team_id=request.opponent_team_id,
                our_team_id=request.our_team_id,
                recommendations=recommendations,
                win_conditions=win_conditions,
                draft_recommendations=[],
                map_recommendations=draft_map_recs,
                key_matchups=key_matchups,
                summary=summary,
                generated_at=datetime.utcnow(),
            )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{report_id}")
async def delete_report(report_id: str):
    """Delete a stored scouting report."""
    if report_id not in report_storage:
        raise HTTPException(status_code=404, detail="Report not found")

    del report_storage[report_id]
    return {"status": "deleted", "report_id": report_id}


def _generate_key_findings(
    team_profile,
    player_profiles: list,
    compositions: list,
) -> list[str]:
    """Generate key findings from analysis."""
    findings = []

    # Team-level findings
    if team_profile.strengths:
        findings.append(f"Team strength: {team_profile.strengths[0]}")
    if team_profile.weaknesses:
        findings.append(f"Exploitable weakness: {team_profile.weaknesses[0]}")

    # Player-level findings
    high_threat_players = [p for p in player_profiles if p.threat_level == "high"]
    if high_threat_players:
        findings.append(
            f"High threat player(s): {', '.join(p.player_name for p in high_threat_players)}"
        )

    # Composition findings
    if compositions:
        top_comp = max(compositions, key=lambda c: c.games_played, default=None)
        if top_comp:
            findings.append(
                f"Most played composition ({top_comp.games_played} games): "
                f"{', '.join(top_comp.composition[:3])}..."
            )

    return findings


def _generate_prep_priorities(team_profile, game) -> list[str]:
    """Generate preparation priorities."""
    priorities = []

    # Based on weaknesses
    for weakness in team_profile.weaknesses[:2]:
        priorities.append(f"Practice exploiting: {weakness}")

    # Based on their strengths (what to defend against)
    for strength in team_profile.strengths[:2]:
        priorities.append(f"Prepare defense against: {strength}")

    # Game-specific
    from app.models.schemas import GameType
    if game == GameType.LOL:
        priorities.append("Review their draft tendencies")
        priorities.append("Study objective timing and setups")
    else:
        priorities.append("Review map preferences and veto strategy")
        priorities.append("Study default setups on likely maps")

    return priorities


def _generate_executive_summary(
    team_profile,
    player_profiles: list,
    compositions: list,
    game,
) -> str:
    """Generate executive summary for the report."""
    from app.models.schemas import GameType

    record = team_profile.overall_record
    total_games = (record.get("wins", 0) + record.get("losses", 0)) if record else 0
    win_rate = record.get("wins", 0) / total_games if total_games > 0 else 0.5

    summary_parts = [
        f"{team_profile.team_name} is a {team_profile.playstyle.lower()} team "
        f"with a {win_rate:.0%} win rate in recent matches.",
    ]

    if team_profile.identity:
        summary_parts.append(f"Team identity: {team_profile.identity}.")

    high_threat = [p for p in player_profiles if p.threat_level == "high"]
    if high_threat:
        summary_parts.append(
            f"Key player(s) to watch: {', '.join(p.player_name for p in high_threat)}."
        )

    if team_profile.weaknesses:
        summary_parts.append(
            f"Primary weakness to exploit: {team_profile.weaknesses[0]}."
        )

    return " ".join(summary_parts)


# ============== NEW ENDPOINTS ==============


@router.get("/teams/search", response_model=TeamSearchResponse)
async def search_teams(
    name: str,
    game: GameType,
    limit: int = 20,
) -> TeamSearchResponse:
    """Search for teams by name.

    Returns matching teams with their IDs for report generation.
    """
    try:
        if game == GameType.LOL:
            queries = LoLTeamQueries(grid_client)
        else:
            queries = ValorantTeamQueries(grid_client)

        result = await queries.get_teams(
            limit=limit,
            name_contains=name,
        )

        edges = result.get("teams", {}).get("edges", [])
        results = []

        for edge in edges:
            node = edge.get("node", {})
            if node:
                results.append(TeamSearchResult(
                    team_id=node.get("id", ""),
                    team_name=node.get("name", "Unknown"),
                    name_shortened=node.get("nameShortened"),
                    logo_url=node.get("logoUrl"),
                    primary_color=node.get("colorPrimary"),
                ))

        return TeamSearchResponse(
            query=name,
            game=game,
            results=results,
            total_count=len(results),
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/reports/history", response_model=ReportHistoryResponse)
async def get_report_history(
    limit: int = 20,
) -> ReportHistoryResponse:
    """Get history of previously generated reports.

    Returns list of reports stored in memory.
    """
    reports = []

    for report_id, report in list(report_storage.items())[:limit]:
        reports.append(ReportHistoryItem(
            report_id=report_id,
            opponent_team_id=report.opponent_team.team_id,
            opponent_team_name=report.opponent_team.team_name,
            game=GameType.VALORANT if report.opponent_team.map_preferences else GameType.LOL,
            matches_analyzed=report.matches_analyzed,
            generated_at=report.generated_at,
        ))

    return ReportHistoryResponse(
        reports=reports,
        total_count=len(reports),
    )


@router.post("/compare", response_model=TeamCompareResponse)
async def compare_teams(request: TeamCompareRequest) -> TeamCompareResponse:
    """Generate a comparison report between two teams.

    Analyzes both teams and provides a comparison summary.
    """
    try:
        # Analyze both teams
        team_a_profile = await opponent_analyzer.analyze_team(
            team_id=request.team_a_id,
            num_matches=request.num_matches,
            game=request.game,
        )

        team_b_profile = await opponent_analyzer.analyze_team(
            team_id=request.team_b_id,
            num_matches=request.num_matches,
            game=request.game,
        )

        # Generate key differences
        key_differences = []

        # Compare win rates
        a_record = team_a_profile.overall_record
        b_record = team_b_profile.overall_record
        a_games = a_record.get("wins", 0) + a_record.get("losses", 0)
        b_games = b_record.get("wins", 0) + b_record.get("losses", 0)
        a_wr = a_record.get("wins", 0) / a_games if a_games > 0 else 0.5
        b_wr = b_record.get("wins", 0) / b_games if b_games > 0 else 0.5

        if abs(a_wr - b_wr) > 0.1:
            if a_wr > b_wr:
                key_differences.append(f"{team_a_profile.team_name} has higher win rate ({a_wr:.0%} vs {b_wr:.0%})")
            else:
                key_differences.append(f"{team_b_profile.team_name} has higher win rate ({b_wr:.0%} vs {a_wr:.0%})")

        # Compare playstyles
        if team_a_profile.playstyle != team_b_profile.playstyle:
            key_differences.append(
                f"Different playstyles: {team_a_profile.team_name} ({team_a_profile.playstyle}) vs "
                f"{team_b_profile.team_name} ({team_b_profile.playstyle})"
            )

        # Strength/weakness matchups
        for a_strength in team_a_profile.strengths[:2]:
            for b_weakness in team_b_profile.weaknesses[:2]:
                if any(word in a_strength.lower() for word in b_weakness.lower().split()):
                    key_differences.append(f"{team_a_profile.team_name}'s {a_strength} exploits {team_b_profile.team_name}'s {b_weakness}")

        # Determine advantage
        advantage = None
        if a_wr > b_wr + 0.15:
            advantage = team_a_profile.team_name
        elif b_wr > a_wr + 0.15:
            advantage = team_b_profile.team_name

        # Generate summary
        summary = (
            f"Comparison of {team_a_profile.team_name} ({team_a_profile.playstyle}) "
            f"vs {team_b_profile.team_name} ({team_b_profile.playstyle}). "
        )
        if advantage:
            summary += f"{advantage} appears to have the edge based on recent performance. "
        else:
            summary += "This appears to be an evenly matched contest. "
        if key_differences:
            summary += f"Key difference: {key_differences[0]}."

        # Matchup prediction
        if advantage:
            prediction = f"{advantage} favored to win"
        else:
            prediction = "Too close to call - expect a competitive match"

        return TeamCompareResponse(
            team_a=team_a_profile,
            team_b=team_b_profile,
            comparison_summary=summary,
            advantage=advantage,
            key_differences=key_differences,
            matchup_prediction=prediction,
            generated_at=datetime.utcnow(),
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/maps/stats/{team_id}", response_model=MapStatsResponse)
async def get_map_stats(
    team_id: str,
    limit: int = 10,
) -> MapStatsResponse:
    """Get detailed map statistics for a VALORANT team.

    Returns per-map attack/defense win rates.
    """
    try:
        queries = ValorantMatchQueries(grid_client)

        # Fetch matches
        match_result = await queries.get_matches_by_team(team_id, limit=limit)
        edges = match_result.get("allSeries", {}).get("edges", [])

        # Get team info
        team_queries = ValorantTeamQueries(grid_client)
        team_info = await team_queries.get_team_info(team_id)
        team_name = team_info.get("team", {}).get("name", f"Team {team_id}")

        # Aggregate map stats
        map_data: dict[str, dict] = {}

        for edge in edges:
            node = edge.get("node", {})
            series_id = node.get("id")
            if not series_id:
                continue

            try:
                state = await queries.get_series_state(series_id)
                series_state = state.get("seriesState", {})
                teams = series_state.get("teams", [])
                games = series_state.get("games", [])

                # Find our team index
                our_idx = None
                for idx, t in enumerate(teams):
                    if str(t.get("id")) == str(team_id):
                        our_idx = idx
                        break

                if our_idx is None:
                    continue

                for game in games:
                    if not game.get("finished"):
                        continue

                    map_name = game.get("map", {}).get("name", "Unknown")
                    game_teams = game.get("teams", [])

                    if our_idx >= len(game_teams):
                        continue

                    our_team = game_teams[our_idx]
                    opp_team = game_teams[1 - our_idx] if len(game_teams) > 1 else {}

                    our_score = our_team.get("score", 0)
                    opp_score = opp_team.get("score", 0)
                    won = our_score > opp_score

                    if map_name not in map_data:
                        map_data[map_name] = {
                            "games_played": 0,
                            "wins": 0,
                            "losses": 0,
                            "attack_won": 0,
                            "attack_total": 0,
                            "defense_won": 0,
                            "defense_total": 0,
                            "total_rounds": 0,
                        }

                    data = map_data[map_name]
                    data["games_played"] += 1
                    if won:
                        data["wins"] += 1
                    else:
                        data["losses"] += 1

                    # Approximate attack/defense (standard Valorant half is 12 rounds)
                    total_rounds = our_score + opp_score
                    data["total_rounds"] += total_rounds

                    # Estimate based on score distribution
                    half_rounds = min(12, total_rounds // 2)
                    data["attack_total"] += half_rounds
                    data["defense_total"] += half_rounds
                    data["attack_won"] += our_score // 2
                    data["defense_won"] += (our_score + 1) // 2

            except Exception:
                continue

        # Build response
        maps = []
        for map_name, data in map_data.items():
            games = data["games_played"]
            maps.append(DetailedMapStats(
                map_name=map_name,
                games_played=games,
                wins=data["wins"],
                losses=data["losses"],
                win_rate=round(data["wins"] / games, 2) if games > 0 else 0,
                attack_rounds_won=data["attack_won"],
                attack_rounds_total=data["attack_total"],
                attack_win_rate=round(data["attack_won"] / max(data["attack_total"], 1), 2),
                defense_rounds_won=data["defense_won"],
                defense_rounds_total=data["defense_total"],
                defense_win_rate=round(data["defense_won"] / max(data["defense_total"], 1), 2),
                avg_rounds_per_game=round(data["total_rounds"] / games, 1) if games > 0 else 0,
            ))

        # Sort by games played
        maps.sort(key=lambda m: m.games_played, reverse=True)

        # Find best/worst
        best_map = None
        worst_map = None
        if maps:
            best = max(maps, key=lambda m: m.win_rate)
            worst = min(maps, key=lambda m: m.win_rate)
            if best.win_rate > 0:
                best_map = best.map_name
            if worst.win_rate < 1:
                worst_map = worst.map_name

        return MapStatsResponse(
            team_id=team_id,
            team_name=team_name,
            maps=maps,
            best_map=best_map,
            worst_map=worst_map,
            generated_at=datetime.utcnow(),
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/threats/{team_id}", response_model=ThreatRankingResponse)
async def get_threat_ranking(
    team_id: str,
    game: GameType,
    limit: int = 10,
) -> ThreatRankingResponse:
    """Get ranked list of players by threat level.

    Analyzes player performance to determine threat scores.
    """
    try:
        # Get player profiles using player_profiler
        if game == GameType.LOL:
            queries = LoLMatchQueries(grid_client)
        else:
            queries = ValorantMatchQueries(grid_client)

        # Fetch match IDs
        match_result = await queries.get_matches_by_team(team_id, limit=limit)
        edges = match_result.get("allSeries", {}).get("edges", [])
        match_ids = [e.get("node", {}).get("id") for e in edges if e.get("node", {}).get("id")]

        # Get profiles
        profiles = await player_profiler.profile_team_players(
            team_id=team_id,
            match_ids=match_ids,
            game=game,
        )

        # Get team name
        if game == GameType.LOL:
            team_queries = LoLTeamQueries(grid_client)
        else:
            team_queries = ValorantTeamQueries(grid_client)
        team_info = await team_queries.get_team_info(team_id)
        team_name = team_info.get("team", {}).get("name", f"Team {team_id}")

        # Build threat list
        players = []
        for profile in profiles:
            # Calculate threat score
            threat_score = 0.5

            # KDA contribution
            avg_stats = profile.average_stats
            kda = avg_stats.get("avg_kda", 0)
            if kda > 3:
                threat_score += 0.3
            elif kda > 2:
                threat_score += 0.2
            elif kda > 1.5:
                threat_score += 0.1

            # Win rate contribution
            primary_picks = profile.primary_picks
            if primary_picks:
                best_wr = max(p.win_rate for p in primary_picks)
                if best_wr > 0.6:
                    threat_score += 0.15
                elif best_wr > 0.5:
                    threat_score += 0.05

            # Cap at 1.0
            threat_score = min(1.0, threat_score)

            # Determine threat level
            if threat_score >= 0.75:
                threat_level = "high"
            elif threat_score >= 0.5:
                threat_level = "medium"
            else:
                threat_level = "low"

            # Get agent names
            agent_names = [p.name for p in profile.primary_picks[:3]]

            players.append(PlayerThreat(
                player_id=profile.player_id,
                player_name=profile.player_name,
                role=profile.role,
                threat_level=threat_level,
                threat_score=round(threat_score, 2),
                primary_agents=agent_names,
                avg_kda=round(kda, 2),
                games_analyzed=avg_stats.get("games", 0),
                key_strengths=profile.strengths[:2],
                exploitable_weaknesses=profile.weaknesses[:2],
                notes=profile.notes[:2],
            ))

        # Sort by threat score
        players.sort(key=lambda p: p.threat_score, reverse=True)

        # Top threat
        top_threat = players[0].player_name if players else None

        # Summary
        high_threats = [p for p in players if p.threat_level == "high"]
        summary = f"Analysis of {len(players)} players. "
        if high_threats:
            summary += f"High threat players: {', '.join(p.player_name for p in high_threats)}. "
        summary += "Focus defensive preparation on these players."

        return ThreatRankingResponse(
            team_id=team_id,
            team_name=team_name,
            players=players,
            top_threat=top_threat,
            summary=summary,
            generated_at=datetime.utcnow(),
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
