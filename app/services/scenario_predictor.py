"""Scenario predictor service for what-if analysis."""

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


from shared.grid_client import GridClient
from shared.grid_client.lol import LoLMatchQueries
from shared.grid_client.valorant import ValorantMatchQueries
from shared.utils.llm import generate_insight, LLMClient

from app.models.schemas import (
    GameType,
    ScenarioPrediction,
)


class ScenarioPredictor:
    """Predicts outcomes for hypothetical game scenarios."""

    def __init__(
        self,
        grid_client: Optional[GridClient] = None,
        llm_client: Optional[LLMClient] = None,
    ):
        self.grid_client = grid_client or GridClient()
        self.llm_client = llm_client or LLMClient()

    async def predict_scenario(
        self,
        match_id: str,
        game: GameType,
        scenario_description: str,
        timestamp: Optional[str] = None,
        game_number: int = 1,
    ) -> tuple[str, ScenarioPrediction, list[ScenarioPrediction]]:
        """Predict outcome for a hypothetical scenario.

        Args:
            match_id: Match ID
            game: Game type
            scenario_description: Description of the alternative scenario
            timestamp: Optional game timestamp for context
            game_number: Game number in series

        Returns:
            Tuple of (original_outcome, main_prediction, alternative_scenarios)
        """
        # Fetch match data
        match_data = await self._fetch_match_data(match_id, game)

        if not match_data:
            return self._empty_prediction(scenario_description)

        # Extract game state at timestamp
        game_state = self._extract_game_state(match_data, game_number, timestamp, game)

        # Get original outcome
        original_outcome = self._get_original_outcome(match_data, game_number)

        # Generate prediction using LLM
        main_prediction = await self._generate_prediction(
            game_state, scenario_description, game
        )

        # Generate alternative scenarios
        alternatives = await self._generate_alternatives(
            game_state, scenario_description, game
        )

        return original_outcome, main_prediction, alternatives

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

        result = await queries.get_match_details(match_id)
        
        # GRID API returns {"series": {...}, "state": {...}}
        # We need to merge them into a usable structure
        series_data = result.get("series", {})
        state_data = result.get("state", {})
        
        # The actual game data (with teams, players, games) is in state
        # Merge series metadata with state data for complete context
        if state_data:
            # State has the games array with detailed stats
            return state_data
        elif series_data:
            # Fallback to series metadata if state is missing
            return series_data
        
        return {}

    def _extract_game_state(
        self,
        match_data: dict[str, Any],
        game_number: int,
        timestamp: Optional[str],
        game: GameType,
    ) -> dict[str, Any]:
        """Extract game state at a specific timestamp."""
        games = match_data.get("games", [])
        target_game = None

        for g in games:
            if g.get("sequenceNumber") == game_number:
                target_game = g
                break

        if not target_game:
            target_game = games[0] if games else {}

        state = {
            "game_number": game_number,
            "teams": target_game.get("teams", []),
            "timestamp": timestamp,
        }

        if game == GameType.LOL:
            state.update({
                "duration": target_game.get("duration", 0),
                "drafts": target_game.get("drafts", []),
            })
        else:
            state.update({
                "map": target_game.get("map", {}).get("name", "Unknown"),
                "rounds": target_game.get("rounds", []),
            })

        return state

    def _get_original_outcome(
        self,
        match_data: dict[str, Any],
        game_number: int,
    ) -> str:
        """Get the original match outcome."""
        games = match_data.get("games", [])

        for g in games:
            if g.get("sequenceNumber") == game_number:
                # Determine winner from team scores
                teams = g.get("teams", [])
                if len(teams) >= 2:
                    team1, team2 = teams[0], teams[1]
                    score1 = team1.get("score", 0)
                    score2 = team2.get("score", 0)
                    
                    if score1 > score2:
                        return f"{team1.get('name', 'Unknown')} victory ({score1}-{score2})"
                    elif score2 > score1:
                        return f"{team2.get('name', 'Unknown')} victory ({score2}-{score1})"
                    else:
                        return f"Tied game ({score1}-{score2})"
                
                return "Unknown outcome - no team data"

        # Fallback to first game if specified game number not found
        if games:
            teams = games[0].get("teams", [])
            if len(teams) >= 2:
                team1, team2 = teams[0], teams[1]
                score1 = team1.get("score", 0)
                score2 = team2.get("score", 0)
                
                if score1 > score2:
                    return f"{team1.get('name', 'Unknown')} victory ({score1}-{score2})"
                elif score2 > score1:
                    return f"{team2.get('name', 'Unknown')} victory ({score2}-{score1})"
                else:
                    return f"Tied game ({score1}-{score2})"

        return "Unknown outcome"

    async def _generate_prediction(
        self,
        game_state: dict[str, Any],
        scenario: str,
        game: GameType,
    ) -> ScenarioPrediction:
        """Generate prediction for the main scenario."""
        # Prepare context for LLM
        context = self._format_game_state(game_state, game)

        prompt = f"""
Analyze this {game.value.upper()} game state and predict the outcome of an alternative scenario.

Game State:
{context}

Alternative Scenario: {scenario}

Provide your analysis in the following EXACT format (use only these labels, provide numeric values where indicated):
SUCCESS_PROBABILITY: [number between 0 and 100, e.g. 65 for 65% chance]
CONFIDENCE: [high/medium/low]
KEY_FACTORS: [factor1, factor2, factor3]
RISKS: [risk1, risk2]
REWARDS: [reward1, reward2]
REASONING: [2-3 sentences explaining your analysis]

IMPORTANT: For SUCCESS_PROBABILITY, provide a realistic percentage. For most strategic alternatives in professional esports, probabilities should typically be between 35-75% unless the scenario is clearly very risky or very safe.
"""

        try:
            logger.info(f"Generating prediction for scenario: {scenario}")
            logger.debug(f"Game state context: {context[:500]}..." if len(context) > 500 else f"Game state context: {context}")
            response = await self.llm_client.generate(prompt)
            logger.info(f"LLM response received, length: {len(response)}")
            logger.debug(f"LLM response: {response[:500]}..." if len(response) > 500 else f"LLM response: {response}")
            return self._parse_prediction_response(response, scenario)
        except Exception as e:
            logger.error(f"LLM prediction failed: {type(e).__name__}: {e}")
            # Return a more informative prediction when LLM fails
            return ScenarioPrediction(
                scenario_description=scenario,
                success_probability=0.5,
                confidence="low",
                key_factors=[f"LLM service error: {type(e).__name__}"],
                risks=["Analysis could not be completed"],
                rewards=["Retry with valid API key or check LLM service"],
                historical_precedents=[],
                reasoning=f"LLM prediction failed: {str(e)}. Please ensure GROQ_API_KEY is set correctly.",
            )

    async def _generate_alternatives(
        self,
        game_state: dict[str, Any],
        original_scenario: str,
        game: GameType,
    ) -> list[ScenarioPrediction]:
        """Generate alternative scenario predictions."""
        context = self._format_game_state(game_state, game)

        prompt = f"""
Given this {game.value.upper()} game state:
{context}

And the proposed scenario: {original_scenario}

Suggest 2 alternative scenarios that could have occurred at this point.
For each alternative, provide in EXACT format:
SCENARIO: [brief description]
SUCCESS_PROBABILITY: [number 0-100, e.g. 55 for 55%]
KEY_FACTORS: [factor1, factor2, factor3]

Separate each alternative with a blank line. Provide realistic probabilities (typically 35-75%).
"""

        try:
            logger.info(f"Generating alternatives for scenario: {original_scenario}")
            response = await self.llm_client.generate(prompt)
            logger.info(f"Alternatives response received, length: {len(response)}")
            return self._parse_alternatives_response(response)
        except Exception as e:
            logger.error(f"LLM alternatives generation failed: {type(e).__name__}: {e}")
            return []

    def _format_game_state(
        self,
        game_state: dict[str, Any],
        game: GameType,
    ) -> str:
        """Format game state for LLM prompt."""
        lines = []

        teams = game_state.get("teams", [])
        for team in teams:
            team_name = team.get("name", "Unknown")
            lines.append(f"\n{team_name}:")

            if game == GameType.LOL:
                lines.append(f"  Score: {team.get('score', 0)}")
                players = team.get("players", [])
                for p in players:
                    lines.append(
                        f"  - {p.get('name')}: {p.get('champion', {}).get('name', '?')} "
                        f"({p.get('kills', 0)}/{p.get('deaths', 0)}/{p.get('assists', 0)})"
                    )
            else:
                lines.append(f"  Rounds Won: {team.get('roundsWon', 0)}")
                players = team.get("players", [])
                for p in players:
                    lines.append(
                        f"  - {p.get('name')}: {p.get('agent', {}).get('name', '?')} "
                        f"(ACS: {p.get('acs', 0):.0f})"
                    )

        if game_state.get("timestamp"):
            lines.append(f"\nTimestamp: {game_state['timestamp']}")

        if game == GameType.VALORANT and game_state.get("map"):
            lines.append(f"Map: {game_state['map']}")

        return "\n".join(lines)

    def _parse_prediction_response(
        self,
        response: str,
        scenario: str,
    ) -> ScenarioPrediction:
        """Parse LLM response into ScenarioPrediction."""
        lines = response.strip().split("\n")

        probability = 0.5
        confidence = "medium"
        key_factors = []
        risks = []
        rewards = []
        reasoning = ""

        for line in lines:
            line_lower = line.lower().strip()
            if "success_probability" in line_lower or ("probability" in line_lower and ":" in line):
                try:
                    # Extract only the value after the colon
                    value_part = line.split(":", 1)[-1].strip()
                    # Remove % sign and any non-numeric chars except dots
                    num_str = "".join(c for c in value_part if c.isdigit() or c == ".")
                    if num_str:
                        num = float(num_str)
                        # If value is > 1, treat as percentage (0-100 scale)
                        probability = num / 100 if num > 1 else num
                        logger.debug(f"Parsed probability: {num} -> {probability}")
                except (ValueError, IndexError) as e:
                    logger.warning(f"Failed to parse probability from line: {line}, error: {e}")
                    pass
            elif "confidence" in line_lower:
                if "high" in line_lower:
                    confidence = "high"
                elif "low" in line_lower:
                    confidence = "low"
            elif "key_factors" in line_lower:
                factors = line.split(":", 1)[-1].strip()
                key_factors = [f.strip() for f in factors.split(",") if f.strip()]
            elif "risks" in line_lower:
                risk_str = line.split(":", 1)[-1].strip()
                risks = [r.strip() for r in risk_str.split(",") if r.strip()]
            elif "rewards" in line_lower:
                reward_str = line.split(":", 1)[-1].strip()
                rewards = [r.strip() for r in reward_str.split(",") if r.strip()]
            elif "reasoning" in line_lower:
                reasoning = line.split(":", 1)[-1].strip()

        if not reasoning:
            reasoning = response[-500:] if len(response) > 500 else response

        return ScenarioPrediction(
            scenario_description=scenario,
            success_probability=min(max(probability, 0.0), 1.0),
            confidence=confidence,
            key_factors=key_factors or ["Game state analysis", "Historical patterns"],
            risks=risks or ["Execution uncertainty"],
            rewards=rewards or ["Potential advantage"],
            historical_precedents=[],
            reasoning=reasoning,
        )

    def _parse_alternatives_response(
        self,
        response: str,
    ) -> list[ScenarioPrediction]:
        """Parse LLM response into alternative predictions."""
        alternatives = []
        sections = response.split("\n\n")

        for section in sections[:2]:  # Max 2 alternatives
            if not section.strip():
                continue

            scenario = ""
            probability = 0.5
            factors = []

            for line in section.split("\n"):
                line_lower = line.lower().strip()
                if "scenario" in line_lower:
                    scenario = line.split(":", 1)[-1].strip()
                elif "probability" in line_lower and ":" in line:
                    try:
                        # Extract only the value after the colon
                        value_part = line.split(":", 1)[-1].strip()
                        num_str = "".join(c for c in value_part if c.isdigit() or c == ".")
                        if num_str:
                            num = float(num_str)
                            probability = num / 100 if num > 1 else num
                    except (ValueError, IndexError):
                        pass
                elif "factors" in line_lower:
                    factor_str = line.split(":", 1)[-1].strip()
                    factors = [f.strip() for f in factor_str.split(",") if f.strip()]

            if scenario:
                alternatives.append(ScenarioPrediction(
                    scenario_description=scenario,
                    success_probability=min(max(probability, 0.0), 1.0),
                    confidence="medium",
                    key_factors=factors or ["Alternative approach"],
                    risks=["Execution risk"],
                    rewards=["Different outcome"],
                    historical_precedents=[],
                    reasoning=f"Alternative scenario: {scenario}",
                ))

        return alternatives

    def _default_prediction(self, scenario: str) -> ScenarioPrediction:
        """Return default prediction when LLM fails."""
        return ScenarioPrediction(
            scenario_description=scenario,
            success_probability=0.5,
            confidence="low",
            key_factors=["Insufficient data for analysis"],
            risks=["Unknown execution factors"],
            rewards=["Potential outcome change"],
            historical_precedents=[],
            reasoning="Unable to generate detailed prediction. Based on general game theory, "
                     "alternative decisions carry inherent uncertainty.",
        )

    def _empty_prediction(
        self,
        scenario: str,
    ) -> tuple[str, ScenarioPrediction, list[ScenarioPrediction]]:
        """Return empty prediction when no match data available."""
        return (
            "Unknown - match data not found",
            ScenarioPrediction(
                scenario_description=scenario,
                success_probability=0.5,
                confidence="low",
                key_factors=["No match data available"],
                risks=["Cannot assess without game context"],
                rewards=["Unknown"],
                historical_precedents=[],
                reasoning="Unable to fetch match data. Please verify the match ID is correct.",
            ),
            [],
        )
