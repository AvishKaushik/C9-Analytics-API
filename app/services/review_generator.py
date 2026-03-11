"""Review generator service for creating macro review agendas."""

from typing import Any, Optional


from shared.grid_client import GridClient
from shared.grid_client.lol import LoLMatchQueries
from shared.grid_client.valorant import ValorantMatchQueries
from shared.utils.llm import generate_insight

from app.models.schemas import (
    GameType,
    ReviewAgenda,
    ReviewAgendaItem,
)


class ReviewGenerator:
    """Generates structured macro review agendas for matches."""

    def __init__(self, grid_client: Optional[GridClient] = None):
        self.grid_client = grid_client or GridClient()

    async def generate_review(
        self,
        match_id: str,
        game: GameType,
        game_number: int = 1,
        team_id: Optional[str] = None,
        review_duration_minutes: int = 30,
    ) -> ReviewAgenda:
        """Generate a macro review agenda for a match.

        Args:
            match_id: Match ID
            game: Game type (lol or valorant)
            game_number: Game number in series
            team_id: Optional team perspective
            review_duration_minutes: Target duration for review

        Returns:
            ReviewAgenda with structured review items
        """
        # Fetch match data
        match_data = await self._fetch_match_data(match_id, game)

        if not match_data:
            return self._empty_agenda(match_id, game_number)

        # Extract the specific game
        games = match_data.get("games", [])
        target_game = None
        for g in games:
            if g.get("sequenceNumber") == game_number:
                target_game = g
                break

        if not target_game:
            target_game = games[0] if games else {}

        # Generate agenda based on game type
        if game == GameType.LOL:
            return await self._generate_lol_review(
                match_id, target_game, team_id, review_duration_minutes
            )
        else:
            return await self._generate_valorant_review(
                match_id, target_game, team_id, review_duration_minutes
            )

    async def _fetch_match_data(
        self,
        match_id: str,
        game: GameType,
    ) -> dict[str, Any]:
        """Fetch match data from GRID API."""
        if game == GameType.LOL:
            queries = LoLMatchQueries(self.grid_client)
        else:
            queries = ValorantMatchQueries(self.grid_client)

        result = await queries.get_series_state(match_id)
        state = result.get("seriesState", {})

        # Transform to expected format
        return state

    async def _generate_lol_review(
        self,
        match_id: str,
        game_data: dict[str, Any],
        team_id: Optional[str],
        duration_minutes: int,
    ) -> ReviewAgenda:
        """Generate LoL-specific review agenda."""
        key_moments = []
        team_observations = []
        individual_notes: dict[str, list[str]] = {}

        winner_name = game_data.get("winner", {}).get("name", "Unknown")
        game_duration = game_data.get("duration", 0)

        # Analyze events for key moments
        events = game_data.get("events", [])
        objective_fights = self._extract_objective_fights(events, "lol")
        teamfights = self._extract_teamfights(events, "lol")

        # Add draft review item
        key_moments.append(ReviewAgendaItem(
            timestamp="Pre-game",
            title="Draft Analysis",
            description="Review draft decisions, win conditions, and composition strengths",
            category="objective",
            priority="important",
            discussion_points=[
                "Was the draft executed according to plan?",
                "What were our win conditions?",
                "Did we correctly identify their composition's strengths?",
            ],
            suggested_duration_minutes=5,
        ))

        # Add early game review
        key_moments.append(ReviewAgendaItem(
            timestamp="0:00 - 14:00",
            title="Early Game & Laning Phase",
            description="Review lane states, jungle pathing, and first objectives",
            category="objective",
            priority="critical",
            discussion_points=[
                "Did we achieve expected lane states?",
                "Was jungle tracking accurate?",
                "First objective decisions",
            ],
            suggested_duration_minutes=7,
        ))

        # Add objective fights
        for i, fight in enumerate(objective_fights[:3]):
            key_moments.append(ReviewAgendaItem(
                timestamp=fight.get("timestamp", ""),
                title=f"Objective Fight: {fight.get('objective', 'Unknown')}",
                description=fight.get("description", "Major objective contest"),
                category="objective",
                priority="critical" if i == 0 else "important",
                players_involved=fight.get("players", []),
                discussion_points=[
                    "Was the fight setup correct?",
                    "Did we have proper vision control?",
                    "Were cooldowns tracked correctly?",
                ],
                suggested_duration_minutes=5,
            ))

        # Add teamfight review
        for i, tf in enumerate(teamfights[:2]):
            key_moments.append(ReviewAgendaItem(
                timestamp=tf.get("timestamp", ""),
                title=f"Teamfight #{i+1}",
                description=tf.get("description", "Major teamfight"),
                category="teamfight",
                priority="important",
                players_involved=tf.get("players", []),
                discussion_points=[
                    "Was engage timing correct?",
                    "Did carries position properly?",
                    "Were abilities used correctly?",
                ],
                suggested_duration_minutes=4,
            ))

        # Analyze player performances
        for team in game_data.get("teams", []):
            for player in team.get("players", []):
                player_name = player.get("name", "Unknown")
                individual_notes[player_name] = []

                deaths = player.get("deaths", 0)
                kills = player.get("kills", 0)

                if deaths >= 5:
                    individual_notes[player_name].append(
                        f"High death count ({deaths}) - review positioning"
                    )
                if player.get("visionScore", 0) < 20:
                    individual_notes[player_name].append(
                        "Vision score below expectations - review warding patterns"
                    )

        # Team-level observations
        team_observations.extend([
            f"Game duration: {game_duration // 60}:{game_duration % 60:02d}",
            f"Match outcome: {winner_name} victory",
            "Review macro rotations and objective priority",
        ])

        # Priority topics based on outcome
        priority_topics = [
            "Win condition execution",
            "Objective decision making",
            "Vision control and tracking",
        ]

        return ReviewAgenda(
            match_id=match_id,
            game_number=game_data.get("sequenceNumber", 1),
            match_outcome=f"{winner_name} victory",
            total_duration_minutes=duration_minutes,
            executive_summary=self._generate_executive_summary(game_data, "lol"),
            key_moments=key_moments,
            team_level_observations=team_observations,
            individual_notes=individual_notes,
            priority_topics=priority_topics,
        )

    async def _generate_valorant_review(
        self,
        match_id: str,
        game_data: dict[str, Any],
        team_id: Optional[str],
        duration_minutes: int,
    ) -> ReviewAgenda:
        """Generate VALORANT-specific review agenda."""
        key_moments = []
        team_observations = []
        individual_notes: dict[str, list[str]] = {}

        # Extract winner from team scores, or kills if scores unavailable
        teams = game_data.get("teams", [])
        winner_name = "Unknown"
        if teams:
            # Try score first
            sorted_teams = sorted(teams, key=lambda t: t.get("score", 0), reverse=True)
            if sorted_teams and sorted_teams[0].get("score", 0) > 0:
                winner_name = sorted_teams[0].get("name", "Unknown")
            else:
                # Fallback to total kills
                team_kills = []
                for t in teams:
                    total_kills = sum(p.get("kills", 0) for p in t.get("players", []))
                    team_kills.append((t.get("name", "Unknown"), total_kills))
                if team_kills:
                    team_kills.sort(key=lambda x: x[1], reverse=True)
                    winner_name = team_kills[0][0]

        map_name = game_data.get("map", {}).get("name", "Unknown")
        rounds = game_data.get("segments", [])  # Rounds are in segments

        # Add pistol round review
        key_moments.append(ReviewAgendaItem(
            timestamp="Pistol 1 (Round 1)",
            title="First Pistol Round",
            description="Review pistol round execution and economy setup",
            category="economy",
            priority="critical",
            discussion_points=[
                "Was the buy correct?",
                "Did we execute the strategy properly?",
                "Post-pistol economy decision",
            ],
            suggested_duration_minutes=4,
        ))

        # Add key round reviews
        critical_rounds = self._identify_critical_rounds(rounds)
        for round_info in critical_rounds[:4]:
            key_moments.append(ReviewAgendaItem(
                timestamp=f"Round {round_info.get('number', '?')}",
                title=round_info.get("title", "Key Round"),
                description=round_info.get("description", "Critical round decision"),
                category=round_info.get("category", "execution"),
                priority="critical",
                discussion_points=round_info.get("discussion_points", []),
                suggested_duration_minutes=3,
            ))

        # Second pistol
        key_moments.append(ReviewAgendaItem(
            timestamp="Pistol 2 (Round 13)",
            title="Second Pistol Round",
            description="Review second half pistol and adaptation",
            category="economy",
            priority="important",
            discussion_points=[
                "Did we adapt to their defense/attack?",
                "Economy management going into second half",
            ],
            suggested_duration_minutes=3,
        ))

        # Add economy overview
        key_moments.append(ReviewAgendaItem(
            timestamp="Full Game",
            title="Economy Management",
            description="Review eco/force/full-buy decisions throughout the match",
            category="economy",
            priority="important",
            discussion_points=[
                "Were force buys well-timed?",
                "Did we lose rounds due to poor eco?",
                "Weapon and utility purchases",
            ],
            suggested_duration_minutes=4,
        ))

        # Analyze player performances
        for team in game_data.get("teams", []):
            for player in team.get("players", []):
                player_name = player.get("name", "Unknown")
                individual_notes[player_name] = []

                kills = player.get("kills", 0)
                deaths = player.get("deaths", 0)
                assists = player.get("killAssistsGiven", 0)

                # Calculate KDA
                kda = (kills + assists) / max(deaths, 1)

                if kda < 1.0:
                    individual_notes[player_name].append(
                        f"Low KDA ({kda:.2f}) - review positioning and trading"
                    )
                if deaths > kills + 5:
                    individual_notes[player_name].append(
                        f"High death count ({deaths}K/{kills}D) - review aggression timing"
                    )

        # Team observations - extract from game teams
        game_teams = game_data.get("teams", [])
        total_rounds = 0

        for team in game_teams:
            team_score = team.get("score", 0)
            team_name = team.get("name", "Unknown")

            # Count kills/deaths for the team as alternative stats
            team_kills = sum(p.get("kills", 0) for p in team.get("players", []))
            team_deaths = sum(p.get("deaths", 0) for p in team.get("players", []))

            if team_score > 0:
                team_observations.append(f"{team_name}: {team_score} rounds won")
            else:
                team_observations.append(f"{team_name}: {team_kills}K / {team_deaths}D")

            total_rounds += team_score

        # If no scores, estimate from player stats
        if total_rounds == 0 and game_teams:
            total_kills = sum(
                sum(p.get("kills", 0) for p in t.get("players", []))
                for t in game_teams
            )
            # Rough estimate: ~25 kills per round average in pro play
            total_rounds = max(1, total_kills // 5)

        team_observations.extend([
            f"Map: {map_name}",
            f"Total rounds: {total_rounds}",
        ])

        priority_topics = [
            "Round conversion and clutches",
            "Utility usage and timing",
            "Site executes and retakes",
        ]

        # Calculate final score string
        score_str = ""
        if len(teams) >= 2:
            s1, s2 = teams[0].get("score", 0), teams[1].get("score", 0)
            if s1 > 0 or s2 > 0:
                score_str = f" ({s1}-{s2})"

        return ReviewAgenda(
            match_id=match_id,
            game_number=game_data.get("sequenceNumber", 1),
            match_outcome=f"{winner_name} victory on {map_name}{score_str}",
            total_duration_minutes=duration_minutes,
            executive_summary=self._generate_executive_summary(game_data, "valorant"),
            key_moments=key_moments,
            team_level_observations=team_observations,
            individual_notes=individual_notes,
            priority_topics=priority_topics,
        )

    def _extract_objective_fights(
        self,
        events: list[dict[str, Any]],
        game: str,
    ) -> list[dict[str, Any]]:
        """Extract objective fights from game events."""
        fights = []

        for event in events:
            event_type = event.get("type", "")
            if event_type in ["DRAGON_KILL", "BARON_KILL", "HERALD_KILL"]:
                fights.append({
                    "timestamp": self._format_timestamp(event.get("timestamp", 0)),
                    "objective": event_type.replace("_KILL", "").title(),
                    "description": f"{event_type.replace('_KILL', '').title()} secured",
                    "players": [],
                })

        return fights

    def _extract_teamfights(
        self,
        events: list[dict[str, Any]],
        game: str,
    ) -> list[dict[str, Any]]:
        """Extract major teamfights from game events."""
        # Simplified teamfight detection
        teamfights = []
        kill_events = [e for e in events if e.get("type") == "CHAMPION_KILL"]

        # Group kills by timestamp proximity (within 10 seconds)
        if not kill_events:
            return teamfights

        current_fight: list[dict] = []
        for event in kill_events:
            timestamp = event.get("timestamp", 0)
            if not current_fight:
                current_fight = [event]
            elif timestamp - current_fight[-1].get("timestamp", 0) < 10000:
                current_fight.append(event)
            else:
                if len(current_fight) >= 3:
                    teamfights.append({
                        "timestamp": self._format_timestamp(current_fight[0].get("timestamp", 0)),
                        "description": f"Teamfight with {len(current_fight)} kills",
                        "players": [],
                    })
                current_fight = [event]

        return teamfights

    def _identify_critical_rounds(
        self,
        rounds: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Identify critical rounds for VALORANT review."""
        critical = []

        for r in rounds:
            round_num = r.get("number", 0)
            win_condition = r.get("winCondition", "")

            # Eco wins/losses
            economy = r.get("economy", [])
            if economy:
                # Check for force buy wins or full buy losses
                for team_economy in economy:
                    loadout_value = team_economy.get("loadoutValue", 0)
                    team_id = team_economy.get("team", {}).get("id")
                    won_round = r.get("winningTeam", {}).get("id") == team_id

                    # Eco/save round: < 5000 loadout value
                    if loadout_value < 5000 and won_round:
                        critical.append({
                            "number": round_num,
                            "title": f"Eco Win Round {round_num}",
                            "description": f"Won with low economy (${loadout_value})",
                            "category": "economy",
                            "discussion_points": [
                                "What made this eco round successful?",
                                "Can we replicate this setup?",
                                "Enemy mistakes to exploit",
                            ],
                        })
                    # Full buy loss: > 20000 loadout value
                    elif loadout_value > 20000 and not won_round:
                        critical.append({
                            "number": round_num,
                            "title": f"Full Buy Loss Round {round_num}",
                            "description": f"Lost with full economy (${loadout_value})",
                            "category": "economy",
                            "discussion_points": [
                                "What went wrong in this full buy?",
                                "Trade efficiency issues?",
                                "Utility usage and timing",
                            ],
                        })

            # Clutch rounds
            if "clutch" in str(r).lower():
                critical.append({
                    "number": round_num,
                    "title": f"Clutch Round {round_num}",
                    "description": "Clutch situation",
                    "category": "execution",
                    "discussion_points": [
                        "What information did we have?",
                        "Was utility used correctly?",
                        "Positioning and timing",
                    ],
                })

            # Half-ending rounds (11, 12)
            if round_num in [11, 12, 23, 24]:
                critical.append({
                    "number": round_num,
                    "title": f"Critical Round {round_num}",
                    "description": "Half/game-deciding round",
                    "category": "execution",
                    "discussion_points": [
                        "Did we play for the score correctly?",
                        "Economy consideration for next half",
                    ],
                })

        return critical[:6]

    def _format_timestamp(self, ms: int) -> str:
        """Format milliseconds to MM:SS format."""
        seconds = ms // 1000
        minutes = seconds // 60
        secs = seconds % 60
        return f"{minutes}:{secs:02d}"

    def _generate_executive_summary(
        self,
        game_data: dict[str, Any],
        game: str,
    ) -> str:
        """Generate executive summary for the review."""
        teams = game_data.get("teams", [])

        # Find winner from scores, or from kills if scores unavailable
        winner = "Unknown"
        if teams:
            # Try score first
            sorted_teams = sorted(teams, key=lambda t: t.get("score", 0), reverse=True)
            if sorted_teams and sorted_teams[0].get("score", 0) > 0:
                winner = sorted_teams[0].get("name", "Unknown")
            else:
                # Fallback to total kills
                team_kills = []
                for t in teams:
                    total_kills = sum(p.get("kills", 0) for p in t.get("players", []))
                    team_kills.append((t.get("name", "Unknown"), total_kills))
                if team_kills:
                    team_kills.sort(key=lambda x: x[1], reverse=True)
                    winner = team_kills[0][0]

        if game == "lol":
            duration = game_data.get("duration", 0)
            if duration:
                return (
                    f"Match won by {winner} in {duration // 60}:{duration % 60:02d}. "
                    "Review focuses on key objective decisions and teamfight execution."
                )
            else:
                return (
                    f"Match won by {winner}. "
                    "Review focuses on key objective decisions and teamfight execution."
                )
        else:
            map_name = game_data.get("map", {}).get("name", "Unknown")
            score = ""
            if len(teams) >= 2:
                s1, s2 = teams[0].get("score", 0), teams[1].get("score", 0)
                if s1 > 0 or s2 > 0:
                    score = f"{s1}-{s2}"
                else:
                    # Show kills instead
                    k1 = sum(p.get("kills", 0) for p in teams[0].get("players", []))
                    k2 = sum(p.get("kills", 0) for p in teams[1].get("players", []))
                    score = f"{k1}K-{k2}K"
            return (
                f"Match on {map_name} won by {winner} ({score}). "
                "Review focuses on key rounds, economy decisions, and execution."
            )

    def _empty_agenda(self, match_id: str, game_number: int) -> ReviewAgenda:
        """Return empty agenda when no data available."""
        return ReviewAgenda(
            match_id=match_id,
            game_number=game_number,
            match_outcome="Unknown",
            total_duration_minutes=30,
            executive_summary="Unable to fetch match data. Please verify match ID.",
            key_moments=[],
            team_level_observations=["No data available"],
            individual_notes={},
            priority_topics=[],
        )
