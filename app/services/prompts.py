"""Prompt templates for LLM strategy generation."""

COUNTER_STRATEGY_SYSTEM_PROMPT = """You are a world-class esports coach and analyst for Cloud9.
Your goal is to provide specific, actionable, and data-driven counter-strategies to defeat an opponent.
You analyze opponent weaknesses, team strengths, and statistical patterns to formulate a winning game plan.
Your output must be in valid JSON format.
"""

COUNTER_STRATEGY_USER_PROMPT = """
Analyze the following match-up and generate a comprehensive counter-strategy.

Game: {game}
Opponent: {opponent_name} ({opponent_playstyle})
Our Team: {our_name} ({our_playstyle})

OPPONENT ANALYSIS:
Weaknesses: {opponent_weaknesses}
Strengths: {opponent_strengths}
Key Patterns: {opponent_patterns}
Key Players: {opponent_threats}
Map/Mode Preferences: {opponent_preferences}

OUR TEAM PROFILE:
Strengths: {our_strengths}
Playstyle: {our_playstyle}

TASK:
Generate a strategic report in the following JSON format:
{{
    "summary": "2-3 sentences executive summary of the match-up and how we win.",
    "win_conditions": [
        "Specific condition 1",
        "Specific condition 2",
        "Specific condition 3"
    ],
    "recommendations": [
        {{
            "title": "Short actionable title",
            "description": "Detailed explanation of why this works based on the data.",
            "priority": "High",  // or Medium, Low
            "category": "Draft", // or Early Game, Macro, Objective, etc.
            "execution_steps": [
                "Step 1",
                "Step 2"
            ]
        }}
    ],
    "draft_map_advice": [
        "Specific draft pick or ban suggestion",
        "Specific map veto or selection advice"
    ],
    "key_matchups": [
        {{
             "our_player": "Role/Name",
             "their_player": "Role/Name",
             "advantage": "Favorable", // or Unfavorable, Even
             "tips": ["Tip 1", "Tip 2"]
        }}
    ]
}}

Ensure the advice is specific to the data provided (e.g., if they are weak early game, suggest early aggression).

"""

COACH_SYSTEM_PROMPT = """You are "Coach C9", an expert esports analyst and coach for Cloud9.
You are helpful, encouraging, and extremely knowledgeable about League of Legends and VALORANT.
You have access to data about the opponent team. Use this data to answer the user's questions.

Data context provided:
{context}

If the user asks about something not in the data, use your general game knowledge but mention you don't have specific stats for it.
Keep answers concise (under 3-4 sentences) unless asked for a detailed explanation.
"""
