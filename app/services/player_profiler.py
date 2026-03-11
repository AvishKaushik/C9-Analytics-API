"""Player profiler service for individual tendency analysis."""

from typing import Any, Optional
from statistics import mean


from shared.grid_client import GridClient
from shared.grid_client.lol import LoLPlayerQueries, LoLMatchQueries
from shared.grid_client.valorant import ValorantPlayerQueries, ValorantMatchQueries

from app.models.schemas import (
    GameType,
    PlayerProfile,
    ChampionAgentStats,
)


class PlayerProfiler:
    """Profiles individual player tendencies and patterns."""

    def __init__(self, grid_client: Optional[GridClient] = None):
        self.grid_client = grid_client or GridClient()

    async def profile_player(
        self,
        player_id: str,
        match_ids: list[str],
        game: GameType,
    ) -> PlayerProfile:
        """Create a comprehensive player profile.

        Args:
            player_id: Player ID
            match_ids: Match IDs to analyze
            game: Game type

        Returns:
            PlayerProfile with tendencies and analysis
        """
        # Fetch performances
        performances = await self._fetch_performances(player_id, match_ids, game)

        # Build profile from actual data
        if game == GameType.LOL:
            return self._build_lol_profile(player_id, performances)
        else:
            return self._build_valorant_profile(player_id, performances)

    async def profile_team_players(
        self,
        team_id: str,
        match_ids: list[str],
        game: GameType,
    ) -> list[PlayerProfile]:
        """Profile all players on a team from match data.

        Args:
            team_id: Team ID
            match_ids: Match IDs to analyze
            game: Game type

        Returns:
            List of PlayerProfiles for team members
        """
        # Fetch match data to extract players
        if game == GameType.LOL:
            queries = LoLMatchQueries(self.grid_client)
        else:
            queries = ValorantMatchQueries(self.grid_client)

        # Collect player data from matches
        player_data: dict[str, dict] = {}

        for match_id in match_ids:
            try:
                result = await queries.get_series_state(match_id)
                state = result.get("seriesState", {})
                if not state:
                    continue

                teams = state.get("teams", [])
                games = state.get("games", [])

                # Find our team index
                our_team_idx = None
                for idx, t in enumerate(teams):
                    if str(t.get("id")) == str(team_id):
                        our_team_idx = idx
                        break

                if our_team_idx is None:
                    continue

                # Extract player performances from each game
                for game_data in games:
                    if not game_data.get("finished"):
                        continue

                    game_teams = game_data.get("teams", [])
                    if our_team_idx >= len(game_teams):
                        continue

                    our_team = game_teams[our_team_idx]
                    our_score = our_team.get("score", 0)

                    enemy_idx = 1 if our_team_idx == 0 else 0
                    enemy_team = game_teams[enemy_idx] if enemy_idx < len(game_teams) else {}
                    enemy_score = enemy_team.get("score", 0)
                    is_win = our_score > enemy_score

                    for player in our_team.get("players", []):
                        player_id = str(player.get("id", "unknown"))
                        player_name = player.get("name", f"Player {player_id}")

                        if player_id not in player_data:
                            player_data[player_id] = {
                                "player_id": player_id,
                                "player_name": player_name,
                                "performances": [],
                            }

                        # Record this performance
                        perf = {
                            "kills": player.get("kills", 0),
                            "deaths": player.get("deaths", 0),
                            "assists": player.get("killAssistsGiven", 0) or player.get("assists", 0),
                            "character": player.get("character", {}),
                            "win": is_win,
                            "score": our_score,
                            "enemy_score": enemy_score,
                        }
                        player_data[player_id]["performances"].append(perf)

            except Exception:
                continue

        # Build profiles for each player
        profiles = []
        for player_id, data in player_data.items():
            if game == GameType.LOL:
                profile = self._build_lol_profile_from_data(
                    data["player_id"],
                    data["player_name"],
                    data["performances"]
                )
            else:
                profile = self._build_valorant_profile_from_data(
                    data["player_id"],
                    data["player_name"],
                    data["performances"]
                )
            profiles.append(profile)

        return profiles

    async def _fetch_performances(
        self,
        player_id: str,
        match_ids: list[str],
        game: GameType,
    ) -> list[dict[str, Any]]:
        """Fetch individual game performances."""
        if game == GameType.LOL:
            queries = LoLPlayerQueries(self.grid_client)
        else:
            queries = ValorantPlayerQueries(self.grid_client)

        result = await queries.get_player_performance(player_id, match_ids)
        return result.get("player", {}).get("performances", [])

    def _build_lol_profile(
        self,
        player_id: str,
        performances: list[dict[str, Any]],
    ) -> PlayerProfile:
        """Build LoL player profile from performances."""
        return self._build_lol_profile_from_data(player_id, player_id, performances)

    def _build_lol_profile_from_data(
        self,
        player_id: str,
        player_name: str,
        performances: list[dict[str, Any]],
    ) -> PlayerProfile:
        """Build LoL player profile from performance data."""
        if not performances:
            return PlayerProfile(
                player_id=player_id,
                player_name=player_name,
                primary_picks=[],
                playstyle="unknown",
                strengths=[],
                weaknesses=["No performance data available"],
                tendencies=[],
                threat_level="unknown",
                average_stats={},
            )

        # Calculate stats
        total_kills = sum(p.get("kills", 0) for p in performances)
        total_deaths = sum(p.get("deaths", 0) for p in performances)
        total_assists = sum(p.get("assists", 0) for p in performances)
        games = len(performances)
        wins = sum(1 for p in performances if p.get("win"))

        avg_kills = total_kills / games
        avg_deaths = total_deaths / games
        avg_assists = total_assists / games
        win_rate = wins / games
        kda = (total_kills + total_assists) / max(total_deaths, 1)

        # Champion pool
        champion_stats: dict[str, dict] = {}
        for p in performances:
            champ = p.get("champion", {}) or p.get("character", {})
            champ_name = champ.get("name", "Unknown")
            if champ_name not in champion_stats:
                champion_stats[champ_name] = {"games": 0, "wins": 0, "kills": 0, "deaths": 0, "assists": 0}
            champion_stats[champ_name]["games"] += 1
            if p.get("win"):
                champion_stats[champ_name]["wins"] += 1
            champion_stats[champ_name]["kills"] += p.get("kills", 0)
            champion_stats[champ_name]["deaths"] += p.get("deaths", 0)
            champion_stats[champ_name]["assists"] += p.get("assists", 0)

        primary_picks = []
        for champ_name, stats in sorted(champion_stats.items(), key=lambda x: x[1]["games"], reverse=True)[:5]:
            champ_games = stats["games"]
            champ_deaths = stats["deaths"] or 1
            primary_picks.append(ChampionAgentStats(
                name=champ_name,
                games_played=champ_games,
                wins=stats["wins"],
                losses=champ_games - stats["wins"],
                win_rate=stats["wins"] / champ_games if champ_games > 0 else 0,
                average_kda=(stats["kills"] + stats["assists"]) / champ_deaths,
            ))

        # Determine playstyle
        if avg_kills > avg_assists:
            playstyle = "aggressive"
        elif avg_deaths > (avg_kills + avg_assists) / 3:
            playstyle = "high-risk"
        else:
            playstyle = "supportive"

        # Strengths and weaknesses
        strengths = []
        weaknesses = []
        tendencies = []

        if kda > 3.5:
            strengths.append("Excellent KDA")
        elif kda < 2.0:
            weaknesses.append("Low KDA - dies frequently")

        if win_rate > 0.55:
            strengths.append(f"Strong win rate ({win_rate:.0%})")
        elif win_rate < 0.45:
            weaknesses.append(f"Low win rate ({win_rate:.0%})")

        if avg_kills > 8:
            tendencies.append("High kill threat")
        if avg_deaths > 5:
            tendencies.append("Prone to dying")
        if avg_assists > 10:
            tendencies.append("Team-oriented player")

        # Threat assessment
        if kda > 3.0 and win_rate > 0.55:
            threat_level = "high"
        elif kda < 2.0 or win_rate < 0.45:
            threat_level = "low"
        else:
            threat_level = "medium"

        return PlayerProfile(
            player_id=player_id,
            player_name=player_name,
            primary_picks=primary_picks,
            playstyle=playstyle,
            strengths=strengths if strengths else ["No notable strengths"],
            weaknesses=weaknesses if weaknesses else ["No notable weaknesses"],
            tendencies=tendencies if tendencies else ["Standard play patterns"],
            threat_level=threat_level,
            average_stats={
                "kills": round(avg_kills, 1),
                "deaths": round(avg_deaths, 1),
                "assists": round(avg_assists, 1),
                "kda": round(kda, 2),
                "winRate": round(win_rate, 2),
                "gamesPlayed": games,
            },
        )

    def _build_valorant_profile(
        self,
        player_id: str,
        performances: list[dict[str, Any]],
    ) -> PlayerProfile:
        """Build VALORANT player profile from performances."""
        return self._build_valorant_profile_from_data(player_id, player_id, performances)

    def _build_valorant_profile_from_data(
        self,
        player_id: str,
        player_name: str,
        performances: list[dict[str, Any]],
    ) -> PlayerProfile:
        """Build VALORANT player profile from performance data."""
        if not performances:
            return PlayerProfile(
                player_id=player_id,
                player_name=player_name,
                primary_picks=[],
                playstyle="unknown",
                strengths=[],
                weaknesses=["No performance data available"],
                tendencies=[],
                threat_level="unknown",
                average_stats={},
            )

        # Calculate stats
        total_kills = sum(p.get("kills", 0) for p in performances)
        total_deaths = sum(p.get("deaths", 0) for p in performances)
        total_assists = sum(p.get("assists", 0) for p in performances)
        games = len(performances)
        wins = sum(1 for p in performances if p.get("win"))

        avg_kills = total_kills / games
        avg_deaths = total_deaths / games
        avg_assists = total_assists / games
        win_rate = wins / games
        kda = (total_kills + total_assists) / max(total_deaths, 1)

        # Agent pool
        agent_stats: dict[str, dict] = {}
        for p in performances:
            agent = p.get("agent", {}) or p.get("character", {})
            agent_name = agent.get("name", "Unknown")
            if agent_name not in agent_stats:
                agent_stats[agent_name] = {"games": 0, "wins": 0, "kills": 0, "deaths": 0, "assists": 0}
            agent_stats[agent_name]["games"] += 1
            if p.get("win"):
                agent_stats[agent_name]["wins"] += 1
            agent_stats[agent_name]["kills"] += p.get("kills", 0)
            agent_stats[agent_name]["deaths"] += p.get("deaths", 0)
            agent_stats[agent_name]["assists"] += p.get("assists", 0)

        primary_picks = []
        for agent_name, stats in sorted(agent_stats.items(), key=lambda x: x[1]["games"], reverse=True)[:5]:
            agent_games = stats["games"]
            agent_deaths = stats["deaths"] or 1
            primary_picks.append(ChampionAgentStats(
                name=agent_name,
                games_played=agent_games,
                wins=stats["wins"],
                losses=agent_games - stats["wins"],
                win_rate=stats["wins"] / agent_games if agent_games > 0 else 0,
                average_kda=(stats["kills"] + stats["assists"]) / agent_deaths,
            ))

        # Determine role from agent picks
        duelists = ["Jett", "Raze", "Reyna", "Phoenix", "Yoru", "Neon", "Iso"]
        controllers = ["Brimstone", "Omen", "Viper", "Astra", "Harbor", "Clove"]
        initiators = ["Sova", "Breach", "Skye", "KAY/O", "Fade", "Gekko"]
        sentinels = ["Killjoy", "Cypher", "Sage", "Chamber", "Deadlock"]

        duelist_games = sum(agent_stats.get(a, {}).get("games", 0) for a in duelists)
        total_games = sum(s["games"] for s in agent_stats.values())
        is_duelist = duelist_games > total_games * 0.5 if total_games > 0 else False

        # Playstyle
        if is_duelist and avg_kills > avg_deaths:
            playstyle = "aggressive"
        elif avg_deaths > avg_kills:
            playstyle = "passive"
        else:
            playstyle = "adaptive"

        # Strengths and weaknesses
        strengths = []
        weaknesses = []
        tendencies = []

        if kda > 2.5:
            strengths.append("Strong KDA performance")
        elif kda < 1.5:
            weaknesses.append("Low impact - poor KDA")

        if win_rate > 0.55:
            strengths.append(f"Winning player ({win_rate:.0%} WR)")
        elif win_rate < 0.45:
            weaknesses.append(f"Struggling recently ({win_rate:.0%} WR)")

        if avg_kills > 18:
            tendencies.append("High fragging output")
            strengths.append("Carries through kills")
        elif avg_kills < 12:
            tendencies.append("Low frag count")

        if avg_deaths > 15:
            tendencies.append("Dies frequently - exploitable")
            weaknesses.append("High death count")

        if is_duelist:
            tendencies.append("Primary duelist/entry player")
        else:
            tendencies.append("Support/utility role")

        # Threat level
        if kda > 2.0 and win_rate > 0.55:
            threat_level = "high"
        elif kda < 1.5 or win_rate < 0.45:
            threat_level = "low"
        else:
            threat_level = "medium"

        return PlayerProfile(
            player_id=player_id,
            player_name=player_name,
            primary_picks=primary_picks,
            playstyle=playstyle,
            strengths=strengths if strengths else ["No notable strengths"],
            weaknesses=weaknesses if weaknesses else ["No notable weaknesses"],
            tendencies=tendencies if tendencies else ["Standard play patterns"],
            threat_level=threat_level,
            average_stats={
                "kills": round(avg_kills, 1),
                "deaths": round(avg_deaths, 1),
                "assists": round(avg_assists, 1),
                "kda": round(kda, 2),
                "winRate": round(win_rate, 2),
                "gamesPlayed": games,
            },
        )
