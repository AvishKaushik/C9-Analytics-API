"""Pattern detection service for identifying recurring patterns in match data."""

import logging
from typing import Any, Optional
from statistics import mean, stdev


from shared.grid_client import GridClient
from shared.grid_client.client import GridClientError
from shared.grid_client.lol import LoLMatchQueries, LoLPlayerQueries
from shared.grid_client.valorant import ValorantMatchQueries, ValorantPlayerQueries
from shared.utils.analytics import detect_outliers, calculate_win_correlation
from shared.utils.llm import generate_insight

from app.models.schemas import GameType, Pattern, Insight

logger = logging.getLogger(__name__)


class PatternDetector:
    """Detects recurring patterns in player and team performance."""

    def __init__(self, grid_client: Optional[GridClient] = None):
        # Use provided client, or create one that respects USE_MOCK_DATA env var
        self.grid_client = grid_client or GridClient()

    async def analyze_player(
        self,
        player_id: str,
        match_ids: list[str],
        game: GameType,
        focus_areas: Optional[list[str]] = None,
    ) -> tuple[list[Pattern], list[Insight]]:
        """Analyze player data to find patterns and generate insights.

        Args:
            player_id: Player ID
            match_ids: List of match IDs to analyze
            game: Game type (lol or valorant)
            focus_areas: Optional areas to focus analysis on

        Returns:
            Tuple of (patterns, insights)
        """
        # Fetch performance data
        performances = await self._fetch_player_performances(player_id, match_ids, game)

        if not performances:
            return [], []

        # Detect patterns
        patterns = await self._detect_player_patterns(performances, game)

        # Generate insights using LLM
        insights = await self._generate_player_insights(
            player_id, performances, patterns, game, focus_areas
        )

        return patterns, insights

    async def analyze_player_detailed(
        self,
        player_id: str,
        match_ids: list[str],
        game: GameType,
        focus_areas: Optional[list[str]] = None,
        limit: int = 10,
    ) -> tuple[list[Pattern], list[Insight], list[dict[str, Any]]]:
        """Analyze player data with detailed performance data returned.

        Args:
            player_id: Player ID
            match_ids: List of match IDs to analyze
            game: Game type (lol or valorant)
            focus_areas: Optional areas to focus analysis on
            limit: Maximum number of series to analyze

        Returns:
            Tuple of (patterns, insights, performances)
        """
        # Fetch performance data
        performances = await self._fetch_player_performances_with_limit(
            player_id, match_ids, game, limit
        )

        if not performances:
            return [], [], []

        # Detect patterns
        patterns = await self._detect_player_patterns(performances, game)

        # Generate insights
        insights = await self._generate_player_insights(
            player_id, performances, patterns, game, focus_areas
        )

        return patterns, insights, performances

    async def get_player_performances(
        self,
        player_id: str,
        game: GameType,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Get raw player performances.

        Args:
            player_id: Player ID
            game: Game type (lol or valorant)
            limit: Maximum number of series to analyze

        Returns:
            List of performance data
        """
        return await self._fetch_player_performances_with_limit(
            player_id, [], game, limit
        )

    async def analyze_team(
        self,
        team_id: str,
        match_ids: list[str],
        game: GameType,
        focus_areas: Optional[list[str]] = None,
    ) -> tuple[list[Pattern], list[Insight], dict[str, list[str]]]:
        """Analyze team data to find patterns and generate insights.

        Args:
            team_id: Team ID
            match_ids: List of match IDs to analyze
            game: Game type (lol or valorant)
            focus_areas: Optional areas to focus analysis on

        Returns:
            Tuple of (patterns, insights, player_highlights)
        """
        # Fetch team match data
        matches = await self._fetch_team_matches(team_id, match_ids, game)

        if not matches:
            return [], [], {}

        # Detect team-level patterns
        patterns = await self._detect_team_patterns(matches, game)

        # Extract player highlights
        player_highlights = self._extract_player_highlights(matches)

        # Generate insights
        insights = await self._generate_team_insights(
            team_id, matches, patterns, game, focus_areas
        )

        return patterns, insights, player_highlights

    async def analyze_team_detailed(
        self,
        team_id: str,
        match_ids: list[str],
        game: GameType,
        focus_areas: Optional[list[str]] = None,
        limit: int = 10,
    ) -> dict[str, Any]:
        """Analyze team data with detailed results.

        Args:
            team_id: Team ID
            match_ids: List of match IDs to analyze
            game: Game type (lol or valorant)
            focus_areas: Optional areas to focus analysis on
            limit: Maximum number of series to analyze

        Returns:
            Dict with patterns, insights, player_highlights, matches, roster
        """
        # Fetch team match data
        matches = await self._fetch_team_matches_with_limit(team_id, match_ids, game, limit)

        if not matches:
            return {
                "patterns": [],
                "insights": [],
                "player_highlights": {},
                "matches": [],
                "roster": [],
            }

        # Detect team-level patterns
        patterns = await self._detect_team_patterns(matches, game)

        # Extract player highlights
        player_highlights = self._extract_player_highlights(matches)

        # Generate insights
        insights = await self._generate_team_insights(
            team_id, matches, patterns, game, focus_areas
        )

        # Build roster from match data
        roster = self._build_roster_from_matches(matches, team_id)

        return {
            "patterns": patterns,
            "insights": insights,
            "player_highlights": player_highlights,
            "matches": matches,
            "roster": roster,
        }

    async def get_team_roster(
        self,
        team_id: str,
        game: GameType,
        limit: int = 10,
    ) -> dict[str, Any]:
        """Get team roster with player stats.

        Args:
            team_id: Team ID
            game: Game type (lol or valorant)
            limit: Maximum number of series to analyze for stats

        Returns:
            Dict with players list and team_stats
        """
        # Fetch team matches
        matches = await self._fetch_team_matches_with_limit(team_id, [], game, limit)

        if not matches:
            return {
                "team_name": team_id,
                "players": [],
                "team_stats": {
                    "games_played": 0,
                    "wins": 0,
                    "losses": 0,
                    "win_rate": 0,
                    "total_kills": 0,
                    "total_deaths": 0,
                    "avg_kills_per_game": 0,
                    "avg_deaths_per_game": 0,
                    "team_kd": 0,
                },
            }

        # Build roster from match data
        roster = self._build_roster_from_matches(matches, team_id)

        # Calculate team stats
        team_stats = self._calculate_team_stats_from_matches(matches, team_id)

        # Get team name
        team_name = team_id
        if matches and matches[0].get("teams"):
            for t in matches[0].get("teams", []):
                if str(t.get("id")) == str(team_id):
                    team_name = t.get("name", team_id)
                    break

        return {
            "team_name": team_name,
            "players": roster,
            "team_stats": team_stats,
        }

    async def _fetch_player_performances(
        self,
        player_id: str,
        match_ids: list[str],
        game: GameType,
    ) -> list[dict[str, Any]]:
        """Fetch player performance data from GRID API."""
        try:
            if game == GameType.LOL:
                queries = LoLPlayerQueries(self.grid_client)
                result = await queries.get_player_performance(player_id, match_ids)
            else:
                queries = ValorantPlayerQueries(self.grid_client)
                result = await queries.get_player_performance(player_id, match_ids)

            return result.get("player", {}).get("performances", [])
        except GridClientError as e:
            logger.warning(f"GRID API error, using empty data: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error fetching player performances: {e}")
            return []

    async def _fetch_player_performances_with_limit(
        self,
        player_id: str,
        match_ids: list[str],
        game: GameType,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Fetch player performance data with a series limit."""
        try:
            if game == GameType.LOL:
                queries = LoLPlayerQueries(self.grid_client)
            else:
                queries = ValorantPlayerQueries(self.grid_client)

            # Use the get_player_performance method which already handles fetching
            # recent series if no match_ids are provided
            result = await queries.get_player_performance(
                player_id,
                match_ids[:limit] if match_ids else None,
                limit=limit
            )
            performances = result.get("player", {}).get("performances", [])

            return performances

        except GridClientError as e:
            logger.warning(f"GRID API error, using empty data: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error fetching player performances: {e}")
            return []

    async def _fetch_team_matches(
        self,
        team_id: str,
        match_ids: list[str],
        game: GameType,
    ) -> list[dict[str, Any]]:
        """Fetch team match data from GRID API."""
        matches = []
        try:
            if game == GameType.LOL:
                queries = LoLMatchQueries(self.grid_client)
            else:
                queries = ValorantMatchQueries(self.grid_client)

            # If no match_ids provided, fetch recent series for the team
            if not match_ids:
                series_result = await queries.get_matches_by_team(team_id, limit=10)
                edges = series_result.get("allSeries", {}).get("edges", [])
                match_ids = [edge["node"]["id"] for edge in edges]

            for match_id in match_ids:
                try:
                    result = await queries.get_series_state(match_id)
                    state = result.get("seriesState", {})
                    if state:
                        # Extract games from series state
                        for game_data in state.get("games", []):
                            if game_data.get("finished"):
                                matches.append({
                                    "seriesId": match_id,
                                    "game": game_data,
                                    "teams": state.get("teams", []),
                                })
                except GridClientError as e:
                    logger.warning(f"Error fetching match {match_id}: {e}")
                    continue

        except Exception as e:
            logger.error(f"Unexpected error fetching team matches: {e}")

        return matches

    async def _fetch_team_matches_with_limit(
        self,
        team_id: str,
        match_ids: list[str],
        game: GameType,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Fetch team match data with a series limit."""
        matches = []
        try:
            if game == GameType.LOL:
                queries = LoLMatchQueries(self.grid_client)
            else:
                queries = ValorantMatchQueries(self.grid_client)

            # If no match_ids provided, fetch recent series for the team
            series_dates = {}  # Map series_id -> date
            if not match_ids:
                print(f"[PatternDetector] Fetching series for team {team_id}, limit {limit}")
                series_result = await queries.get_matches_by_team(team_id, limit=limit)
                edges = series_result.get("allSeries", {}).get("edges", [])
                match_ids = [edge["node"]["id"] for edge in edges[:limit]]
                # Store dates from series list
                for edge in edges[:limit]:
                    node = edge.get("node", {})
                    series_dates[node.get("id")] = node.get("startTimeScheduled")
                print(f"[PatternDetector] Got {len(match_ids)} series IDs")

            for match_id in match_ids[:limit]:
                try:
                    result = await queries.get_series_state(match_id)
                    state = result.get("seriesState", {})
                    if state:
                        # Extract games from series state
                        for game_data in state.get("games", []):
                            if game_data.get("finished"):
                                matches.append({
                                    "seriesId": match_id,
                                    "game": game_data,
                                    "teams": state.get("teams", []),
                                    "date": series_dates.get(match_id),
                                })
                except GridClientError as e:
                    logger.warning(f"Error fetching match {match_id}: {e}")
                    continue

            print(f"[PatternDetector] Returning {len(matches)} matches")

        except Exception as e:
            print(f"[PatternDetector] ERROR: {e}")
            logger.error(f"Unexpected error fetching team matches: {e}")

        return matches

    def _build_roster_from_matches(
        self,
        matches: list[dict[str, Any]],
        team_id: str,
    ) -> list[dict[str, Any]]:
        """Build roster data from match data."""
        player_data: dict[str, dict] = {}

        for match in matches:
            game = match.get("game", {})
            teams_list = match.get("teams", [])

            # Find which team index corresponds to our team
            our_team_idx = None
            for idx, t in enumerate(teams_list):
                if str(t.get("id")) == str(team_id):
                    our_team_idx = idx
                    break

            # Get our team's players from the game data
            game_teams = game.get("teams", [])
            if our_team_idx is not None and our_team_idx < len(game_teams):
                our_game_team = game_teams[our_team_idx]
                our_score = our_game_team.get("score", 0)

                # Determine if this was a win
                enemy_idx = 1 if our_team_idx == 0 else 0
                enemy_score = 0
                if enemy_idx < len(game_teams):
                    enemy_score = game_teams[enemy_idx].get("score", 0)
                is_win = our_score > enemy_score

                for player in our_game_team.get("players", []):
                    player_id = str(player.get("id", "unknown"))
                    # Series State API uses "name", Central Data API uses "nickname"
                    player_name = player.get("name") or player.get("nickname") or f"Player {player_id}"

                    if player_id not in player_data:
                        player_data[player_id] = {
                            "player_id": player_id,
                            "player_name": player_name,
                            "games_played": 0,
                            "wins": 0,
                            "kills": 0,
                            "deaths": 0,
                            "assists": 0,
                            "agents": {},
                            "recent_wins": [],
                        }

                    data = player_data[player_id]
                    data["games_played"] += 1
                    if is_win:
                        data["wins"] += 1
                    data["kills"] += player.get("kills", 0)
                    data["deaths"] += player.get("deaths", 0)
                    data["assists"] += player.get("killAssistsGiven", 0) or player.get("assists", 0)

                    # Track recent wins for form calculation
                    if len(data["recent_wins"]) < 5:
                        data["recent_wins"].append(is_win)

                    # Track agent/champion usage
                    agent_name = player.get("character", {}).get("name", "Unknown")
                    data["agents"][agent_name] = data["agents"].get(agent_name, 0) + 1

        # Convert to final format
        roster = []
        for player_id, data in player_data.items():
            games = data["games_played"]
            deaths = data["deaths"] or 1
            avg_kda = (data["kills"] + data["assists"]) / deaths if games > 0 else 0
            win_rate = data["wins"] / games if games > 0 else 0

            # Get main agents sorted by usage
            main_agents = sorted(data["agents"].items(), key=lambda x: x[1], reverse=True)
            main_agents = [a[0] for a in main_agents[:3]]

            # Determine recent form
            recent = data["recent_wins"]
            recent_wins = sum(recent)
            if len(recent) >= 3:
                if recent_wins >= 4:
                    recent_form = "hot"
                elif recent_wins <= 1:
                    recent_form = "cold"
                else:
                    recent_form = "neutral"
            else:
                recent_form = "neutral"

            roster.append({
                "player_id": player_id,
                "player_name": data["player_name"],
                "games_played": games,
                "avg_kda": round(avg_kda, 2),
                "win_rate": round(win_rate, 3),
                "main_agents": main_agents,
                "recent_form": recent_form,
            })

        # Sort by games played
        roster.sort(key=lambda x: x["games_played"], reverse=True)
        return roster

    def _calculate_team_stats_from_matches(
        self,
        matches: list[dict[str, Any]],
        team_id: str,
    ) -> dict[str, Any]:
        """Calculate team statistics from matches."""
        games_played = 0
        wins = 0
        total_kills = 0
        total_deaths = 0

        for match in matches:
            game = match.get("game", {})
            teams_list = match.get("teams", [])

            # Find our team index
            our_team_idx = None
            for idx, t in enumerate(teams_list):
                if str(t.get("id")) == str(team_id):
                    our_team_idx = idx
                    break

            game_teams = game.get("teams", [])
            if our_team_idx is not None and our_team_idx < len(game_teams):
                games_played += 1
                our_game_team = game_teams[our_team_idx]
                our_score = our_game_team.get("score", 0)

                # Determine win
                enemy_idx = 1 if our_team_idx == 0 else 0
                enemy_score = 0
                if enemy_idx < len(game_teams):
                    enemy_score = game_teams[enemy_idx].get("score", 0)
                if our_score > enemy_score:
                    wins += 1

                # Aggregate player stats
                for player in our_game_team.get("players", []):
                    total_kills += player.get("kills", 0)
                    total_deaths += player.get("deaths", 0)

        losses = games_played - wins

        return {
            "games_played": games_played,
            "wins": wins,
            "losses": losses,
            "win_rate": round(wins / games_played, 3) if games_played > 0 else 0,
            "total_kills": total_kills,
            "total_deaths": total_deaths,
            "avg_kills_per_game": round(total_kills / games_played, 2) if games_played > 0 else 0,
            "avg_deaths_per_game": round(total_deaths / games_played, 2) if games_played > 0 else 0,
            "team_kd": round(total_kills / max(total_deaths, 1), 2),
        }

    async def _detect_player_patterns(
        self,
        performances: list[dict[str, Any]],
        game: GameType,
    ) -> list[Pattern]:
        """Detect patterns in player performance data."""
        patterns = []

        if game == GameType.LOL:
            patterns.extend(self._detect_lol_player_patterns(performances))
        else:
            patterns.extend(self._detect_valorant_player_patterns(performances))

        return patterns

    def _detect_lol_player_patterns(
        self,
        performances: list[dict[str, Any]],
    ) -> list[Pattern]:
        """Detect LoL-specific player patterns."""
        patterns = []

        if not performances:
            return patterns

        # Death pattern analysis
        deaths = [p.get("deaths", 0) for p in performances]
        if len(deaths) >= 2 and stdev(deaths) > 0:
            death_outliers = detect_outliers(deaths, threshold=1.5)

            if death_outliers:
                avg_deaths = mean(deaths)
                high_death_games = [
                    p for p in performances
                    if p.get("deaths", 0) > avg_deaths + stdev(deaths)
                ]
                if high_death_games:
                    patterns.append(Pattern(
                        pattern_type="high_death_games",
                        description=f"Player has unusually high deaths in {len(high_death_games)} games",
                        frequency=len(high_death_games) / len(performances),
                        impact="negative",
                        games_observed=len(high_death_games),
                        examples=high_death_games[:3],
                        recommendation="Review positioning and map awareness in these games",
                    ))

        # KDA pattern analysis
        kdas = []
        for p in performances:
            kills = p.get("kills", 0)
            deaths = p.get("deaths", 0) or 1
            assists = p.get("assists", 0)
            kdas.append((kills + assists) / deaths)

        if kdas:
            avg_kda = mean(kdas)
            if avg_kda < 2.0:
                patterns.append(Pattern(
                    pattern_type="low_kda",
                    description=f"Average KDA ({avg_kda:.2f}) is below professional standards",
                    frequency=sum(1 for k in kdas if k < 2.0) / len(kdas),
                    impact="negative",
                    games_observed=len([k for k in kdas if k < 2.0]),
                    recommendation="Focus on reducing deaths and participating in team fights",
                ))
            elif avg_kda > 4.0:
                patterns.append(Pattern(
                    pattern_type="high_kda",
                    description=f"Strong KDA performance ({avg_kda:.2f})",
                    frequency=sum(1 for k in kdas if k > 4.0) / len(kdas),
                    impact="positive",
                    games_observed=len([k for k in kdas if k > 4.0]),
                    recommendation="Maintain this level of play and look to carry harder",
                ))

        # Win rate analysis
        wins = [1 if p.get("win", False) else 0 for p in performances]
        if wins:
            win_rate = mean(wins)
            if win_rate < 0.4:
                patterns.append(Pattern(
                    pattern_type="low_win_rate",
                    description=f"Win rate ({win_rate*100:.1f}%) is concerning",
                    frequency=win_rate,
                    impact="negative",
                    games_observed=len(wins),
                    recommendation="Review game decisions and team coordination",
                ))
            elif win_rate > 0.6:
                patterns.append(Pattern(
                    pattern_type="high_win_rate",
                    description=f"Strong win rate ({win_rate*100:.1f}%)",
                    frequency=win_rate,
                    impact="positive",
                    games_observed=len(wins),
                    recommendation="Continue current strategies and maintain performance",
                ))

        # Champion diversity analysis
        champions = [p.get("champion", {}).get("name", "Unknown") for p in performances]
        unique_champions = set(champions)
        if len(performances) >= 5:
            diversity_ratio = len(unique_champions) / len(performances)
            if diversity_ratio < 0.3:
                patterns.append(Pattern(
                    pattern_type="narrow_champion_pool",
                    description=f"Limited champion pool ({len(unique_champions)} unique champions in {len(performances)} games)",
                    frequency=diversity_ratio,
                    impact="neutral",
                    games_observed=len(performances),
                    recommendation="Consider expanding champion pool for flexibility",
                ))

        # Kill participation (using kills + assists vs total team kills would be ideal but we don't have team totals)
        total_kills = sum(p.get("kills", 0) for p in performances)
        total_assists = sum(p.get("assists", 0) for p in performances)
        if total_kills > 0:
            assist_ratio = total_assists / (total_kills + total_assists) if (total_kills + total_assists) > 0 else 0
            if assist_ratio > 0.7:
                patterns.append(Pattern(
                    pattern_type="supportive_playstyle",
                    description=f"High assist ratio ({assist_ratio*100:.1f}%) indicates supportive playstyle",
                    frequency=assist_ratio,
                    impact="neutral",
                    games_observed=len(performances),
                    recommendation="Strong team player - continue enabling teammates",
                ))

        return patterns

    def _detect_valorant_player_patterns(
        self,
        performances: list[dict[str, Any]],
    ) -> list[Pattern]:
        """Detect VALORANT-specific player patterns."""
        patterns = []

        if not performances:
            return patterns

        # KDA pattern analysis
        kdas = []
        for p in performances:
            kills = p.get("kills", 0)
            deaths = p.get("deaths", 0) or 1
            assists = p.get("assists", 0)
            kdas.append((kills + assists) / deaths)

        if kdas:
            avg_kda = mean(kdas)
            if avg_kda < 1.5:
                patterns.append(Pattern(
                    pattern_type="low_kda",
                    description=f"Average KDA ({avg_kda:.2f}) is below professional standards",
                    frequency=sum(1 for k in kdas if k < 1.5) / len(kdas),
                    impact="negative",
                    games_observed=len([k for k in kdas if k < 1.5]),
                    recommendation="Focus on positioning and trade opportunities",
                ))
            elif avg_kda > 3.0:
                patterns.append(Pattern(
                    pattern_type="high_kda",
                    description=f"Strong KDA performance ({avg_kda:.2f})",
                    frequency=sum(1 for k in kdas if k > 3.0) / len(kdas),
                    impact="positive",
                    games_observed=len([k for k in kdas if k > 3.0]),
                    recommendation="Maintain this level of play",
                ))

        # Death pattern analysis
        deaths = [p.get("deaths", 0) for p in performances]
        if len(deaths) >= 2 and stdev(deaths) > 0:
            avg_deaths = mean(deaths)
            high_death_games = [
                p for p in performances
                if p.get("deaths", 0) > avg_deaths + stdev(deaths)
            ]
            if high_death_games:
                patterns.append(Pattern(
                    pattern_type="high_death_games",
                    description=f"Unusually high deaths in {len(high_death_games)} games",
                    frequency=len(high_death_games) / len(performances),
                    impact="negative",
                    games_observed=len(high_death_games),
                    examples=high_death_games[:3],
                    recommendation="Review positioning and timing in these games",
                ))

        # Win rate analysis
        wins = [1 if p.get("win", False) else 0 for p in performances]
        if wins:
            win_rate = mean(wins)
            if win_rate < 0.4:
                patterns.append(Pattern(
                    pattern_type="low_win_rate",
                    description=f"Win rate ({win_rate*100:.1f}%) is concerning",
                    frequency=win_rate,
                    impact="negative",
                    games_observed=len(wins),
                    recommendation="Review team coordination and individual decisions",
                ))
            elif win_rate > 0.6:
                patterns.append(Pattern(
                    pattern_type="high_win_rate",
                    description=f"Strong win rate ({win_rate*100:.1f}%)",
                    frequency=win_rate,
                    impact="positive",
                    games_observed=len(wins),
                    recommendation="Continue current strategies",
                ))

        # Agent diversity analysis
        agents = [p.get("agent", {}).get("name", "Unknown") for p in performances]
        unique_agents = set(agents)
        if len(performances) >= 5:
            diversity_ratio = len(unique_agents) / len(performances)
            if diversity_ratio < 0.3:
                patterns.append(Pattern(
                    pattern_type="narrow_agent_pool",
                    description=f"Limited agent pool ({len(unique_agents)} unique agents in {len(performances)} games)",
                    frequency=diversity_ratio,
                    impact="neutral",
                    games_observed=len(performances),
                    recommendation="Consider expanding agent pool for flexibility",
                ))

        # Frag hunting vs supportive playstyle
        total_kills = sum(p.get("kills", 0) for p in performances)
        total_assists = sum(p.get("assists", 0) for p in performances)
        if total_kills + total_assists > 0:
            kill_ratio = total_kills / (total_kills + total_assists)
            if kill_ratio > 0.7:
                patterns.append(Pattern(
                    pattern_type="aggressive_fragger",
                    description=f"High kill focus ({kill_ratio*100:.1f}% kills vs assists)",
                    frequency=kill_ratio,
                    impact="neutral",
                    games_observed=len(performances),
                    recommendation="Aggressive playstyle - ensure team coordination",
                ))
            elif kill_ratio < 0.4:
                patterns.append(Pattern(
                    pattern_type="supportive_playstyle",
                    description=f"High assist focus ({(1-kill_ratio)*100:.1f}% assists vs kills)",
                    frequency=1 - kill_ratio,
                    impact="neutral",
                    games_observed=len(performances),
                    recommendation="Strong team player - continue enabling teammates",
                ))

        return patterns

    async def _detect_team_patterns(
        self,
        matches: list[dict[str, Any]],
        game: GameType,
    ) -> list[Pattern]:
        """Detect patterns in team performance data."""
        patterns = []

        if game == GameType.LOL:
            patterns.extend(self._detect_lol_team_patterns(matches))
        else:
            patterns.extend(self._detect_valorant_team_patterns(matches))

        return patterns

    def _detect_lol_team_patterns(
        self,
        matches: list[dict[str, Any]],
    ) -> list[Pattern]:
        """Detect LoL-specific team patterns."""
        patterns = []

        if not matches:
            return patterns

        # Aggregate stats across all games
        total_games = len(matches)
        wins = 0
        total_kills = 0
        total_deaths = 0
        champion_picks: dict[str, int] = {}

        for match in matches:
            game = match.get("game", {})
            game_teams = game.get("teams", [])

            for team in game_teams:
                for player in team.get("players", []):
                    total_kills += player.get("kills", 0)
                    total_deaths += player.get("deaths", 0)

                    champ = player.get("character", {}).get("name", "Unknown")
                    champion_picks[champ] = champion_picks.get(champ, 0) + 1

            # Determine winner by score
            if len(game_teams) >= 2:
                if game_teams[0].get("score", 0) > game_teams[1].get("score", 0):
                    wins += 1

        # Win rate pattern
        if total_games >= 3:
            win_rate = wins / total_games
            if win_rate < 0.4:
                patterns.append(Pattern(
                    pattern_type="low_win_rate",
                    description=f"Team win rate ({win_rate*100:.1f}%) needs improvement",
                    frequency=win_rate,
                    impact="negative",
                    games_observed=total_games,
                    recommendation="Review team coordination and draft strategies",
                ))
            elif win_rate > 0.6:
                patterns.append(Pattern(
                    pattern_type="high_win_rate",
                    description=f"Strong team win rate ({win_rate*100:.1f}%)",
                    frequency=win_rate,
                    impact="positive",
                    games_observed=total_games,
                    recommendation="Maintain current strategies and team synergy",
                ))

        # KDA pattern
        if total_deaths > 0:
            team_kda = total_kills / total_deaths
            if team_kda < 0.9:
                patterns.append(Pattern(
                    pattern_type="negative_kd",
                    description=f"Team K/D ratio ({team_kda:.2f}) is below 1.0",
                    frequency=team_kda,
                    impact="negative",
                    games_observed=total_games,
                    recommendation="Focus on trading and reducing unnecessary deaths",
                ))

        return patterns

    def _detect_valorant_team_patterns(
        self,
        matches: list[dict[str, Any]],
    ) -> list[Pattern]:
        """Detect VALORANT-specific team patterns."""
        patterns = []

        if not matches:
            return patterns

        # Aggregate stats across all games
        total_games = len(matches)
        wins = 0
        total_kills = 0
        total_deaths = 0
        agent_picks: dict[str, int] = {}

        for match in matches:
            game = match.get("game", {})
            game_teams = game.get("teams", [])

            for team in game_teams:
                team_score = team.get("score", 0)
                for player in team.get("players", []):
                    total_kills += player.get("kills", 0)
                    total_deaths += player.get("deaths", 0)

                    agent = player.get("character", {}).get("name", "Unknown")
                    agent_picks[agent] = agent_picks.get(agent, 0) + 1

            # Determine winner by score
            if len(game_teams) >= 2:
                if game_teams[0].get("score", 0) > game_teams[1].get("score", 0):
                    wins += 1

        # Win rate pattern
        if total_games >= 3:
            win_rate = wins / total_games
            if win_rate < 0.4:
                patterns.append(Pattern(
                    pattern_type="low_win_rate",
                    description=f"Team win rate ({win_rate*100:.1f}%) needs improvement",
                    frequency=win_rate,
                    impact="negative",
                    games_observed=total_games,
                    recommendation="Review team coordination and strategy execution",
                ))
            elif win_rate > 0.6:
                patterns.append(Pattern(
                    pattern_type="high_win_rate",
                    description=f"Strong team win rate ({win_rate*100:.1f}%)",
                    frequency=win_rate,
                    impact="positive",
                    games_observed=total_games,
                    recommendation="Maintain current strategies and team synergy",
                ))

        # KDA pattern
        if total_deaths > 0:
            team_kda = total_kills / total_deaths
            if team_kda < 0.9:
                patterns.append(Pattern(
                    pattern_type="negative_kd",
                    description=f"Team K/D ratio ({team_kda:.2f}) is below 1.0",
                    frequency=team_kda,
                    impact="negative",
                    games_observed=total_games,
                    recommendation="Focus on trading and reducing unnecessary deaths",
                ))

        # Agent diversity pattern
        if len(agent_picks) < 8 and total_games >= 5:
            patterns.append(Pattern(
                pattern_type="limited_agent_pool",
                description=f"Team uses only {len(agent_picks)} unique agents",
                frequency=len(agent_picks) / 20,  # 20 agents in Valorant
                impact="neutral",
                games_observed=total_games,
                recommendation="Consider expanding agent pool for strategic flexibility",
            ))

        return patterns

    def _extract_player_highlights(
        self,
        matches: list[dict[str, Any]],
    ) -> dict[str, list[str]]:
        """Extract notable player performances from matches."""
        highlights: dict[str, list[str]] = {}

        for match in matches:
            game = match.get("game", {})
            for team in game.get("teams", []):
                for player in team.get("players", []):
                    player_name = player.get("name", "Unknown")
                    if player_name not in highlights:
                        highlights[player_name] = []

                    # Check for standout performances
                    kills = player.get("kills", 0)
                    deaths = player.get("deaths", 0)
                    assists = player.get("killAssistsGiven", 0)

                    if kills >= 20 and deaths <= 10:
                        highlights[player_name].append(
                            f"Strong game: {kills}/{deaths}/{assists}"
                        )
                    elif deaths > 20:
                        highlights[player_name].append(
                            f"Struggled: {kills}/{deaths}/{assists}"
                        )

        return highlights

    async def _generate_player_insights(
        self,
        player_id: str,
        performances: list[dict[str, Any]],
        patterns: list[Pattern],
        game: GameType,
        focus_areas: Optional[list[str]] = None,
    ) -> list[Insight]:
        """Generate actionable insights from player patterns."""
        insights = []

        # Convert patterns to insights
        for pattern in patterns:
            priority = "high" if pattern.impact == "negative" else "medium"
            category = self._categorize_pattern(pattern.pattern_type)

            insights.append(Insight(
                title=pattern.description,
                category=category,
                priority=priority,
                description=pattern.recommendation or "",
                data_points=[{"pattern": pattern.pattern_type, "frequency": pattern.frequency}],
                actionable_steps=self._generate_action_steps(pattern, game),
            ))

        return insights

    async def _generate_team_insights(
        self,
        team_id: str,
        matches: list[dict[str, Any]],
        patterns: list[Pattern],
        game: GameType,
        focus_areas: Optional[list[str]] = None,
    ) -> list[Insight]:
        """Generate actionable insights from team patterns."""
        insights = []

        for pattern in patterns:
            priority = "high" if pattern.impact == "negative" else "medium"

            insights.append(Insight(
                title=pattern.description,
                category="strategic",
                priority=priority,
                description=pattern.recommendation or "",
                data_points=[{"pattern": pattern.pattern_type, "frequency": pattern.frequency}],
                actionable_steps=self._generate_action_steps(pattern, game),
            ))

        return insights

    def _categorize_pattern(self, pattern_type: str) -> str:
        """Categorize a pattern type."""
        mechanical = ["low_cs", "headshot", "aim"]
        strategic = ["vision", "first_dragon", "pistol", "economy"]
        mental = ["tilt", "comeback", "clutch"]
        teamwork = ["trading", "rotation", "communication"]

        for category, keywords in [
            ("mechanical", mechanical),
            ("strategic", strategic),
            ("mental", mental),
            ("teamwork", teamwork),
        ]:
            if any(kw in pattern_type.lower() for kw in keywords):
                return category

        return "strategic"

    def _generate_action_steps(
        self,
        pattern: Pattern,
        game: GameType,
    ) -> list[str]:
        """Generate action steps for a pattern."""
        steps = []

        if "death" in pattern.pattern_type.lower():
            steps.extend([
                "Review death timers and respawn locations",
                "Practice positioning in custom games",
                "Communicate positions more frequently",
            ])
        elif "vision" in pattern.pattern_type.lower():
            steps.extend([
                "Set reminders for ward placement timings",
                "Review professional VODs for ward spots",
                "Track enemy jungle pathing",
            ])
        elif "cs" in pattern.pattern_type.lower():
            steps.extend([
                "Practice last-hitting in tool mode",
                "Focus on wave management concepts",
                "Review CS benchmarks at key timings",
            ])
        elif "kast" in pattern.pattern_type.lower():
            steps.extend([
                "Focus on trading positions",
                "Avoid isolated fights",
                "Communicate utility usage with team",
            ])
        elif "clutch" in pattern.pattern_type.lower():
            steps.extend([
                "Review clutch scenarios in VODs",
                "Practice 1vX situations in deathmatch",
                "Work on information gathering in clutches",
            ])

        return steps or [pattern.recommendation or "Review gameplay footage"]
