"""Composition tracker service for meta and composition analysis."""

from typing import Any, Optional
from collections import defaultdict


from shared.grid_client import GridClient
from shared.grid_client.lol import LoLTeamQueries, LoLMatchQueries
from shared.grid_client.valorant import ValorantTeamQueries, ValorantMatchQueries

from app.models.schemas import (
    GameType,
    CompositionAnalysis,
)


class CompositionTracker:
    """Tracks and analyzes team compositions and meta trends."""

    def __init__(self, grid_client: Optional[GridClient] = None):
        self.grid_client = grid_client or GridClient()

    async def analyze_compositions(
        self,
        team_id: str,
        match_ids: list[str],
        game: GameType,
    ) -> list[CompositionAnalysis]:
        """Analyze team's composition patterns.

        Args:
            team_id: Team ID
            match_ids: Match IDs to analyze
            game: Game type

        Returns:
            List of CompositionAnalysis for common compositions
        """
        # Fetch composition data
        if game == GameType.LOL:
            compositions = await self._fetch_lol_compositions(team_id, match_ids)
            return self._analyze_lol_compositions(compositions)
        else:
            compositions = await self._fetch_valorant_compositions(team_id, match_ids)
            return self._analyze_valorant_compositions(compositions)

    async def _fetch_lol_compositions(
        self,
        team_id: str,
        match_ids: list[str],
    ) -> list[dict[str, Any]]:
        """Fetch LoL team compositions."""
        queries = LoLTeamQueries(self.grid_client)
        result = await queries.get_team_compositions(team_id, match_ids)
        return result.get("team", {}).get("compositions", [])

    async def _fetch_valorant_compositions(
        self,
        team_id: str,
        match_ids: list[str],
    ) -> list[dict[str, Any]]:
        """Fetch VALORANT team compositions."""
        queries = ValorantTeamQueries(self.grid_client)
        result = await queries.get_team_compositions(team_id, match_ids)
        return result.get("team", {}).get("compositions", [])

    def _analyze_lol_compositions(
        self,
        compositions: list[dict[str, Any]],
    ) -> list[CompositionAnalysis]:
        """Analyze LoL compositions."""
        analyses = []

        for comp in compositions[:10]:  # Top 10 compositions
            champions = [c.get("name", "") for c in comp.get("champions", [])]
            games = comp.get("gamesPlayed", 0)
            wins = comp.get("wins", 0)

            # Determine strategy type
            strategy_type = self._classify_lol_comp(champions)

            # Identify strengths and weaknesses
            strengths, weaknesses = self._assess_lol_comp(champions)

            # Identify power spikes
            power_spikes = self._identify_lol_power_spikes(champions)

            # Counter strategies
            counters = self._generate_lol_counter_strategies(champions, strategy_type)

            analyses.append(CompositionAnalysis(
                composition=champions,
                games_played=games,
                win_rate=wins / games if games > 0 else 0.0,
                strategy_type=strategy_type,
                strengths=strengths,
                weaknesses=weaknesses,
                power_spikes=power_spikes,
                counter_strategies=counters,
            ))

        return analyses

    def _analyze_valorant_compositions(
        self,
        compositions: list[dict[str, Any]],
    ) -> list[CompositionAnalysis]:
        """Analyze VALORANT compositions."""
        analyses = []

        for comp in compositions[:10]:
            agents = [a.get("name", "") for a in comp.get("agents", [])]
            map_name = comp.get("map", {}).get("name", "")
            games = comp.get("gamesPlayed", 0)
            wins = comp.get("wins", 0)

            # Determine strategy type based on agent roles
            strategy_type = self._classify_valorant_comp(agents)

            # Site preferences
            site_prefs = {}
            attack_wr = comp.get("attackRoundWinRate", 0.5)
            defense_wr = comp.get("defenseRoundWinRate", 0.5)

            # Strengths and weaknesses
            strengths, weaknesses = self._assess_valorant_comp(agents)

            # Counter strategies
            counters = self._generate_valorant_counter_strategies(agents, map_name)

            analyses.append(CompositionAnalysis(
                composition=agents,
                games_played=games,
                win_rate=wins / games if games > 0 else 0.0,
                strategy_type=strategy_type,
                strengths=strengths,
                weaknesses=weaknesses,
                counter_strategies=counters,
                map=map_name,
                site_preferences={"attack_wr": attack_wr, "defense_wr": defense_wr},
            ))

        return analyses

    def _classify_lol_comp(self, champions: list[str]) -> str:
        """Classify LoL team composition type."""
        # Simplified classification based on common archetypes
        engage_champs = ["Ornn", "Malphite", "Leona", "Nautilus", "Sejuani"]
        poke_champs = ["Jayce", "Nidalee", "Xerath", "Zoe", "Varus"]
        split_champs = ["Fiora", "Jax", "Tryndamere", "Camille"]

        engage_count = sum(1 for c in champions if c in engage_champs)
        poke_count = sum(1 for c in champions if c in poke_champs)
        split_count = sum(1 for c in champions if c in split_champs)

        if engage_count >= 2:
            return "Teamfight/Engage"
        elif poke_count >= 2:
            return "Poke/Siege"
        elif split_count >= 1:
            return "Split-push"
        else:
            return "Standard/Skirmish"

    def _classify_valorant_comp(self, agents: list[str]) -> str:
        """Classify VALORANT team composition type."""
        duelists = ["Jett", "Raze", "Reyna", "Phoenix", "Yoru", "Neon", "Iso"]
        controllers = ["Brimstone", "Omen", "Viper", "Astra", "Harbor"]
        initiators = ["Sova", "Breach", "Skye", "KAY/O", "Fade", "Gekko"]
        sentinels = ["Killjoy", "Cypher", "Sage", "Chamber", "Deadlock"]

        duelist_count = sum(1 for a in agents if a in duelists)
        controller_count = sum(1 for a in agents if a in controllers)
        initiator_count = sum(1 for a in agents if a in initiators)

        if duelist_count >= 2:
            return "Aggressive/Entry-focused"
        elif controller_count >= 2:
            return "Control/Execute"
        elif initiator_count >= 2:
            return "Information-based"
        else:
            return "Standard/Balanced"

    def _assess_lol_comp(
        self,
        champions: list[str],
    ) -> tuple[list[str], list[str]]:
        """Assess LoL composition strengths and weaknesses."""
        strengths = []
        weaknesses = []

        # Simplified assessment
        ap_heavy = ["Syndra", "Orianna", "Viktor", "Azir", "Ryze"]
        ad_heavy = ["Zed", "Talon", "Jayce", "Pantheon"]

        ap_count = sum(1 for c in champions if c in ap_heavy)
        ad_count = sum(1 for c in champions if c in ad_heavy)

        if ap_count >= 3:
            weaknesses.append("AP-heavy, vulnerable to MR stacking")
        if ad_count >= 3:
            weaknesses.append("AD-heavy, vulnerable to armor stacking")

        return strengths, weaknesses

    def _assess_valorant_comp(
        self,
        agents: list[str],
    ) -> tuple[list[str], list[str]]:
        """Assess VALORANT composition strengths and weaknesses."""
        strengths = []
        weaknesses = []

        # Check for role coverage
        has_smoke = any(a in ["Omen", "Brimstone", "Astra", "Viper", "Harbor"] for a in agents)
        has_flash = any(a in ["Breach", "Skye", "KAY/O", "Phoenix", "Yoru", "Reyna"] for a in agents)
        has_info = any(a in ["Sova", "Fade", "Gekko", "Cypher", "Killjoy"] for a in agents)

        if has_smoke:
            strengths.append("Has smoke coverage for executes")
        else:
            weaknesses.append("No smoke agent - limited execute options")

        if has_flash:
            strengths.append("Flash utility for entries")
        else:
            weaknesses.append("No flash utility - harder entries")

        if has_info:
            strengths.append("Information gathering capability")
        else:
            weaknesses.append("Limited information gathering")

        return strengths, weaknesses

    def _identify_lol_power_spikes(self, champions: list[str]) -> list[str]:
        """Identify team composition power spikes."""
        spikes = []

        early_game = ["Renekton", "Lee Sin", "Elise", "Draven", "Lucian"]
        mid_game = ["Corki", "Azir", "Tristana"]
        late_game = ["Kayle", "Kassadin", "Vayne", "Kog'Maw"]

        if sum(1 for c in champions if c in early_game) >= 2:
            spikes.append("Strong levels 1-10")
        if sum(1 for c in champions if c in mid_game) >= 2:
            spikes.append("2-item power spike (~20-25 min)")
        if sum(1 for c in champions if c in late_game) >= 2:
            spikes.append("Strong 35+ minutes")

        return spikes or ["Moderate scaling throughout game"]

    def _generate_lol_counter_strategies(
        self,
        champions: list[str],
        strategy_type: str,
    ) -> list[str]:
        """Generate counter-strategy suggestions."""
        counters = []

        if strategy_type == "Teamfight/Engage":
            counters.extend([
                "Pick disengage/peel compositions",
                "Avoid 5v5 fights, focus on side lanes",
                "Split map pressure to prevent grouping",
            ])
        elif strategy_type == "Poke/Siege":
            counters.extend([
                "Hard engage to close distance quickly",
                "Flank angles to bypass poke zones",
                "1-3-1 to prevent siege grouping",
            ])
        elif strategy_type == "Split-push":
            counters.extend([
                "Force fights before they split",
                "Strong waveclear to match side pressure",
                "Collapse quickly with globals",
            ])

        return counters

    def _generate_valorant_counter_strategies(
        self,
        agents: list[str],
        map_name: str,
    ) -> list[str]:
        """Generate VALORANT counter-strategy suggestions."""
        counters = []

        # Agent-specific counters
        if "Viper" in agents:
            counters.append("Push through Viper wall early before lineup")
        if "Killjoy" in agents:
            counters.append("Hunt for Killjoy utility pre-execute")
        if "Sova" in agents:
            counters.append("Avoid common recon positions")

        # Comp-type counters
        duelists = ["Jett", "Raze", "Reyna", "Phoenix", "Yoru", "Neon"]
        if sum(1 for a in agents if a in duelists) >= 2:
            counters.append("Expect aggressive entries - hold angles passively")

        return counters
