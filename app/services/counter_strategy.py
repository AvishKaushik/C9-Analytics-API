import json
from typing import Any, Optional


from shared.grid_client import GridClient
from shared.utils.llm import LLMClient

from app.models.schemas import (
    GameType,
    TeamProfile,
    PlayerProfile,
    StrategyRecommendation,
)
from app.services.opponent_analyzer import OpponentAnalyzer
from app.services.player_profiler import PlayerProfiler
from app.services.prompts import COUNTER_STRATEGY_SYSTEM_PROMPT, COUNTER_STRATEGY_USER_PROMPT


class CounterStrategyGenerator:
    """Generates actionable counter-strategies based on opponent analysis."""

    def __init__(
        self,
        grid_client: Optional[GridClient] = None,
        llm_client: Optional[LLMClient] = None,
    ):
        self.grid_client = grid_client or GridClient()
        self.llm_client = llm_client or LLMClient()
        self.opponent_analyzer = OpponentAnalyzer(self.grid_client)
        self.player_profiler = PlayerProfiler(self.grid_client)

    async def generate_counter_strategy(
        self,
        opponent_team_id: str,
        our_team_id: str,
        game: GameType,
        num_opponent_matches: int = 10,
        num_our_matches: int = 5,
    ) -> tuple[list[StrategyRecommendation], list[str], list[str], list[dict], str]:
        """Generate comprehensive counter-strategy.

        Args:
            opponent_team_id: Opponent team ID
            our_team_id: Our team ID
            game: Game type
            num_opponent_matches: Matches to analyze for opponent
            num_our_matches: Matches to analyze for our team

        Returns:
            Tuple of (recommendations, win_conditions, draft/map_recs, key_matchups, summary)
        """
        # Analyze both teams
        opponent_profile = await self.opponent_analyzer.analyze_team(
            opponent_team_id, num_opponent_matches, game
        )
        our_profile = await self.opponent_analyzer.analyze_team(
            our_team_id, num_our_matches, game
        )

        return await self._generate_with_llm(opponent_profile, our_profile, game)

    async def _generate_with_llm(
        self,
        opponent: TeamProfile,
        our_team: TeamProfile,
        game: GameType,
    ) -> tuple[list[StrategyRecommendation], list[str], list[str], list[dict], str]:
        """Generate strategy using LLM."""
        
        # Prepare data for prompt
        opponent_threats = "N/A" # Ideally would fetch player profiles too, but keeping it simple for now
        
        prompt = COUNTER_STRATEGY_USER_PROMPT.format(
            game=game.value,
            opponent_name=opponent.team_name,
            opponent_playstyle=opponent.playstyle,
            our_name=our_team.team_name,
            our_playstyle=our_team.playstyle,
            opponent_weaknesses=", ".join(opponent.weaknesses),
            opponent_strengths=", ".join(opponent.strengths),
            opponent_patterns=self._format_patterns(opponent),
            opponent_threats=opponent_threats, 
            opponent_preferences=self._format_preferences(opponent, game),
            our_strengths=", ".join(our_team.strengths),
        )

        try:
            # Call LLM
            response_text = await self.llm_client.generate(
                prompt, 
                system_prompt=COUNTER_STRATEGY_SYSTEM_PROMPT,
                max_tokens=2048
            )
            
            # Parse JSON
            # Clean formatting if LLM includes backticks
            cleaned_text = response_text.replace("```json", "").replace("```", "").strip()
            data = json.loads(cleaned_text)
            
            # Map to objects
            recommendations = []
            for rec in data.get("recommendations", []):
                recommendations.append(StrategyRecommendation(
                    title=rec.get("title", "Strategy"),
                    priority=rec.get("priority", "Medium"),
                    category=rec.get("category", "General"),
                    description=rec.get("description", ""),
                    execution_steps=rec.get("execution_steps", []),
                    risks=[],
                    success_indicators=[]
                ))

            win_conditions = data.get("win_conditions", [])
            draft_map_recs = data.get("draft_map_advice", [])
            key_matchups = data.get("key_matchups", [])
            summary = data.get("summary", "")

            return recommendations, win_conditions, draft_map_recs, key_matchups, summary

        except Exception as e:
            print(f"LLM Generation failed: {e}")
            # Fallback to static generation if LLM fails
            if game == GameType.LOL:
                return await self._generate_lol_counter_strategy_static(opponent, our_team)
            else:
                return await self._generate_valorant_counter_strategy_static(opponent, our_team)

    def _format_patterns(self, profile: TeamProfile) -> str:
        """Format team patterns for prompt."""
        patterns = []
        patterns.extend(profile.early_game_patterns)
        patterns.extend(profile.mid_game_patterns)
        patterns.extend(profile.late_game_patterns)
        patterns.extend(profile.attack_tendencies)
        patterns.extend(profile.defense_tendencies)
        return ", ".join(patterns) if patterns else "No clear patterns"

    def _format_preferences(self, profile: TeamProfile, game: GameType) -> str:
        """Format preferences."""
        if game == GameType.VALORANT and profile.map_preferences:
            best = max(profile.map_preferences.items(), key=lambda x: x[1].win_rate)
            worst = min(profile.map_preferences.items(), key=lambda x: x[1].win_rate)
            return f"Best Map: {best[0]} ({best[1].win_rate:.0%}), Worst Map: {worst[0]} ({worst[1].win_rate:.0%})"
        return "N/A"

    async def _generate_lol_counter_strategy_static(
        self,
        opponent: TeamProfile,
        our_team: TeamProfile,
    ) -> tuple[list[StrategyRecommendation], list[str], list[str], list[dict], str]:
        """Fallback static generation for LoL."""
        # ... preserved simplistic logic for fallback ...
        recommendations = []
        win_conditions = ["Control objectives", "Don't feed"]
        draft_recs = ["Ban their best champ"]
        
        # Simple rule-based
        for weakness in opponent.weaknesses:
             recommendations.append(StrategyRecommendation(
                title=f"Exploit {weakness}",
                description=f"Focus on their {weakness}",
                execution_steps=["Step 1", "Step 2"]
            ))
            
        return recommendations, win_conditions, draft_recs, [], "Static fallback summary."

    async def _generate_valorant_counter_strategy_static(
        self,
        opponent: TeamProfile,
        our_team: TeamProfile,
    ) -> tuple[list[StrategyRecommendation], list[str], list[str], list[dict], str]:
        """Fallback static generation for Valorant."""
        recommendations = []
        win_conditions = ["Win pistol rounds", "Trade efficiently"]
        map_recs = ["Veto their best map"]
        
        for weakness in opponent.weaknesses:
             recommendations.append(StrategyRecommendation(
                title=f"Exploit {weakness}",
                description=f"Focus on their {weakness}",
                execution_steps=["Step 1", "Step 2"]
            ))
            
        return recommendations, win_conditions, map_recs, [], "Static fallback summary."
