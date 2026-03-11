"""Counter engine for matchup analysis."""

from typing import Optional
from app.models.schemas import (
    Role,
    ChampionInfo,
    DraftPick,
)


class CounterEngine:
    """Analyzes champion matchups and counter-picks."""

    # Counter relationships (champion -> list of counters with effectiveness)
    COUNTER_DATA: dict[str, list[tuple[str, float]]] = {
        # Top lane counters
        "Aatrox": [("Fiora", 0.7), ("Irelia", 0.6), ("Riven", 0.55), ("Vayne", 0.65)],
        "K'Sante": [("Vayne", 0.65), ("Fiora", 0.6), ("Darius", 0.55), ("Mordekaiser", 0.55)],
        "Renekton": [("Quinn", 0.7), ("Vayne", 0.65), ("Kennen", 0.55), ("Gnar", 0.5)],
        "Jax": [("Malphite", 0.65), ("Poppy", 0.6), ("Teemo", 0.55), ("Kennen", 0.55)],
        "Ornn": [("Fiora", 0.7), ("Vayne", 0.65), ("Mordekaiser", 0.55), ("Trundle", 0.6)],
        "Gnar": [("Irelia", 0.65), ("Camille", 0.6), ("Aatrox", 0.55), ("Jax", 0.55)],
        "Fiora": [("Malphite", 0.6), ("Kennen", 0.55), ("Quinn", 0.55), ("Vayne", 0.5)],
        "Camille": [("Jax", 0.65), ("Renekton", 0.6), ("Darius", 0.55), ("Poppy", 0.6)],
        "Jayce": [("Irelia", 0.65), ("Camille", 0.6), ("Wukong", 0.55)],
        "Kennen": [("Irelia", 0.65), ("Yasuo", 0.6), ("Sylas", 0.6)],
        "Shen": [("Mordekaiser", 0.65), ("Darius", 0.6), ("Illaoi", 0.6)],
        "Gangplank": [("Irelia", 0.7), ("Camille", 0.6), ("Lucian", 0.55)],
        "Gwen": [("Mordekaiser", 0.6), ("Sett", 0.55), ("Warwick", 0.55)],
        "Malphite": [("Sylas", 0.65), ("Mordekaiser", 0.6), ("Darius", 0.55)],
        "Darius": [("Vayne", 0.7), ("Quinn", 0.65), ("Kennen", 0.6), ("Kayle", 0.55)],
        "Mordekaiser": [("Fiora", 0.65), ("Vayne", 0.6), ("Olaf", 0.6)],
        "Sett": [("Gangplank", 0.6), ("Vayne", 0.65), ("Quinn", 0.55)],

        # Jungle counters
        "Lee Sin": [("Rammus", 0.65), ("Shyvana", 0.6), ("Warwick", 0.55), ("Poppy", 0.55)],
        "Vi": [("Morgana", 0.7), ("Elise", 0.6), ("Gragas", 0.55), ("Poppy", 0.55)],
        "Viego": [("Rammus", 0.65), ("Trundle", 0.6), ("Lee Sin", 0.55), ("Warwick", 0.55)],
        "Sejuani": [("Olaf", 0.7), ("Trundle", 0.65), ("Dr. Mundo", 0.55), ("Mordekaiser", 0.55)],
        "Maokai": [("Olaf", 0.65), ("Trundle", 0.6), ("Morgana", 0.55), ("Ivern", 0.5)],
        "Nocturne": [("Lee Sin", 0.6), ("Elise", 0.55), ("Kindred", 0.55)],
        "Xin Zhao": [("Rammus", 0.65), ("Poppy", 0.6), ("Trundle", 0.55)],
        "Nidalee": [("Elise", 0.6), ("Lee Sin", 0.55), ("Hecarim", 0.55)],
        "Graves": [("Rammus", 0.65), ("Lee Sin", 0.55), ("Elise", 0.55)],
        "Kindred": [("Rammus", 0.6), ("Nocturne", 0.55), ("Kha'Zix", 0.55)],
        "Hecarim": [("Olaf", 0.65), ("Trundle", 0.6), ("Poppy", 0.55)],
        "Kha'Zix": [("Rammus", 0.65), ("Elise", 0.55), ("Lee Sin", 0.55)],
        "Wukong": [("Lee Sin", 0.6), ("Elise", 0.55), ("Trundle", 0.55)],
        "Taliyah": [("Nocturne", 0.65), ("Lee Sin", 0.55), ("Kha'Zix", 0.55)],
        "Elise": [("Rammus", 0.6), ("Nocturne", 0.55), ("Diana", 0.55)],
        "Jarvan IV": [("Lee Sin", 0.6), ("Elise", 0.55), ("Poppy", 0.55)],

        # Mid lane counters
        "Azir": [("Xerath", 0.65), ("Syndra", 0.6), ("Kassadin", 0.7), ("Zed", 0.55)],
        "Ahri": [("Zed", 0.6), ("Yasuo", 0.55), ("Kassadin", 0.6), ("Annie", 0.55)],
        "Syndra": [("Fizz", 0.7), ("Zed", 0.65), ("Yasuo", 0.55), ("Kassadin", 0.55)],
        "Orianna": [("Zed", 0.65), ("Fizz", 0.6), ("LeBlanc", 0.55), ("Kassadin", 0.55)],
        "Corki": [("Kassadin", 0.65), ("Sylas", 0.6), ("Zed", 0.55)],
        "LeBlanc": [("Galio", 0.7), ("Malzahar", 0.6), ("Lissandra", 0.55)],
        "Viktor": [("Fizz", 0.65), ("Zed", 0.6), ("LeBlanc", 0.55), ("Kassadin", 0.55)],
        "Zed": [("Lissandra", 0.65), ("Galio", 0.6), ("Malzahar", 0.6)],
        "Sylas": [("Cassiopeia", 0.6), ("Syndra", 0.55), ("Zed", 0.55)],
        "Kassadin": [("Zed", 0.65), ("Lucian", 0.6), ("Pantheon", 0.6), ("Talon", 0.55)],
        "Neeko": [("Fizz", 0.6), ("Zed", 0.55), ("LeBlanc", 0.55)],
        "Twisted Fate": [("Fizz", 0.7), ("Zed", 0.65), ("Kassadin", 0.55)],
        "Ryze": [("Cassiopeia", 0.6), ("Syndra", 0.55), ("Lucian", 0.55)],
        "Cassiopeia": [("Fizz", 0.65), ("Zed", 0.6), ("LeBlanc", 0.55)],
        "Lissandra": [("Cassiopeia", 0.6), ("Syndra", 0.55), ("Orianna", 0.5)],
        "Galio": [("Cassiopeia", 0.6), ("Anivia", 0.55), ("Ryze", 0.55)],
        "Yasuo": [("Renekton", 0.7), ("Malphite", 0.65), ("Pantheon", 0.6)],
        "Yone": [("Renekton", 0.65), ("Pantheon", 0.6), ("Akali", 0.55)],
        "Zoe": [("Fizz", 0.65), ("Zed", 0.6), ("Yasuo", 0.55)],
        "Akali": [("Galio", 0.65), ("Malzahar", 0.6), ("Lissandra", 0.55)],

        # ADC counters
        "Kai'Sa": [("Draven", 0.6), ("Caitlyn", 0.55), ("Miss Fortune", 0.55)],
        "Varus": [("Samira", 0.65), ("Draven", 0.6), ("Lucian", 0.55)],
        "Jinx": [("Draven", 0.7), ("Lucian", 0.6), ("Caitlyn", 0.55)],
        "Aphelios": [("Draven", 0.65), ("Miss Fortune", 0.6), ("Caitlyn", 0.55)],
        "Xayah": [("Draven", 0.6), ("Caitlyn", 0.55), ("Miss Fortune", 0.55)],
        "Ezreal": [("Draven", 0.65), ("Lucian", 0.6), ("Caitlyn", 0.55)],
        "Caitlyn": [("Samira", 0.6), ("Draven", 0.55), ("Lucian", 0.55)],
        "Miss Fortune": [("Draven", 0.6), ("Lucian", 0.55), ("Samira", 0.55)],
        "Lucian": [("Draven", 0.6), ("Caitlyn", 0.55), ("Varus", 0.5)],
        "Draven": [("Caitlyn", 0.55), ("Ashe", 0.55), ("Jhin", 0.5)],
        "Ashe": [("Draven", 0.65), ("Samira", 0.6), ("Lucian", 0.55)],
        "Sivir": [("Draven", 0.6), ("Caitlyn", 0.55), ("Miss Fortune", 0.55)],
        "Samira": [("Caitlyn", 0.6), ("Ashe", 0.55), ("Varus", 0.55)],
        "Jhin": [("Samira", 0.6), ("Draven", 0.55), ("Lucian", 0.55)],
        "Zeri": [("Draven", 0.65), ("Caitlyn", 0.55), ("Lucian", 0.55)],
        "Kalista": [("Miss Fortune", 0.6), ("Draven", 0.55), ("Caitlyn", 0.55)],
        "Tristana": [("Draven", 0.6), ("Lucian", 0.55), ("Caitlyn", 0.55)],

        # Support counters
        "Nautilus": [("Morgana", 0.75), ("Braum", 0.6), ("Alistar", 0.55), ("Tahm Kench", 0.55)],
        "Thresh": [("Morgana", 0.7), ("Braum", 0.55), ("Alistar", 0.55), ("Leona", 0.5)],
        "Rakan": [("Morgana", 0.7), ("Alistar", 0.6), ("Leona", 0.55)],
        "Lulu": [("Nautilus", 0.65), ("Leona", 0.6), ("Zyra", 0.55)],
        "Leona": [("Morgana", 0.7), ("Braum", 0.55), ("Alistar", 0.55)],
        "Morgana": [("Zyra", 0.55), ("Karma", 0.55), ("Lulu", 0.5)],
        "Alistar": [("Morgana", 0.6), ("Janna", 0.55), ("Zyra", 0.55)],
        "Braum": [("Zyra", 0.6), ("Karma", 0.55), ("Lulu", 0.55)],
        "Karma": [("Nautilus", 0.6), ("Leona", 0.55), ("Alistar", 0.55)],
        "Janna": [("Leona", 0.6), ("Nautilus", 0.55), ("Alistar", 0.55)],
        "Tahm Kench": [("Zyra", 0.6), ("Karma", 0.55), ("Morgana", 0.5)],
        "Rell": [("Morgana", 0.65), ("Braum", 0.55), ("Alistar", 0.55)],
        "Blitzcrank": [("Morgana", 0.75), ("Sivir", 0.6), ("Ezreal", 0.55)],
        "Pyke": [("Nautilus", 0.6), ("Leona", 0.55), ("Alistar", 0.55)],
        "Renata Glasc": [("Nautilus", 0.6), ("Leona", 0.55), ("Thresh", 0.55)],
        "Milio": [("Nautilus", 0.65), ("Leona", 0.6), ("Thresh", 0.55)],
        "Nami": [("Nautilus", 0.6), ("Leona", 0.55), ("Blitzcrank", 0.55)],
        "Senna": [("Nautilus", 0.65), ("Leona", 0.6), ("Blitzcrank", 0.55)],
    }

    # Soft counter relationships (less severe)
    SOFT_COUNTERS: dict[str, list[str]] = {
        "Assassins": ["Lulu", "Exhaust carriers", "Zhonyas builders"],
        "Tanks": ["Vayne", "Kog'Maw", "Fiora", "%HP damage"],
        "Poke comps": ["Hard engage", "Sustain", "Flankers"],
        "Split pushers": ["Globals", "Strong 4v4", "Hard CC"],
    }

    def get_counters(
        self,
        champion_name: str,
        role: Optional[Role] = None,
    ) -> list[tuple[str, float]]:
        """Get counter picks for a champion.

        Args:
            champion_name: Champion to counter
            role: Optional role filter

        Returns:
            List of (counter_name, effectiveness) tuples
        """
        counters = self.COUNTER_DATA.get(champion_name, [])

        # Would filter by role in production with full data
        return counters

    def get_countered_by(
        self,
        champion_name: str,
    ) -> list[tuple[str, float]]:
        """Get champions that counter this champion.

        Args:
            champion_name: Champion name

        Returns:
            List of (champion_name, effectiveness) tuples
        """
        countered_by = []

        for champ, counters in self.COUNTER_DATA.items():
            for counter_name, effectiveness in counters:
                if counter_name == champion_name:
                    countered_by.append((champ, effectiveness))

        return countered_by

    def calculate_matchup_score(
        self,
        our_picks: list[DraftPick],
        enemy_picks: list[DraftPick],
    ) -> float:
        """Calculate overall matchup advantage.

        Args:
            our_picks: Our team's picks
            enemy_picks: Enemy team's picks

        Returns:
            Matchup score from 0 to 1 (0.5 = even)
        """
        if not our_picks or not enemy_picks:
            return 0.5

        our_names = [p.champion.name for p in our_picks]
        enemy_names = [p.champion.name for p in enemy_picks]

        total_advantage = 0.0
        comparisons = 0

        # Check each of our picks against enemies
        for our_champ in our_names:
            our_counters = [c[0] for c in self.COUNTER_DATA.get(our_champ, [])]

            for enemy_champ in enemy_names:
                enemy_counters = self.COUNTER_DATA.get(enemy_champ, [])

                # Check if we counter them
                for counter, effectiveness in enemy_counters:
                    if counter == our_champ:
                        total_advantage += effectiveness
                        break

                # Check if they counter us
                if enemy_champ in our_counters:
                    for counter, effectiveness in self.COUNTER_DATA.get(our_champ, []):
                        if counter == enemy_champ:
                            total_advantage -= effectiveness
                            break

                comparisons += 1

        if comparisons == 0:
            return 0.5

        # Normalize to 0-1
        avg_advantage = total_advantage / comparisons
        return 0.5 + (avg_advantage / 2)

    def get_counter_recommendations(
        self,
        enemy_picks: list[DraftPick],
        available_champions: list[ChampionInfo],
        role: Optional[Role] = None,
    ) -> list[tuple[ChampionInfo, float, list[str]]]:
        """Get counter-pick recommendations.

        Args:
            enemy_picks: Enemy team picks
            available_champions: Available champions
            role: Optional role filter

        Returns:
            List of (champion, counter_score, reasons) tuples
        """
        recommendations = []
        enemy_names = [p.champion.name for p in enemy_picks]

        for champ in available_champions:
            if role and role not in champ.roles:
                continue

            total_counter = 0.0
            reasons = []

            for enemy_name in enemy_names:
                counters = self.COUNTER_DATA.get(enemy_name, [])
                for counter_name, effectiveness in counters:
                    if counter_name == champ.name:
                        total_counter += effectiveness
                        reasons.append(f"Counters {enemy_name} ({effectiveness:.0%})")
                        break

            avg_counter = total_counter / len(enemy_names) if enemy_names else 0
            recommendations.append((champ, avg_counter, reasons))

        recommendations.sort(key=lambda x: x[1], reverse=True)
        return recommendations[:10]

    def get_ban_recommendations(
        self,
        our_planned_picks: list[str],
        enemy_tendencies: list[str],
    ) -> list[tuple[str, str]]:
        """Get ban recommendations based on our comp vulnerability.

        Args:
            our_planned_picks: Champions we might pick
            enemy_tendencies: Enemy's favorite champions

        Returns:
            List of (champion_name, reason) for bans
        """
        ban_recommendations = []

        # Ban champions that counter our picks
        for our_pick in our_planned_picks:
            counters = self.COUNTER_DATA.get(our_pick, [])
            for counter, effectiveness in counters:
                if effectiveness >= 0.6:
                    ban_recommendations.append(
                        (counter, f"Counters our {our_pick} ({effectiveness:.0%})")
                    )

        # Ban enemy comfort picks
        for enemy_champ in enemy_tendencies[:3]:
            if enemy_champ not in [b[0] for b in ban_recommendations]:
                ban_recommendations.append(
                    (enemy_champ, "Enemy comfort pick")
                )

        return ban_recommendations[:5]

    def analyze_lane_matchups(
        self,
        our_picks: list[DraftPick],
        enemy_picks: list[DraftPick],
    ) -> dict[Role, dict]:
        """Analyze individual lane matchups.

        Args:
            our_picks: Our picks
            enemy_picks: Enemy picks

        Returns:
            Dict of role -> matchup analysis
        """
        matchups = {}

        for our_pick in our_picks:
            if not our_pick.role:
                continue

            # Find enemy in same role
            enemy_pick = None
            for ep in enemy_picks:
                if ep.role == our_pick.role:
                    enemy_pick = ep
                    break

            if enemy_pick:
                advantage = self._calculate_lane_advantage(
                    our_pick.champion.name,
                    enemy_pick.champion.name
                )

                matchups[our_pick.role] = {
                    "our_champion": our_pick.champion.name,
                    "enemy_champion": enemy_pick.champion.name,
                    "advantage": advantage,
                    "assessment": self._get_matchup_assessment(advantage),
                }

        return matchups

    def _calculate_lane_advantage(
        self,
        our_champ: str,
        enemy_champ: str,
    ) -> float:
        """Calculate lane advantage for a specific matchup."""
        # Check if we counter them
        enemy_counters = self.COUNTER_DATA.get(enemy_champ, [])
        for counter, effectiveness in enemy_counters:
            if counter == our_champ:
                return 0.5 + effectiveness / 2

        # Check if they counter us
        our_counters = self.COUNTER_DATA.get(our_champ, [])
        for counter, effectiveness in our_counters:
            if counter == enemy_champ:
                return 0.5 - effectiveness / 2

        return 0.5  # Even matchup

    def _get_matchup_assessment(self, advantage: float) -> str:
        """Get text assessment for matchup advantage."""
        if advantage >= 0.7:
            return "Strong advantage"
        elif advantage >= 0.55:
            return "Slight advantage"
        elif advantage >= 0.45:
            return "Even matchup"
        elif advantage >= 0.3:
            return "Slight disadvantage"
        else:
            return "Strong disadvantage"
