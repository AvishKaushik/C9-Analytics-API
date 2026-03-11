"""LLM integration utilities for generating natural language insights.

Supports multiple LLM providers:
- Groq (free, fast) - recommended for hackathons
- Anthropic (paid)
- Ollama (local, free)
"""

import os
from typing import Any, Optional
from functools import lru_cache
from pydantic import BaseModel


class InsightRequest(BaseModel):
    """Request model for generating insights."""

    data: dict[str, Any]
    insight_type: str
    game: str  # "lol" or "valorant"
    context: Optional[str] = None


class LLMClient:
    """Client for LLM-powered insight generation.

    Supports multiple providers:
    - "groq": Free, fast inference (default)
    - "anthropic": Claude models (paid)
    - "ollama": Local models (free)
    """

    def __init__(
        self,
        provider: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self.provider = provider or os.getenv("LLM_PROVIDER", "groq")

        if self.provider == "groq":
            self.api_key = api_key or os.getenv("GROQ_API_KEY", "")
            self.model = model or "llama-3.3-70b-versatile"
        elif self.provider == "anthropic":
            self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY", "")
            self.model = model or "claude-sonnet-4-20250514"
        elif self.provider == "ollama":
            self.api_key = ""  # Not needed for local
            self.model = model or "llama3.2"
            self.ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
        else:
            raise ValueError(f"Unknown provider: {self.provider}")

        self._client = None

    def _get_groq_client(self):
        """Get Groq client."""
        if self._client is None:
            from groq import Groq
            self._client = Groq(api_key=self.api_key)
        return self._client

    def _get_anthropic_client(self):
        """Get Anthropic client."""
        if self._client is None:
            import anthropic
            self._client = anthropic.Anthropic(api_key=self.api_key)
        return self._client

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1024,
    ) -> str:
        """Generate a response from the LLM.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            max_tokens: Maximum tokens in response

        Returns:
            Generated text response
        """
        system = system_prompt or "You are an expert esports analyst providing actionable insights."

        if self.provider == "groq":
            return await self._generate_groq(prompt, system, max_tokens)
        elif self.provider == "anthropic":
            return await self._generate_anthropic(prompt, system, max_tokens)
        elif self.provider == "ollama":
            return await self._generate_ollama(prompt, system, max_tokens)
        else:
            raise ValueError(f"Unknown provider: {self.provider}")

    async def _generate_groq(self, prompt: str, system: str, max_tokens: int) -> str:
        """Generate using Groq (free tier)."""
        client = self._get_groq_client()
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            max_tokens=max_tokens,
            temperature=0.7,
        )
        return response.choices[0].message.content

    async def _generate_anthropic(self, prompt: str, system: str, max_tokens: int) -> str:
        """Generate using Anthropic."""
        client = self._get_anthropic_client()
        response = client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text

    async def _generate_ollama(self, prompt: str, system: str, max_tokens: int) -> str:
        """Generate using local Ollama."""
        import httpx

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": f"{system}\n\nUser: {prompt}",
                    "stream": False,
                    "options": {"num_predict": max_tokens},
                },
                timeout=60.0,
            )
            result = response.json()
            return result.get("response", "")


@lru_cache()
def get_llm_client() -> LLMClient:
    """Get singleton LLM client instance."""
    return LLMClient()


# Prompt templates for different insight types
INSIGHT_TEMPLATES = {
    "player_improvement": """
Analyze the following player performance data and provide actionable improvement insights.

Player: {player_name}
Game: {game}
Recent Performance Data:
{data}

Provide 3-5 specific, actionable insights for improvement based on the data.
Focus on patterns, weaknesses, and concrete areas for growth.
Format each insight with a clear title and explanation.
""",
    "team_pattern": """
Analyze the following team statistics and identify key patterns.

Team: {team_name}
Game: {game}
Statistics:
{data}

Identify:
1. Consistent strengths to leverage
2. Recurring weaknesses to address
3. Strategic patterns and tendencies
4. Comparison to typical professional play

Be specific and reference the data in your analysis.
""",
    "macro_review": """
Review the following match data and create a structured game review agenda.

Match ID: {match_id}
Game: {game}
Match Data:
{data}

Create a review agenda that covers:
1. Key turning points (with timestamps if available)
2. Critical decision errors
3. Execution highlights and lowlights
4. Strategic observations
5. Priority topics for team discussion

Format as a structured agenda with time allocations for each topic.
""",
    "what_if": """
Analyze the following game state and predict the outcome of an alternative scenario.

Game: {game}
Current State:
{data}

Scenario: {scenario}

Provide:
1. Probability estimate for success (0-100%)
2. Key factors that influence this probability
3. Potential risks and rewards
4. Historical precedents if applicable

Base your analysis on typical professional play patterns.
""",
    "scouting_report": """
Generate a comprehensive scouting report based on the following team data.

Team: {team_name}
Game: {game}
Data:
{data}

Include:
1. Team Overview (playstyle, strengths, identity)
2. Individual Player Profiles (tendencies, champion/agent pools)
3. Strategic Patterns (compositions, site preferences, objective focus)
4. Exploitable Weaknesses
5. Key Preparation Points

Make the report actionable for an opposing team's preparation.
""",
    "counter_strategy": """
Based on the following opponent analysis, generate counter-strategy recommendations.

Opponent: {opponent_name}
Your Team: {our_team_name}
Game: {game}
Opponent Data:
{opponent_data}
Your Team Data:
{our_data}

Provide:
1. Win Conditions (how to beat this opponent)
2. Draft/Composition Recommendations
3. In-Game Strategic Adjustments
4. Player Matchup Considerations
5. Key Moments to Exploit

Be specific and actionable.
""",
    "draft_recommendation": """
Analyze the current draft state and provide pick/ban recommendations.

Our Side: {side}
Current Draft State:
{draft_state}

Our Team Champion Pools:
{champion_pools}

Opponent Tendencies:
{opponent_tendencies}

Provide:
1. Top 3 recommended picks with reasoning
2. Priority bans for remaining phases
3. Composition synergy analysis
4. Win condition assessment
5. Risk factors

Consider both individual champion strength and team composition.
""",
}


async def generate_insight(
    insight_type: str,
    data: dict[str, Any],
    game: str,
    **kwargs: Any,
) -> str:
    """Generate an insight using the LLM.

    Args:
        insight_type: Type of insight (matches template keys)
        data: Data to analyze
        game: Game type ("lol" or "valorant")
        **kwargs: Additional template variables

    Returns:
        Generated insight text
    """
    template = INSIGHT_TEMPLATES.get(insight_type)
    if not template:
        raise ValueError(f"Unknown insight type: {insight_type}")

    prompt = template.format(
        data=_format_data(data),
        game=game.upper(),
        **kwargs,
    )

    client = get_llm_client()
    return await client.generate(prompt)


async def generate_report(
    report_type: str,
    sections: list[dict[str, Any]],
    game: str,
) -> str:
    """Generate a structured report with multiple sections.

    Args:
        report_type: Type of report
        sections: List of section data dictionaries
        game: Game type ("lol" or "valorant")

    Returns:
        Complete generated report
    """
    system_prompt = f"""
You are an expert {game.upper()} analyst creating professional reports.
Structure your output with clear headers and bullet points.
Use specific data references to support your analysis.
Keep language concise and actionable.
"""

    sections_text = "\n\n".join(
        f"## {section.get('title', 'Section')}\n{_format_data(section.get('data', {}))}"
        for section in sections
    )

    prompt = f"""
Generate a comprehensive {report_type} report based on the following sections:

{sections_text}

Synthesize the information into a cohesive report with executive summary and recommendations.
"""

    client = get_llm_client()
    return await client.generate(prompt, system_prompt=system_prompt, max_tokens=2048)


def _format_data(data: dict[str, Any], indent: int = 0) -> str:
    """Format data dictionary for prompt inclusion."""
    lines = []
    prefix = "  " * indent

    for key, value in data.items():
        if isinstance(value, dict):
            lines.append(f"{prefix}{key}:")
            lines.append(_format_data(value, indent + 1))
        elif isinstance(value, list):
            lines.append(f"{prefix}{key}:")
            for item in value[:10]:  # Limit list items
                if isinstance(item, dict):
                    lines.append(_format_data(item, indent + 1))
                else:
                    lines.append(f"{prefix}  - {item}")
        else:
            lines.append(f"{prefix}{key}: {value}")

    return "\n".join(lines)
