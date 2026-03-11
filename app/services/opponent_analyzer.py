"""Opponent analyzer service for team-wide pattern analysis."""

from typing import Any, Optional
from statistics import mean


from shared.grid_client import GridClient
from shared.grid_client.lol import LoLMatchQueries, LoLTeamQueries
from shared.grid_client.valorant import ValorantMatchQueries, ValorantTeamQueries

from app.models.schemas import (
    GameType,
    TeamProfile,
    ObjectiveAnalysis,
    MapStats,
)


class OpponentAnalyzer:
    """Analyzes opponent team patterns and tendencies."""

    def __init__(self, grid_client: Optional[GridClient] = None):
        self.grid_client = grid_client or GridClient()

    async def analyze_team(
        self,
        team_id: str,
        num_matches: int,
        game: GameType,
    ) -> TeamProfile:
        """Analyze a team's patterns across recent matches.

        Args:
            team_id: Team ID
            num_matches: Number of recent matches to analyze
            game: Game type (lol or valorant)

        Returns:
            TeamProfile with comprehensive analysis
        """
        # Fetch team info
        team_info = await self._fetch_team_info(team_id, game)

        # Fetch matches and compute stats from them
        matches = await self._fetch_recent_matches(team_id, num_matches, game)

        # Compute team stats from match data
        team_stats = self._compute_team_stats(matches, team_id, game)

        # Build profile based on game type
        if game == GameType.LOL:
            return await self._build_lol_profile(team_id, team_info, team_stats, matches)
        else:
            return await self._build_valorant_profile(team_id, team_info, team_stats, matches)

    async def _fetch_team_info(
        self,
        team_id: str,
        game: GameType,
    ) -> dict[str, Any]:
        """Fetch basic team information."""
        if game == GameType.LOL:
            queries = LoLTeamQueries(self.grid_client)
        else:
            queries = ValorantTeamQueries(self.grid_client)

        result = await queries.get_team_info(team_id)
        return result.get("team", {})

    async def _fetch_recent_matches(
        self,
        team_id: str,
        num_matches: int,
        game: GameType,
    ) -> list[dict[str, Any]]:
        """Fetch recent match data from Series State API."""
        if game == GameType.LOL:
            queries = LoLMatchQueries(self.grid_client)
        else:
            queries = ValorantMatchQueries(self.grid_client)

        # Get series list
        match_result = await queries.get_matches_by_team(team_id, limit=num_matches)

        # Extract matches from the result (API returns allSeries.edges)
        matches = []
        edges = match_result.get("allSeries", {}).get("edges", [])

        for edge in edges[:num_matches]:
            node = edge.get("node", {})
            if node:
                match_id = node.get("id")
                if match_id:
                    try:
                        # Fetch full series state
                        match_details = await queries.get_series_state(match_id)
                        state = match_details.get("seriesState", {})
                        if state:
                            # Add team_id context for later analysis
                            state["_team_id"] = team_id
                            state["_series_id"] = match_id
                            matches.append(state)
                    except Exception:
                        continue

        return matches

    def _compute_team_stats(
        self,
        matches: list[dict[str, Any]],
        team_id: str,
        game: GameType,
    ) -> dict[str, Any]:
        """Compute team statistics from match data."""
        stats = {
            "wins": 0,
            "losses": 0,
            "gamesPlayed": 0,
            "totalKills": 0,
            "totalDeaths": 0,
            "totalAssists": 0,
            "firstBloodRate": 0.0,
            "averageGameDuration": 0,
            # Valorant specific
            "attackRoundWins": 0,
            "attackRoundTotal": 0,
            "defenseRoundWins": 0,
            "defenseRoundTotal": 0,
            "pistolRoundWins": 0,
            "pistolRoundTotal": 0,
            # LoL specific
            "firstDragonRate": 0.0,
            "firstTowerRate": 0.0,
            "firstHeraldRate": 0.0,
            "firstBaronRate": 0.0,
            # Map stats for Valorant
            "mapStats": {},
        }

        first_bloods = 0
        total_games = 0

        for match in matches:
            teams = match.get("teams", [])
            games = match.get("games", [])

            # Find our team index
            our_team_idx = None
            for idx, t in enumerate(teams):
                if str(t.get("id")) == str(team_id):
                    our_team_idx = idx
                    break

            if our_team_idx is None:
                continue

            # Analyze each game in the series
            for game_data in games:
                if not game_data.get("finished"):
                    continue

                total_games += 1
                game_teams = game_data.get("teams", [])

                if our_team_idx >= len(game_teams):
                    continue

                our_team = game_teams[our_team_idx]
                enemy_idx = 1 if our_team_idx == 0 else 0
                enemy_team = game_teams[enemy_idx] if enemy_idx < len(game_teams) else {}

                our_score = our_team.get("score", 0)
                enemy_score = enemy_team.get("score", 0)

                # Win/loss
                if our_score > enemy_score:
                    stats["wins"] += 1
                else:
                    stats["losses"] += 1

                # Player stats aggregation
                for player in our_team.get("players", []):
                    stats["totalKills"] += player.get("kills", 0)
                    stats["totalDeaths"] += player.get("deaths", 0)
                    stats["totalAssists"] += player.get("killAssistsGiven", 0) or player.get("assists", 0)

                # Map stats for Valorant
                if game == GameType.VALORANT:
                    map_name = game_data.get("map", {}).get("name", "Unknown")
                    if map_name not in stats["mapStats"]:
                        stats["mapStats"][map_name] = {"wins": 0, "losses": 0, "played": 0}
                    stats["mapStats"][map_name]["played"] += 1
                    if our_score > enemy_score:
                        stats["mapStats"][map_name]["wins"] += 1
                    else:
                        stats["mapStats"][map_name]["losses"] += 1

                    # Round-level stats (approximate from score)
                    # In Valorant, first half is usually one side
                    total_rounds = our_score + enemy_score
                    if total_rounds > 0:
                        # Approximate attack/defense (assume equal distribution)
                        half_rounds = total_rounds // 2
                        stats["attackRoundTotal"] += half_rounds
                        stats["defenseRoundTotal"] += half_rounds
                        stats["attackRoundWins"] += our_score // 2
                        stats["defenseRoundWins"] += (our_score + 1) // 2

                        # Pistol rounds (round 1 and round 13 approximately)
                        stats["pistolRoundTotal"] += 2
                        if our_score >= 1:
                            stats["pistolRoundWins"] += 1
                        if our_score >= 7:  # Won at least one on each half
                            stats["pistolRoundWins"] += 1

        stats["gamesPlayed"] = total_games

        # Calculate rates
        if total_games > 0:
            stats["firstBloodRate"] = first_bloods / total_games
            stats["winRate"] = stats["wins"] / total_games
            stats["averageKills"] = stats["totalKills"] / total_games
            stats["averageDeaths"] = stats["totalDeaths"] / total_games
            stats["averageAssists"] = stats["totalAssists"] / total_games

        if stats["attackRoundTotal"] > 0:
            stats["attackRoundWinRate"] = stats["attackRoundWins"] / stats["attackRoundTotal"]
        else:
            stats["attackRoundWinRate"] = 0.5

        if stats["defenseRoundTotal"] > 0:
            stats["defenseRoundWinRate"] = stats["defenseRoundWins"] / stats["defenseRoundTotal"]
        else:
            stats["defenseRoundWinRate"] = 0.5

        if stats["pistolRoundTotal"] > 0:
            stats["pistolRoundWinRate"] = stats["pistolRoundWins"] / stats["pistolRoundTotal"]
        else:
            stats["pistolRoundWinRate"] = 0.5

        return stats

    async def _build_lol_profile(
        self,
        team_id: str,
        team_info: dict[str, Any],
        team_stats: dict[str, Any],
        matches: list[dict[str, Any]],
    ) -> TeamProfile:
        """Build LoL-specific team profile."""
        team_name = team_info.get("name", "Unknown Team")

        wins = team_stats.get("wins", 0)
        losses = team_stats.get("losses", 0)
        games_played = team_stats.get("gamesPlayed", 0)

        # Determine playstyle from actual data
        avg_kills = team_stats.get("averageKills", 0)
        avg_deaths = team_stats.get("averageDeaths", 0)

        if avg_kills > avg_deaths * 1.2:
            playstyle = "Aggressive"
        elif avg_deaths > avg_kills * 1.2:
            playstyle = "Passive/Scaling"
        else:
            playstyle = "Balanced"

        # Determine identity
        win_rate = wins / games_played if games_played > 0 else 0.5
        if win_rate > 0.6:
            identity = f"Strong team with {win_rate:.0%} win rate"
        elif win_rate < 0.4:
            identity = f"Struggling team with {win_rate:.0%} win rate"
        else:
            identity = f"Competitive team with {win_rate:.0%} win rate"

        # Build early/mid/late patterns from match data
        early_patterns = []
        mid_patterns = []
        late_patterns = []

        if avg_kills > 15:
            early_patterns.append("High kill activity in laning phase")
        if games_played > 0:
            kd_ratio = avg_kills / max(avg_deaths, 1)
            if kd_ratio > 1.3:
                mid_patterns.append("Strong mid-game team fighting")
            elif kd_ratio < 0.8:
                mid_patterns.append("Struggles in mid-game skirmishes")

        # Determine strengths and weaknesses
        strengths = []
        weaknesses = []

        if win_rate > 0.55:
            strengths.append("Consistent winner")
        if avg_kills > 20:
            strengths.append("High kill threat")
        if avg_deaths < 10:
            strengths.append("Clean gameplay, few deaths")

        if win_rate < 0.45:
            weaknesses.append("Inconsistent results")
        if avg_deaths > 15:
            weaknesses.append("Prone to giving up kills")
        if games_played < 3:
            weaknesses.append("Limited recent match data")

        return TeamProfile(
            team_id=team_id,
            team_name=team_name,
            overall_record={"wins": wins, "losses": losses, "games_played": games_played},
            playstyle=playstyle,
            identity=identity,
            objectives=[],
            early_game_patterns=early_patterns,
            mid_game_patterns=mid_patterns,
            late_game_patterns=late_patterns,
            strengths=strengths if strengths else ["No clear strengths identified"],
            weaknesses=weaknesses if weaknesses else ["No clear weaknesses identified"],
        )

    async def _build_valorant_profile(
        self,
        team_id: str,
        team_info: dict[str, Any],
        team_stats: dict[str, Any],
        matches: list[dict[str, Any]],
    ) -> TeamProfile:
        """Build VALORANT-specific team profile."""
        team_name = team_info.get("name", "Unknown Team")

        wins = team_stats.get("wins", 0)
        losses = team_stats.get("losses", 0)
        games_played = team_stats.get("gamesPlayed", 0)
        win_rate = wins / games_played if games_played > 0 else 0.5

        # Map preferences from computed stats
        map_stats_data = team_stats.get("mapStats", {})
        map_preferences = {}
        for map_name, data in map_stats_data.items():
            played = data.get("played", 0)
            map_wins = data.get("wins", 0)
            if played > 0:
                map_preferences[map_name] = MapStats(
                    played=played,
                    win_rate=round(map_wins / played, 2),
                )

        # Determine playstyle from round win rates
        attack_wr = team_stats.get("attackRoundWinRate", 0.5)
        defense_wr = team_stats.get("defenseRoundWinRate", 0.5)
        pistol_wr = team_stats.get("pistolRoundWinRate", 0.5)

        if attack_wr > defense_wr + 0.1:
            playstyle = "Attack-sided"
        elif defense_wr > attack_wr + 0.1:
            playstyle = "Defense-sided"
        else:
            playstyle = "Balanced"

        # Identity based on actual performance
        avg_kills = team_stats.get("averageKills", 0)
        avg_deaths = team_stats.get("averageDeaths", 0)

        if win_rate > 0.6:
            identity = f"{playstyle} team with strong {win_rate:.0%} win rate"
        elif win_rate < 0.4:
            identity = f"{playstyle} team struggling with {win_rate:.0%} win rate"
        else:
            identity = f"{playstyle} team with competitive {win_rate:.0%} win rate"

        # Attack/defense tendencies
        attack_tendencies = []
        defense_tendencies = []

        if attack_wr > 0.55:
            attack_tendencies.append("Strong attack executes")
        elif attack_wr < 0.45:
            attack_tendencies.append("Struggles to convert attack rounds")
        else:
            attack_tendencies.append("Average attack round performance")

        if defense_wr > 0.55:
            defense_tendencies.append("Strong defensive setups")
        elif defense_wr < 0.45:
            defense_tendencies.append("Vulnerable on defense")
        else:
            defense_tendencies.append("Average defensive performance")

        # Economy patterns
        economy_patterns = []
        if pistol_wr > 0.55:
            economy_patterns.append("Strong pistol round conversion")
        elif pistol_wr < 0.45:
            economy_patterns.append("Weak pistol rounds - economy disadvantages likely")

        # Strengths and weaknesses
        strengths = []
        weaknesses = []

        if pistol_wr > 0.55:
            strengths.append("Strong pistol rounds")
        elif pistol_wr < 0.45:
            weaknesses.append("Inconsistent pistol rounds")

        if attack_wr > 0.55:
            strengths.append("Effective attack executes")
        elif attack_wr < 0.45:
            weaknesses.append("Struggles on attack")

        if defense_wr > 0.55:
            strengths.append("Solid defensive play")
        elif defense_wr < 0.45:
            weaknesses.append("Vulnerable on defense")

        if win_rate > 0.55:
            strengths.append(f"Strong overall record ({wins}W-{losses}L)")
        elif win_rate < 0.45:
            weaknesses.append(f"Poor recent form ({wins}W-{losses}L)")

        if avg_kills > avg_deaths * 1.2:
            strengths.append("Positive K/D ratio")
        elif avg_deaths > avg_kills * 1.2:
            weaknesses.append("Negative K/D ratio")

        # Best/worst maps
        if map_preferences:
            best_map = max(map_preferences.items(), key=lambda x: x[1].win_rate)
            worst_map = min(map_preferences.items(), key=lambda x: x[1].win_rate)
            if best_map[1].win_rate > 0.6:
                strengths.append(f"Strong on {best_map[0]} ({best_map[1].win_rate:.0%} WR)")
            if worst_map[1].win_rate < 0.4:
                weaknesses.append(f"Weak on {worst_map[0]} ({worst_map[1].win_rate:.0%} WR)")

        return TeamProfile(
            team_id=team_id,
            team_name=team_name,
            overall_record={"wins": wins, "losses": losses, "games_played": games_played},
            playstyle=playstyle,
            identity=identity,
            map_preferences=map_preferences,
            attack_tendencies=attack_tendencies,
            defense_tendencies=defense_tendencies,
            economy_patterns=economy_patterns,
            strengths=strengths if strengths else ["No clear strengths - limited data"],
            weaknesses=weaknesses if weaknesses else ["No clear weaknesses - limited data"],
        )
