"""Synergy engine for team composition analysis."""

from typing import Optional
from app.models.schemas import (
    Role,
    ChampionInfo,
    DraftPick,
)


class SynergyEngine:
    """Calculates and analyzes team composition synergies."""

    # Synergy definitions (champion pairs with synergy scores -1 to 1)
    SYNERGY_PAIRS: dict[tuple[str, str], float] = {
        # Knockup synergies with Yasuo
        ("Yasuo", "Malphite"): 0.9, ("Yasuo", "Gragas"): 0.8,
        ("Yasuo", "Alistar"): 0.8, ("Yasuo", "Rell"): 0.75,
        ("Yasuo", "Nautilus"): 0.7, ("Yasuo", "Vi"): 0.7,
        ("Yasuo", "Jarvan IV"): 0.75, ("Yasuo", "Ornn"): 0.7,
        ("Yasuo", "Sejuani"): 0.7, ("Yasuo", "Lee Sin"): 0.65,
        # Xayah Rakan
        ("Xayah", "Rakan"): 0.95,
        # Orianna ball delivery
        ("Orianna", "Jarvan IV"): 0.85, ("Orianna", "Malphite"): 0.85,
        ("Orianna", "Renekton"): 0.7, ("Orianna", "Hecarim"): 0.75,
        ("Orianna", "Nocturne"): 0.7, ("Orianna", "Shen"): 0.65,
        # Protect the carry
        ("Lulu", "Kog'Maw"): 0.9, ("Lulu", "Jinx"): 0.8,
        ("Lulu", "Twitch"): 0.85, ("Lulu", "Aphelios"): 0.75,
        ("Lulu", "Zeri"): 0.7, ("Lulu", "Vayne"): 0.7,
        ("Karma", "Kog'Maw"): 0.75, ("Karma", "Jinx"): 0.7,
        ("Janna", "Kog'Maw"): 0.75, ("Janna", "Jinx"): 0.7,
        ("Braum", "Jinx"): 0.7, ("Braum", "Aphelios"): 0.65,
        ("Tahm Kench", "Aphelios"): 0.7, ("Tahm Kench", "Kog'Maw"): 0.7,
        ("Milio", "Jinx"): 0.75, ("Milio", "Aphelios"): 0.7,
        # Engage combos
        ("Nautilus", "Kai'Sa"): 0.7, ("Nautilus", "Syndra"): 0.65,
        ("Nautilus", "Miss Fortune"): 0.7,
        ("Leona", "Yasuo"): 0.75, ("Leona", "Miss Fortune"): 0.75,
        ("Leona", "Samira"): 0.7, ("Leona", "Kalista"): 0.65,
        ("Thresh", "Jinx"): 0.65, ("Thresh", "Lucian"): 0.7,
        ("Alistar", "Samira"): 0.75, ("Alistar", "Kalista"): 0.7,
        ("Rell", "Samira"): 0.8, ("Rell", "Yasuo"): 0.75,
        # CC chains
        ("Sejuani", "Renekton"): 0.7, ("Sejuani", "Jax"): 0.65,
        ("Sejuani", "Yasuo"): 0.7,
        # Dive compositions
        ("Lee Sin", "Renekton"): 0.6, ("Lee Sin", "Akali"): 0.6,
        ("Vi", "Syndra"): 0.65, ("Vi", "Orianna"): 0.65,
        ("Jarvan IV", "Rumble"): 0.8, ("Jarvan IV", "Orianna"): 0.85,
        ("Nocturne", "Rell"): 0.7, ("Nocturne", "Orianna"): 0.7,
        ("Hecarim", "Orianna"): 0.75, ("Hecarim", "Rumble"): 0.7,
        # Poke compositions
        ("Jayce", "Varus"): 0.65, ("Jayce", "Ezreal"): 0.6,
        ("Nidalee", "Varus"): 0.6, ("Nidalee", "Ezreal"): 0.55,
        ("Zoe", "Varus"): 0.6, ("Zoe", "Ezreal"): 0.55,
        # Global synergies
        ("Shen", "Nocturne"): 0.7, ("Shen", "Twisted Fate"): 0.7,
        ("Twisted Fate", "Nocturne"): 0.65,
        ("Galio", "Nocturne"): 0.7, ("Galio", "Camille"): 0.65,
        # Wombo combo
        ("Malphite", "Miss Fortune"): 0.8, ("Malphite", "Orianna"): 0.85,
        ("Amumu", "Miss Fortune"): 0.8, ("Kennen", "Miss Fortune"): 0.75,
        ("Jarvan IV", "Miss Fortune"): 0.75,
        # Pick compositions
        ("Thresh", "Ahri"): 0.6, ("Thresh", "Syndra"): 0.65,
        ("Elise", "Syndra"): 0.65, ("Elise", "Twisted Fate"): 0.6,
        ("Lee Sin", "Syndra"): 0.6, ("Lee Sin", "Orianna"): 0.65,
        # Kalista synergies
        ("Kalista", "Thresh"): 0.7, ("Kalista", "Alistar"): 0.75,
        ("Kalista", "Nautilus"): 0.65, ("Kalista", "Rell"): 0.7,
        # Azir synergies
        ("Azir", "Gragas"): 0.7, ("Azir", "Lee Sin"): 0.65,
        ("Azir", "Jarvan IV"): 0.65,
        # Split push
        ("Shen", "Fiora"): 0.6, ("Shen", "Camille"): 0.6,
        ("Shen", "Jax"): 0.6,
        # Anti-synergies (negative)
        ("Azir", "Vayne"): -0.3, ("Yasuo", "Azir"): -0.2,
    }

    # Team composition archetypes
    COMP_ARCHETYPES = {
        "teamfight": {
            "champions": ["Orianna", "Malphite", "Sejuani", "Jarvan IV", "Rumble", "Kennen"],
            "description": "Strong 5v5 teamfight composition",
            "win_condition": "Group and force teamfights around objectives",
        },
        "pick": {
            "champions": ["Thresh", "Nautilus", "Ahri", "Syndra", "Elise", "Lee Sin"],
            "description": "Catch composition with pick potential",
            "win_condition": "Find picks on isolated targets, convert to objectives",
        },
        "split": {
            "champions": ["Fiora", "Jax", "Camille", "Tryndamere", "Shen"],
            "description": "Split-push oriented composition",
            "win_condition": "1-3-1 or 1-4 split, force favorable fights",
        },
        "poke": {
            "champions": ["Jayce", "Nidalee", "Xerath", "Zoe", "Varus", "Ezreal"],
            "description": "Poke and siege composition",
            "win_condition": "Poke enemies low before fights, siege towers",
        },
        "protect": {
            "champions": ["Lulu", "Karma", "Braum", "Orianna", "Janna"],
            "description": "Protect the carry composition",
            "win_condition": "Keep carry alive, scale to late game",
        },
    }

    def calculate_synergy_score(
        self,
        picks: list[DraftPick],
    ) -> float:
        """Calculate overall synergy score for a team composition.

        Args:
            picks: List of draft picks

        Returns:
            Synergy score from 0 to 1
        """
        if len(picks) < 2:
            return 0.5

        champion_names = [p.champion.name for p in picks]
        total_synergy = 0.0
        pair_count = 0

        # Check all pairs
        for i, champ1 in enumerate(champion_names):
            for champ2 in champion_names[i + 1:]:
                pair_score = self._get_pair_synergy(champ1, champ2)
                total_synergy += pair_score
                pair_count += 1

        if pair_count == 0:
            return 0.5

        # Normalize to 0-1 range (synergies are -1 to 1)
        avg_synergy = total_synergy / pair_count
        return (avg_synergy + 1) / 2

    def _get_pair_synergy(self, champ1: str, champ2: str) -> float:
        """Get synergy score for a champion pair."""
        # Check both orderings
        if (champ1, champ2) in self.SYNERGY_PAIRS:
            return self.SYNERGY_PAIRS[(champ1, champ2)]
        if (champ2, champ1) in self.SYNERGY_PAIRS:
            return self.SYNERGY_PAIRS[(champ2, champ1)]
        return 0.0  # Neutral synergy

    def identify_composition_type(
        self,
        picks: list[DraftPick],
    ) -> tuple[str, str, str]:
        """Identify the composition archetype.

        Args:
            picks: List of draft picks

        Returns:
            Tuple of (archetype_name, description, win_condition)
        """
        champion_names = [p.champion.name for p in picks]

        best_match = None
        best_score = 0

        for archetype, data in self.COMP_ARCHETYPES.items():
            archetype_champs = data["champions"]
            match_count = sum(1 for c in champion_names if c in archetype_champs)
            score = match_count / len(champion_names) if champion_names else 0

            if score > best_score:
                best_score = score
                best_match = archetype

        if best_match and best_score > 0.3:
            data = self.COMP_ARCHETYPES[best_match]
            return best_match, data["description"], data["win_condition"]

        return "standard", "Balanced composition", "Play to team's strengths"

    def get_synergy_recommendations(
        self,
        current_picks: list[DraftPick],
        available_champions: list[ChampionInfo],
        role: Optional[Role] = None,
    ) -> list[tuple[ChampionInfo, float, list[str]]]:
        """Get champion recommendations based on synergy.

        Args:
            current_picks: Current team picks
            available_champions: Available champions to pick
            role: Optional role filter

        Returns:
            List of (champion, synergy_score, reasons) tuples
        """
        recommendations = []
        current_names = [p.champion.name for p in current_picks]

        for champ in available_champions:
            if role and role not in champ.roles:
                continue

            # Calculate synergy with current picks
            total_synergy = 0.0
            reasons = []

            for current_name in current_names:
                pair_synergy = self._get_pair_synergy(champ.name, current_name)
                if pair_synergy > 0.5:
                    reasons.append(f"Strong synergy with {current_name}")
                    total_synergy += pair_synergy

            avg_synergy = total_synergy / len(current_names) if current_names else 0
            recommendations.append((champ, avg_synergy, reasons))

        # Sort by synergy score
        recommendations.sort(key=lambda x: x[1], reverse=True)
        return recommendations[:10]

    def analyze_composition_strengths(
        self,
        picks: list[DraftPick],
    ) -> dict[str, list[str]]:
        """Analyze composition strengths and weaknesses.

        Args:
            picks: Team picks

        Returns:
            Dict with 'strengths' and 'weaknesses' lists
        """
        champion_names = [p.champion.name for p in picks]

        strengths = []
        weaknesses = []

        # Check for engage
        engage_champs = ["Malphite", "Sejuani", "Leona", "Nautilus", "Ornn", "Rakan"]
        has_engage = any(c in engage_champs for c in champion_names)
        if has_engage:
            strengths.append("Has reliable engage")
        else:
            weaknesses.append("Lacks hard engage")

        # Check for disengage/peel
        peel_champs = ["Lulu", "Janna", "Braum", "Gragas", "Thresh"]
        has_peel = any(c in peel_champs for c in champion_names)
        if has_peel:
            strengths.append("Has peel for carries")
        else:
            weaknesses.append("Limited peel options")

        # Check damage type balance
        ap_heavy = ["Syndra", "Orianna", "Azir", "Viktor", "Ryze", "Cassiopeia"]
        ad_heavy = ["Jayce", "Zed", "Talon", "Lucian", "Draven"]

        ap_count = sum(1 for c in champion_names if c in ap_heavy)
        ad_count = sum(1 for c in champion_names if c in ad_heavy)

        if ap_count >= 3:
            weaknesses.append("AP-heavy, vulnerable to MR stacking")
        elif ad_count >= 3:
            weaknesses.append("AD-heavy, vulnerable to armor stacking")
        else:
            strengths.append("Balanced damage types")

        # Check for scaling
        scaling_champs = ["Kayle", "Kassadin", "Vayne", "Kog'Maw", "Azir", "Jinx"]
        early_champs = ["Renekton", "Lee Sin", "Draven", "Lucian", "Elise"]

        scaling_count = sum(1 for c in champion_names if c in scaling_champs)
        early_count = sum(1 for c in champion_names if c in early_champs)

        if scaling_count >= 2:
            strengths.append("Strong late game scaling")
            weaknesses.append("Weaker early game")
        elif early_count >= 2:
            strengths.append("Strong early game pressure")
            weaknesses.append("May fall off late game")

        return {"strengths": strengths, "weaknesses": weaknesses}

    def get_team_identity(
        self,
        picks: list[DraftPick],
    ) -> str:
        """Get a description of the team's identity/playstyle.

        Args:
            picks: Team picks

        Returns:
            Team identity description
        """
        comp_type, description, _ = self.identify_composition_type(picks)
        analysis = self.analyze_composition_strengths(picks)

        identity_parts = [description]

        if "Strong late game scaling" in analysis["strengths"]:
            identity_parts.append("with scaling focus")
        elif "Strong early game pressure" in analysis["strengths"]:
            identity_parts.append("with early game focus")

        return " ".join(identity_parts)
