"""Champion analyzer service for player pool and champion data analysis."""

from typing import Any, Optional


from shared.grid_client import GridClient
from shared.grid_client.lol import LoLPlayerQueries, LoLTeamQueries, LoLMatchQueries

from app.models.schemas import (
    Role,
    ChampionInfo,
    PlayerChampionPool,
)


class ChampionAnalyzer:
    """Analyzes champion data and player pools."""

    # Meta tier list (would be updated from patch data in production)
    META_TIERS: dict[str, str] = {
        # Top lane
        "K'Sante": "S", "Aatrox": "S", "Rumble": "A", "Renekton": "A",
        "Jax": "A", "Gnar": "B", "Ornn": "A", "Gragas": "B",
        "Fiora": "A", "Camille": "A", "Jayce": "B", "Kennen": "B",
        "Shen": "A", "Gangplank": "A", "Gwen": "B", "Malphite": "B",
        "Darius": "B", "Mordekaiser": "B", "Sett": "A", "Urgot": "C",
        # Jungle
        "Vi": "S", "Lee Sin": "S", "Viego": "A", "Maokai": "A",
        "Sejuani": "A", "Jarvan IV": "B", "Elise": "B", "Rek'Sai": "B",
        "Nocturne": "A", "Xin Zhao": "B", "Nidalee": "B", "Graves": "A",
        "Kindred": "A", "Hecarim": "B", "Kha'Zix": "B", "Rengar": "C",
        "Wukong": "A", "Poppy": "B", "Ivern": "B", "Taliyah": "A",
        # Mid
        "Azir": "S", "Ahri": "S", "Syndra": "A", "Orianna": "A",
        "Corki": "A", "LeBlanc": "B", "Akali": "B", "Zoe": "B",
        "Viktor": "A", "Zed": "B", "Sylas": "A", "Kassadin": "B",
        "Neeko": "A", "Twisted Fate": "B", "Ryze": "B", "Cassiopeia": "A",
        "Lissandra": "B", "Galio": "A", "Yasuo": "B", "Yone": "B",
        # ADC
        "Kai'Sa": "S", "Varus": "S", "Jinx": "A", "Zeri": "A",
        "Aphelios": "A", "Xayah": "B", "Ezreal": "B", "Tristana": "B",
        "Caitlyn": "A", "Miss Fortune": "B", "Lucian": "B", "Draven": "B",
        "Ashe": "B", "Sivir": "B", "Samira": "B", "Jhin": "A",
        "Kog'Maw": "B", "Twitch": "C", "Kalista": "A", "Nilah": "B",
        # Support
        "Nautilus": "S", "Thresh": "S", "Renata Glasc": "A", "Rakan": "A",
        "Alistar": "A", "Lulu": "B", "Braum": "B", "Milio": "B",
        "Leona": "A", "Morgana": "A", "Karma": "B", "Janna": "B",
        "Tahm Kench": "B", "Rell": "A", "Blitzcrank": "B", "Pyke": "B",
        "Zyra": "C", "Senna": "B", "Soraka": "C", "Nami": "B",
    }

    # Champion role mappings
    CHAMPION_ROLES: dict[str, list[Role]] = {
        # Top laners
        "Aatrox": [Role.TOP], "K'Sante": [Role.TOP], "Renekton": [Role.TOP],
        "Ornn": [Role.TOP], "Gnar": [Role.TOP], "Fiora": [Role.TOP],
        "Camille": [Role.TOP], "Jayce": [Role.TOP, Role.MID], "Kennen": [Role.TOP],
        "Shen": [Role.TOP], "Gangplank": [Role.TOP], "Gwen": [Role.TOP],
        "Malphite": [Role.TOP, Role.SUPPORT], "Darius": [Role.TOP],
        "Mordekaiser": [Role.TOP], "Sett": [Role.TOP, Role.SUPPORT], "Urgot": [Role.TOP],
        "Jax": [Role.TOP, Role.JUNGLE], "Gragas": [Role.TOP, Role.JUNGLE],
        "Rumble": [Role.TOP, Role.MID], "Akali": [Role.MID, Role.TOP],
        # Junglers
        "Vi": [Role.JUNGLE], "Lee Sin": [Role.JUNGLE], "Viego": [Role.JUNGLE],
        "Maokai": [Role.JUNGLE, Role.SUPPORT], "Sejuani": [Role.JUNGLE],
        "Jarvan IV": [Role.JUNGLE], "Elise": [Role.JUNGLE], "Rek'Sai": [Role.JUNGLE],
        "Nocturne": [Role.JUNGLE], "Xin Zhao": [Role.JUNGLE], "Nidalee": [Role.JUNGLE],
        "Graves": [Role.JUNGLE], "Kindred": [Role.JUNGLE], "Hecarim": [Role.JUNGLE],
        "Kha'Zix": [Role.JUNGLE], "Rengar": [Role.JUNGLE], "Wukong": [Role.JUNGLE, Role.TOP],
        "Poppy": [Role.JUNGLE, Role.TOP], "Ivern": [Role.JUNGLE], "Taliyah": [Role.JUNGLE, Role.MID],
        # Mid laners
        "Azir": [Role.MID], "Ahri": [Role.MID], "Syndra": [Role.MID],
        "Orianna": [Role.MID], "Corki": [Role.MID], "LeBlanc": [Role.MID],
        "Zoe": [Role.MID], "Viktor": [Role.MID], "Zed": [Role.MID],
        "Sylas": [Role.MID], "Kassadin": [Role.MID], "Neeko": [Role.MID],
        "Twisted Fate": [Role.MID], "Ryze": [Role.MID], "Cassiopeia": [Role.MID],
        "Lissandra": [Role.MID], "Galio": [Role.MID, Role.SUPPORT], "Yasuo": [Role.MID, Role.TOP],
        "Yone": [Role.MID, Role.TOP], "Tristana": [Role.ADC, Role.MID],
        # ADCs
        "Kai'Sa": [Role.ADC], "Varus": [Role.ADC], "Jinx": [Role.ADC],
        "Zeri": [Role.ADC], "Aphelios": [Role.ADC], "Xayah": [Role.ADC],
        "Ezreal": [Role.ADC], "Caitlyn": [Role.ADC], "Miss Fortune": [Role.ADC],
        "Lucian": [Role.ADC, Role.MID], "Draven": [Role.ADC], "Ashe": [Role.ADC],
        "Sivir": [Role.ADC], "Samira": [Role.ADC], "Jhin": [Role.ADC],
        "Kog'Maw": [Role.ADC], "Twitch": [Role.ADC], "Kalista": [Role.ADC], "Nilah": [Role.ADC],
        # Supports
        "Nautilus": [Role.SUPPORT], "Thresh": [Role.SUPPORT], "Renata Glasc": [Role.SUPPORT],
        "Rakan": [Role.SUPPORT], "Alistar": [Role.SUPPORT], "Lulu": [Role.SUPPORT],
        "Braum": [Role.SUPPORT], "Milio": [Role.SUPPORT], "Leona": [Role.SUPPORT],
        "Morgana": [Role.SUPPORT, Role.MID], "Karma": [Role.SUPPORT], "Janna": [Role.SUPPORT],
        "Tahm Kench": [Role.SUPPORT, Role.TOP], "Rell": [Role.SUPPORT], "Blitzcrank": [Role.SUPPORT],
        "Pyke": [Role.SUPPORT], "Zyra": [Role.SUPPORT], "Senna": [Role.SUPPORT, Role.ADC],
        "Soraka": [Role.SUPPORT], "Nami": [Role.SUPPORT],
    }

    def __init__(self, grid_client: Optional[GridClient] = None):
        self.grid_client = grid_client or GridClient()
        self.champion_stats = {}
        self.synergies = {}
        self.counters = {}
        self.countered_by = {}

        # Populate stats from static data
        for name, tier in self.META_TIERS.items():
            if name not in self.champion_stats:
                self.champion_stats[name] = {}
            self.champion_stats[name]["tier"] = tier

        for name, roles in self.CHAMPION_ROLES.items():
            if name not in self.champion_stats:
                self.champion_stats[name] = {}
            self.champion_stats[name]["roles"] = roles

    async def get_team_champion_pools(
        self,
        team_id: str,
        num_matches: int = 10,
    ) -> list[PlayerChampionPool]:
        """Get champion pools for all players on a team from match data.

        Args:
            team_id: Team ID
            num_matches: Number of matches to analyze

        Returns:
            List of PlayerChampionPool for each player
        """
        # Fetch matches and extract player champion data
        match_queries = LoLMatchQueries(self.grid_client)

        # Get series list
        series_result = await match_queries.get_matches_by_team(team_id, limit=num_matches)
        edges = series_result.get("allSeries", {}).get("edges", [])

        # Track player champion stats
        player_stats: dict[str, dict] = {}

        for edge in edges[:num_matches]:
            series_id = edge.get("node", {}).get("id")
            if not series_id:
                continue

            try:
                # Fetch series state
                state_result = await match_queries.get_series_state(series_id)
                state = state_result.get("seriesState", {})
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

                # Process each game
                for game in games:
                    if not game.get("finished"):
                        continue

                    game_teams = game.get("teams", [])
                    if our_team_idx >= len(game_teams):
                        continue

                    our_team = game_teams[our_team_idx]
                    our_score = our_team.get("score", 0)

                    enemy_idx = 1 if our_team_idx == 0 else 0
                    enemy_score = game_teams[enemy_idx].get("score", 0) if enemy_idx < len(game_teams) else 0
                    is_win = our_score > enemy_score

                    for player in our_team.get("players", []):
                        player_id = str(player.get("id", "unknown"))
                        player_name = player.get("name", f"Player {player_id}")
                        champion = player.get("character", {}).get("name", "Unknown")

                        if player_id not in player_stats:
                            player_stats[player_id] = {
                                "player_name": player_name,
                                "champions": {},
                                "total_games": 0,
                            }

                        if champion not in player_stats[player_id]["champions"]:
                            player_stats[player_id]["champions"][champion] = {
                                "games": 0,
                                "wins": 0,
                                "kills": 0,
                                "deaths": 0,
                                "assists": 0,
                            }

                        champ_stats = player_stats[player_id]["champions"][champion]
                        champ_stats["games"] += 1
                        if is_win:
                            champ_stats["wins"] += 1
                        champ_stats["kills"] += player.get("kills", 0)
                        champ_stats["deaths"] += player.get("deaths", 0)
                        champ_stats["assists"] += player.get("killAssistsGiven", 0) or player.get("assists", 0)
                        player_stats[player_id]["total_games"] += 1

            except Exception:
                continue

        # Build PlayerChampionPool objects
        pools = []
        for player_id, data in player_stats.items():
            champions = []
            comfort_picks = []
            signature_picks = []

            # Sort champions by games played
            sorted_champs = sorted(
                data["champions"].items(),
                key=lambda x: x[1]["games"],
                reverse=True
            )

            for champ_name, stats in sorted_champs[:10]:
                games = stats["games"]
                wins = stats["wins"]
                win_rate = wins / games if games > 0 else 0.5
                deaths = stats["deaths"] or 1
                kda = (stats["kills"] + stats["assists"]) / deaths

                champ_info = self.get_champion_info(champ_name)
                champ_info.win_rate = win_rate
                champions.append(champ_info)

                # Identify comfort and signature picks
                if games >= 3 and win_rate >= 0.55:
                    comfort_picks.append(champ_name)
                if games >= 5 and win_rate >= 0.60:
                    signature_picks.append(champ_name)

            # Determine player role from most played champions
            role = self._determine_player_role(sorted_champs)

            pools.append(PlayerChampionPool(
                player_id=player_id,
                player_name=data["player_name"],
                role=role,
                champions=champions,
                comfort_picks=comfort_picks,
                signature_picks=signature_picks,
            ))

        return pools

    def _determine_player_role(self, champion_data: list) -> Role:
        """Determine player's role based on their champion pool."""
        role_scores: dict[Role, int] = {r: 0 for r in Role}

        for champ_name, stats in champion_data[:5]:
            games = stats["games"]
            roles = self.CHAMPION_ROLES.get(champ_name, [])
            for role in roles:
                role_scores[role] += games

        if role_scores:
            return max(role_scores, key=role_scores.get)
        return Role.MID

    def get_champion_info(self, champion_name: str) -> ChampionInfo:
        """Get info for a specific champion."""
        stats = self.champion_stats.get(champion_name, {})
        
        # Format name for Data Dragon (remove spaces/special chars)
        ddragon_name = champion_name.replace(" ", "").replace("'", "").replace(".", "")
        if ddragon_name == "Wukong":
            ddragon_name = "MonkeyKing"
        elif ddragon_name == "RenataGlasc":
            ddragon_name = "Renata"
            
        version = "14.1.1" # Should ideally be fetched dynamically, but hardcoding for stability for now
        image_url = f"https://ddragon.leagueoflegends.com/cdn/{version}/img/champion/{ddragon_name}.png"
        loading_image_url = f"https://ddragon.leagueoflegends.com/cdn/img/champion/loading/{ddragon_name}_0.jpg"

        return ChampionInfo(
            id=stats.get("id", champion_name.lower()),
            name=champion_name,
            roles=stats.get("roles", []),
            tier=stats.get("tier", "A"),
            win_rate=stats.get("win_rate", 0.5),
            pick_rate=stats.get("pick_rate", 0.1),
            ban_rate=stats.get("ban_rate", 0.1),
            image_url=image_url,
            loading_image_url=loading_image_url,
            synergies=self.synergies.get(champion_name, {}),
            counters=self.counters.get(champion_name, {}),
            countered_by=self.countered_by.get(champion_name, {}),
        )

    def get_meta_champions(self, role: Optional[Role] = None) -> list[ChampionInfo]:
        """Get current meta champions, optionally filtered by role."""
        champions = []

        for champ_name, tier in self.META_TIERS.items():
            champ_info = self.get_champion_info(champ_name)

            if role is None or role in champ_info.roles:
                champions.append(champ_info)

        # Sort by tier
        tier_order = {"S": 0, "A": 1, "B": 2, "C": 3, "D": 4}
        champions.sort(key=lambda c: tier_order.get(c.tier, 5))

        return champions

    def get_flex_picks(self) -> list[ChampionInfo]:
        """Get champions that can flex between multiple roles."""
        flex_picks = []

        for champ_name, roles in self.CHAMPION_ROLES.items():
            if len(roles) >= 2:
                champ_info = self.get_champion_info(champ_name)
                flex_picks.append(champ_info)

        return flex_picks

    async def analyze_draft_tendencies(
        self,
        team_id: str,
        num_matches: int = 10,
    ) -> dict[str, Any]:
        """Analyze a team's draft tendencies from match data.

        Args:
            team_id: Team ID
            num_matches: Number of matches to analyze

        Returns:
            Dictionary of draft tendencies
        """
        match_queries = LoLMatchQueries(self.grid_client)

        # Get series list
        series_result = await match_queries.get_matches_by_team(team_id, limit=num_matches)
        edges = series_result.get("allSeries", {}).get("edges", [])

        # Track picks and bans
        first_picks: dict[str, int] = {}
        first_bans: dict[str, int] = {}
        all_picks: dict[str, int] = {}

        for edge in edges[:num_matches]:
            series_id = edge.get("node", {}).get("id")
            if not series_id:
                continue

            try:
                state_result = await match_queries.get_series_state(series_id)
                state = state_result.get("seriesState", {})
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

                # Analyze each game's draft
                for game in games:
                    game_teams = game.get("teams", [])
                    if our_team_idx >= len(game_teams):
                        continue

                    our_team = game_teams[our_team_idx]
                    players = our_team.get("players", [])

                    # Track all picks
                    for player in players:
                        champion = player.get("character", {}).get("name", "")
                        if champion:
                            all_picks[champion] = all_picks.get(champion, 0) + 1

                    # First pick (if available - usually first player in list)
                    if players:
                        first_champ = players[0].get("character", {}).get("name", "")
                        if first_champ:
                            first_picks[first_champ] = first_picks.get(first_champ, 0) + 1

            except Exception:
                continue

        tendencies = {
            "first_pick_priority": sorted(
                first_picks.items(), key=lambda x: x[1], reverse=True
            )[:5],
            "first_ban_priority": sorted(
                first_bans.items(), key=lambda x: x[1], reverse=True
            )[:5],
            "most_played": sorted(
                all_picks.items(), key=lambda x: x[1], reverse=True
            )[:10],
            "role_priority": {},
            "flex_usage": [],
            "blind_picks": [],
            "counter_picks": [],
        }

        return tendencies
