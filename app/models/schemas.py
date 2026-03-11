"""Unified Pydantic schemas for the C9 Analytics API.

GameType is defined ONCE here and shared across all modules.
Sections:
  - Shared / Common
  - Category 1: Assistant Coach
  - Category 2: Scouting Report
  - Category 3: Draft Assistant
"""

from datetime import datetime
from typing import Optional
from enum import Enum
from pydantic import BaseModel, Field


# ── Shared / Common ───────────────────────────────────────────────────────────

class GameType(str, Enum):
    LOL = "lol"
    VALORANT = "Valorant"


# ── Category 1: Assistant Coach ───────────────────────────────────────────────

class Pattern(BaseModel):
    """Detected pattern in player/team data."""

    pattern_type: str
    description: str
    frequency: float = Field(ge=0.0, le=1.0)
    impact: str  # "positive", "negative", "neutral"
    games_observed: int = 0
    examples: list[dict] = Field(default_factory=list)
    recommendation: Optional[str] = None


class Insight(BaseModel):
    """Individual coaching insight."""

    title: str
    category: str  # "mechanical", "strategic", "mental", "teamwork"
    priority: str  # "high", "medium", "low"
    description: str
    data_points: list[dict] = Field(default_factory=list)
    actionable_steps: list[str] = Field(default_factory=list)


class PlayerInsightRequest(BaseModel):
    """Request for player insights."""

    player_id: str
    match_ids: list[str] = Field(default_factory=list, max_length=50)
    game: GameType
    focus_areas: list[str] = Field(default_factory=list)
    limit: int = Field(default=10, ge=1, le=50, description="Number of series to analyze")


class PlayerStats(BaseModel):
    """Aggregated player statistics."""

    games_played: int = 0
    wins: int = 0
    losses: int = 0
    win_rate: float = 0.0
    total_kills: int = 0
    total_deaths: int = 0
    total_assists: int = 0
    avg_kills: float = 0.0
    avg_deaths: float = 0.0
    avg_assists: float = 0.0
    avg_kda: float = 0.0
    best_kda_game: Optional[dict] = None
    worst_kda_game: Optional[dict] = None


class AgentStats(BaseModel):
    """Stats for a specific agent/champion."""

    agent_id: str
    agent_name: str
    games_played: int = 0
    wins: int = 0
    win_rate: float = 0.0
    avg_kills: float = 0.0
    avg_deaths: float = 0.0
    avg_assists: float = 0.0
    avg_kda: float = 0.0


class RecentForm(BaseModel):
    """Recent performance trend."""

    last_5_results: list[str] = Field(default_factory=list)  # ["W", "L", "W", "W", "L"]
    form_rating: str = "neutral"  # "hot", "cold", "neutral"
    trend: str = "stable"  # "improving", "declining", "stable"
    recent_avg_kda: float = 0.0


class PlayerInsightResponse(BaseModel):
    """Response containing player insights."""

    player_id: str
    player_name: str
    game: GameType
    analysis_period: str
    stats: Optional[PlayerStats] = None
    agent_pool: list[AgentStats] = Field(default_factory=list)
    recent_form: Optional[RecentForm] = None
    patterns: list[Pattern] = Field(default_factory=list)
    insights: list[Insight] = Field(default_factory=list)
    recent_matches: list[dict] = Field(default_factory=list)
    summary: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)


class TeamInsightRequest(BaseModel):
    """Request for team insights."""

    team_id: str
    match_ids: list[str] = Field(default_factory=list, max_length=50)
    game: GameType
    focus_areas: list[str] = Field(default_factory=list)
    limit: int = Field(default=10, ge=1, le=50, description="Number of series to analyze")


class TeamStats(BaseModel):
    """Aggregated team statistics."""

    games_played: int = 0
    wins: int = 0
    losses: int = 0
    win_rate: float = 0.0
    total_kills: int = 0
    total_deaths: int = 0
    avg_kills_per_game: float = 0.0
    avg_deaths_per_game: float = 0.0
    team_kd: float = 0.0


class PlayerSummary(BaseModel):
    """Brief player summary for roster."""

    player_id: str
    player_name: str
    games_played: int = 0
    avg_kda: float = 0.0
    win_rate: float = 0.0
    main_agents: list[str] = Field(default_factory=list)
    recent_form: str = "neutral"  # "hot", "cold", "neutral"


class TeamInsightResponse(BaseModel):
    """Response containing team insights."""

    team_id: str
    team_name: str
    game: GameType
    analysis_period: str
    team_stats: Optional[TeamStats] = None
    roster: list[PlayerSummary] = Field(default_factory=list)
    patterns: list[Pattern] = Field(default_factory=list)
    insights: list[Insight] = Field(default_factory=list)
    player_highlights: dict[str, list[str]] = Field(default_factory=dict)
    recent_matches: list[dict] = Field(default_factory=list)
    summary: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)


class RosterRequest(BaseModel):
    """Request for team roster."""

    game: GameType
    limit: int = Field(default=10, ge=1, le=50, description="Number of series to analyze for stats")


class RosterResponse(BaseModel):
    """Response containing team roster."""

    team_id: str
    team_name: str
    game: GameType
    players: list[PlayerSummary] = Field(default_factory=list)
    team_stats: Optional[TeamStats] = None
    generated_at: datetime = Field(default_factory=datetime.utcnow)


class PlayerProfileRequest(BaseModel):
    """Request for player profile."""

    game: GameType
    limit: int = Field(default=10, ge=1, le=50, description="Number of series to analyze")


class ReviewAgendaItem(BaseModel):
    """Single item in a review agenda."""

    timestamp: Optional[str] = None
    title: str
    description: str
    category: str  # "objective", "teamfight", "rotation", "economy", "execution"
    priority: str  # "critical", "important", "notable"
    players_involved: list[str] = Field(default_factory=list)
    discussion_points: list[str] = Field(default_factory=list)
    suggested_duration_minutes: int = 5


class ReviewAgenda(BaseModel):
    """Complete macro review agenda."""

    match_id: str
    game_number: int = 1
    match_outcome: str
    total_duration_minutes: int = 30
    executive_summary: str
    key_moments: list[ReviewAgendaItem] = Field(default_factory=list)
    team_level_observations: list[str] = Field(default_factory=list)
    individual_notes: dict[str, list[str]] = Field(default_factory=dict)
    priority_topics: list[str] = Field(default_factory=list)


class MacroReviewRequest(BaseModel):
    """Request for macro review generation."""

    match_id: str
    game: GameType
    game_number: int = 1
    team_id: Optional[str] = None  # Perspective for the review
    review_duration_minutes: int = Field(default=30, ge=10, le=120)


class MacroReviewResponse(BaseModel):
    """Response containing macro review."""

    agenda: ReviewAgenda
    generated_at: datetime = Field(default_factory=datetime.utcnow)


class ScenarioPrediction(BaseModel):
    """Prediction for a what-if scenario."""

    scenario_description: str
    success_probability: float = Field(ge=0.0, le=1.0)
    confidence: str  # "high", "medium", "low"
    key_factors: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    rewards: list[str] = Field(default_factory=list)
    historical_precedents: list[dict] = Field(default_factory=list)
    reasoning: str


class WhatIfRequest(BaseModel):
    """Request for what-if analysis."""

    match_id: str
    game: GameType
    timestamp: Optional[str] = None  # Game timestamp for scenario
    scenario_description: str
    game_number: int = 1


class WhatIfResponse(BaseModel):
    """Response containing what-if analysis."""

    match_id: str
    game: GameType
    original_outcome: str
    prediction: ScenarioPrediction
    alternative_scenarios: list[ScenarioPrediction] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=datetime.utcnow)


class MatchSummary(BaseModel):
    """Brief match/series summary for listing."""

    series_id: str
    opponent_name: str
    opponent_id: str
    date: Optional[str] = None
    result: str  # "Win", "Loss", "Ongoing"
    score: str  # "2-1", "1-2", etc.
    tournament: Optional[str] = None
    maps: list[str] = Field(default_factory=list)  # Map names for Valorant


class MatchListResponse(BaseModel):
    """Response containing list of matches."""

    team_id: str
    team_name: str
    game: GameType
    matches: list[MatchSummary] = Field(default_factory=list)
    total_count: int = 0
    generated_at: datetime = Field(default_factory=datetime.utcnow)


class TimelineEvent(BaseModel):
    """Single event in match timeline."""

    timestamp: Optional[str] = None
    round_number: Optional[int] = None
    event_type: str  # "kill", "objective", "round_end", "spike_plant", etc.
    description: str
    team: Optional[str] = None
    players_involved: list[str] = Field(default_factory=list)
    score_after: Optional[str] = None


class MatchTimelineResponse(BaseModel):
    """Response containing match timeline."""

    series_id: str
    game_number: int = 1
    map_name: Optional[str] = None
    events: list[TimelineEvent] = Field(default_factory=list)
    final_score: str = ""
    winner: Optional[str] = None
    duration: Optional[str] = None
    generated_at: datetime = Field(default_factory=datetime.utcnow)


class PlayerComparisonRequest(BaseModel):
    """Request for player comparison."""

    player_ids: list[str] = Field(..., min_length=2, max_length=5)
    game: GameType
    limit: int = Field(default=10, ge=1, le=50)


class PlayerComparisonStats(BaseModel):
    """Comparison stats for a single player."""

    player_id: str
    player_name: str
    games_played: int = 0
    wins: int = 0
    win_rate: float = 0.0
    avg_kills: float = 0.0
    avg_deaths: float = 0.0
    avg_assists: float = 0.0
    avg_kda: float = 0.0
    main_agents: list[str] = Field(default_factory=list)
    recent_form: str = "neutral"

    # Valorant-specific stats
    avg_acs: Optional[float] = None  # Average Combat Score
    avg_adr: Optional[float] = None  # Average Damage per Round
    headshot_pct: Optional[float] = None  # Headshot percentage
    first_kills: Optional[int] = None  # Total first kills
    first_deaths: Optional[int] = None  # Total first deaths
    fk_fd_ratio: Optional[float] = None  # First Kill / First Death ratio
    kast_pct: Optional[float] = None  # Kill/Assist/Survive/Trade percentage
    clutch_win_pct: Optional[float] = None  # Clutch win percentage
    plants: Optional[int] = None  # Spike plants
    defuses: Optional[int] = None  # Spike defuses
    multi_kills: Optional[int] = None  # 3k+ rounds

    # LoL-specific stats
    cs_per_min: Optional[float] = None  # CS per minute
    gold_per_min: Optional[float] = None  # Gold per minute
    damage_per_min: Optional[float] = None  # Damage per minute
    vision_score: Optional[float] = None  # Average vision score
    kill_participation: Optional[float] = None  # Kill participation percentage
    damage_share: Optional[float] = None  # Damage share percentage
    gold_share: Optional[float] = None  # Gold share percentage


class PlayerComparisonResponse(BaseModel):
    """Response containing player comparisons."""

    players: list[PlayerComparisonStats] = Field(default_factory=list)
    comparison_highlights: list[str] = Field(default_factory=list)
    best_performer: Optional[str] = None
    most_consistent: Optional[str] = None
    generated_at: datetime = Field(default_factory=datetime.utcnow)


class PerformanceDataPoint(BaseModel):
    """Single data point for trend chart."""

    date: str
    series_id: str
    kda: float
    kills: int
    deaths: int
    assists: int
    result: str
    agent: Optional[str] = None


class TrendResponse(BaseModel):
    """Response containing performance trends."""

    player_id: str
    player_name: str
    game: GameType
    period: str
    data_points: list[PerformanceDataPoint] = Field(default_factory=list)
    trend_direction: str = "stable"  # "improving", "declining", "stable"
    avg_kda_trend: float = 0.0
    win_rate_trend: float = 0.0
    generated_at: datetime = Field(default_factory=datetime.utcnow)


class TeamComparisonRequest(BaseModel):
    """Request for team comparison."""

    team_ids: list[str] = Field(..., min_length=2, max_length=2)
    game: GameType
    limit: int = Field(default=10, ge=1, le=50)


class TeamComparisonStats(BaseModel):
    """Comparison stats for a single team."""

    team_id: str
    team_name: str
    games_played: int = 0
    wins: int = 0
    losses: int = 0
    win_rate: float = 0.0
    avg_kills: float = 0.0
    avg_deaths: float = 0.0
    team_kd: float = 0.0
    playstyle: str = ""
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)


class HeadToHead(BaseModel):
    """Head-to-head record between two teams."""

    team_a_wins: int = 0
    team_b_wins: int = 0
    recent_matches: list[dict] = Field(default_factory=list)


class TeamComparisonResponse(BaseModel):
    """Response containing team comparisons."""

    teams: list[TeamComparisonStats] = Field(default_factory=list)
    head_to_head: Optional[HeadToHead] = None
    comparison_highlights: list[str] = Field(default_factory=list)
    advantage: Optional[str] = None
    generated_at: datetime = Field(default_factory=datetime.utcnow)


# ── Category 2: Scouting Report ───────────────────────────────────────────────

class ChampionAgentStats(BaseModel):
    """Stats for a champion or agent."""

    name: str
    games_played: int = 0
    wins: int = 0
    losses: int = 0
    win_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    average_kda: float = 0.0
    pick_rate: float = Field(default=0.0, ge=0.0, le=1.0)


class PlayerProfile(BaseModel):
    """Individual player analysis."""

    player_id: str
    player_name: str
    role: Optional[str] = None
    primary_picks: list[ChampionAgentStats] = Field(default_factory=list)
    playstyle: str = ""  # "aggressive", "passive", "adaptive"
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    tendencies: list[str] = Field(default_factory=list)
    threat_level: str = "medium"  # "high", "medium", "low"
    notes: list[str] = Field(default_factory=list)

    # Game-specific stats
    average_stats: dict[str, float] = Field(default_factory=dict)


class CompositionAnalysis(BaseModel):
    """Team composition analysis."""

    composition: list[str] = Field(default_factory=list)
    games_played: int = 0
    win_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    strategy_type: str = ""  # e.g., "teamfight", "split-push", "pick"
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    power_spikes: list[str] = Field(default_factory=list)
    counter_strategies: list[str] = Field(default_factory=list)

    # VALORANT-specific
    map: Optional[str] = None
    site_preferences: dict[str, float] = Field(default_factory=dict)


class MapStats(BaseModel):
    """Map-specific statistics for VALORANT."""

    played: int = 0
    win_rate: float = Field(default=0.0, ge=0.0, le=1.0)


class ObjectiveAnalysis(BaseModel):
    """Objective control analysis."""

    objective_type: str
    priority_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    success_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    average_timing: Optional[str] = None
    tendencies: list[str] = Field(default_factory=list)


class TeamProfile(BaseModel):
    """Complete team analysis."""

    team_id: str
    team_name: str
    overall_record: dict[str, int] = Field(default_factory=dict)  # wins, losses
    playstyle: str = ""
    identity: str = ""  # e.g., "early game focused", "scaling team"

    # Strategic tendencies
    draft_tendencies: list[str] = Field(default_factory=list)  # LoL
    map_preferences: dict[str, MapStats] = Field(default_factory=dict)  # VALORANT

    # Objective analysis
    objectives: list[ObjectiveAnalysis] = Field(default_factory=list)

    # Common patterns
    early_game_patterns: list[str] = Field(default_factory=list)
    mid_game_patterns: list[str] = Field(default_factory=list)
    late_game_patterns: list[str] = Field(default_factory=list)

    # VALORANT-specific
    attack_tendencies: list[str] = Field(default_factory=list)
    defense_tendencies: list[str] = Field(default_factory=list)
    economy_patterns: list[str] = Field(default_factory=list)

    # Overall assessment
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)


class StrategyRecommendation(BaseModel):
    """Counter-strategy recommendation."""

    title: str
    priority: str = "medium"  # "high", "medium", "low"
    category: str = ""  # "draft", "early_game", "teamfight", "macro"
    description: str
    execution_steps: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    success_indicators: list[str] = Field(default_factory=list)


class ScoutingReportRequest(BaseModel):
    """Request for scouting report generation."""

    opponent_team_id: str
    num_recent_matches: int = Field(default=10, ge=1, le=50)
    game: GameType
    include_player_profiles: bool = True
    include_composition_analysis: bool = True
    focus_areas: list[str] = Field(default_factory=list)


class ScoutingReportResponse(BaseModel):
    """Complete scouting report."""

    report_id: str
    opponent_team: TeamProfile
    player_profiles: list[PlayerProfile] = Field(default_factory=list)
    compositions: list[CompositionAnalysis] = Field(default_factory=list)
    key_findings: list[str] = Field(default_factory=list)
    preparation_priorities: list[str] = Field(default_factory=list)
    executive_summary: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    matches_analyzed: int = 0


class CounterStrategyRequest(BaseModel):
    """Request for counter-strategy generation."""

    opponent_team_id: str
    our_team_id: str
    game: GameType
    num_opponent_matches: int = Field(default=10, ge=1, le=50)
    num_our_matches: int = Field(default=5, ge=1, le=20)
    specific_focus: list[str] = Field(default_factory=list)


class CounterStrategyResponse(BaseModel):
    """Counter-strategy recommendations."""

    opponent_team_id: str
    our_team_id: str
    recommendations: list[StrategyRecommendation] = Field(default_factory=list)
    win_conditions: list[str] = Field(default_factory=list)
    draft_recommendations: list[str] = Field(default_factory=list)  # LoL
    map_recommendations: list[str] = Field(default_factory=list)  # VALORANT
    key_matchups: list[dict] = Field(default_factory=list)
    summary: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)


class TeamSearchResult(BaseModel):
    """Single team in search results."""

    team_id: str
    team_name: str
    name_shortened: Optional[str] = None
    logo_url: Optional[str] = None
    primary_color: Optional[str] = None


class TeamSearchResponse(BaseModel):
    """Response for team search."""

    query: str
    game: GameType
    results: list[TeamSearchResult] = Field(default_factory=list)
    total_count: int = 0


class ReportHistoryItem(BaseModel):
    """Single report in history."""

    report_id: str
    opponent_team_id: str
    opponent_team_name: str
    game: GameType
    matches_analyzed: int
    generated_at: datetime


class ReportHistoryResponse(BaseModel):
    """Response for report history."""

    reports: list[ReportHistoryItem] = Field(default_factory=list)
    total_count: int = 0


class TeamCompareRequest(BaseModel):
    """Request for team comparison report."""

    team_a_id: str
    team_b_id: str
    game: GameType
    num_matches: int = Field(default=10, ge=1, le=50)


class TeamCompareResponse(BaseModel):
    """Response for team comparison report."""

    team_a: TeamProfile
    team_b: TeamProfile
    comparison_summary: str
    advantage: Optional[str] = None
    key_differences: list[str] = Field(default_factory=list)
    matchup_prediction: Optional[str] = None
    generated_at: datetime = Field(default_factory=datetime.utcnow)


class DetailedMapStats(BaseModel):
    """Detailed map statistics."""

    map_name: str
    games_played: int = 0
    wins: int = 0
    losses: int = 0
    win_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    attack_rounds_won: int = 0
    attack_rounds_total: int = 0
    attack_win_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    defense_rounds_won: int = 0
    defense_rounds_total: int = 0
    defense_win_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    avg_rounds_per_game: float = 0.0


class MapStatsResponse(BaseModel):
    """Response for detailed map statistics."""

    team_id: str
    team_name: str
    maps: list[DetailedMapStats] = Field(default_factory=list)
    best_map: Optional[str] = None
    worst_map: Optional[str] = None
    generated_at: datetime = Field(default_factory=datetime.utcnow)


class PlayerThreat(BaseModel):
    """Player threat assessment."""

    player_id: str
    player_name: str
    role: Optional[str] = None
    threat_level: str = "medium"  # "high", "medium", "low"
    threat_score: float = Field(default=0.5, ge=0.0, le=1.0)
    primary_agents: list[str] = Field(default_factory=list)
    avg_kda: float = 0.0
    games_analyzed: int = 0
    key_strengths: list[str] = Field(default_factory=list)
    exploitable_weaknesses: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class ThreatRankingResponse(BaseModel):
    """Response for player threat ranking."""

    team_id: str
    team_name: str
    players: list[PlayerThreat] = Field(default_factory=list)
    top_threat: Optional[str] = None
    summary: str = ""
    generated_at: datetime = Field(default_factory=datetime.utcnow)


# ── Category 3: Draft Assistant ───────────────────────────────────────────────

class Side(str, Enum):
    BLUE = "blue"
    RED = "red"


class Role(str, Enum):
    TOP = "top"
    JUNGLE = "jungle"
    MID = "mid"
    ADC = "adc"
    SUPPORT = "support"


class DraftAction(str, Enum):
    PICK = "pick"
    BAN = "ban"


class ChampionInfo(BaseModel):
    """Champion information for draft."""

    id: str
    name: str
    roles: list[Role] = Field(default_factory=list)
    tier: str = "A"  # S, A, B, C, D
    win_rate: float = Field(default=0.5, ge=0.0, le=1.0)
    pick_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    ban_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    image_url: Optional[str] = None
    loading_image_url: Optional[str] = None

    # Synergy and counter scores (champion_id -> score)
    synergies: dict[str, float] = Field(default_factory=dict)
    counters: dict[str, float] = Field(default_factory=dict)
    countered_by: dict[str, float] = Field(default_factory=dict)


class DraftPick(BaseModel):
    """A single draft pick."""

    champion: ChampionInfo
    team: Side
    role: Optional[Role] = None
    player_id: Optional[str] = None
    player_name: Optional[str] = None
    pick_order: int


class DraftBan(BaseModel):
    """A single draft ban."""

    champion: ChampionInfo
    team: Side
    ban_order: int


class DraftState(BaseModel):
    """Current state of the draft."""

    blue_picks: list[DraftPick] = Field(default_factory=list)
    red_picks: list[DraftPick] = Field(default_factory=list)
    blue_bans: list[DraftBan] = Field(default_factory=list)
    red_bans: list[DraftBan] = Field(default_factory=list)
    current_phase: int = 1  # 1-6 (ban1, pick1, ban2, pick2, etc.)
    current_team: Side = Side.BLUE
    current_action: DraftAction = DraftAction.BAN
    is_complete: bool = False

    @property
    def all_picked_champions(self) -> list[str]:
        """Get all picked champion names."""
        return [p.champion.name for p in self.blue_picks + self.red_picks]

    @property
    def all_banned_champions(self) -> list[str]:
        """Get all banned champion names."""
        return [b.champion.name for b in self.blue_bans + self.red_bans]

    @property
    def unavailable_champions(self) -> list[str]:
        """Get all unavailable champion names."""
        return self.all_picked_champions + self.all_banned_champions


class PlayerChampionPool(BaseModel):
    """Player's champion pool data."""

    player_id: str
    player_name: str
    role: Role
    champions: list[ChampionInfo] = Field(default_factory=list)
    comfort_picks: list[str] = Field(default_factory=list)
    signature_picks: list[str] = Field(default_factory=list)


class DraftSession(BaseModel):
    """Active draft session."""

    session_id: str
    our_team_id: str
    opponent_team_id: str
    our_side: Side
    state: DraftState
    our_champion_pools: list[PlayerChampionPool] = Field(default_factory=list)
    opponent_champion_pools: list[PlayerChampionPool] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class WinProbability(BaseModel):
    """Win probability assessment."""

    probability: float = Field(ge=0.0, le=1.0)
    confidence: str = "medium"  # high, medium, low
    factors: list[str] = Field(default_factory=list)
    composition_score: float = 0.0
    matchup_score: float = 0.0
    player_comfort_score: float = 0.0


class DraftRecommendation(BaseModel):
    """Draft pick/ban recommendation."""

    champion: ChampionInfo
    action: DraftAction
    priority: int = 1  # 1 = highest priority
    reasoning: list[str] = Field(default_factory=list)
    win_probability_impact: float = 0.0
    role: Optional[Role] = None
    target_player: Optional[str] = None
    synergy_score: float = 0.0
    counter_score: float = 0.0
    flex_potential: bool = False


class OpponentPrediction(BaseModel):
    """Prediction for opponent's next action."""

    champion: ChampionInfo
    probability: float = Field(ge=0.0, le=1.0)
    likely_role: Optional[Role] = None
    reasoning: str = ""


class DraftStartRequest(BaseModel):
    """Request to start a draft session."""

    our_team_id: str
    opponent_team_id: str
    our_side: Side


class DraftStartResponse(BaseModel):
    """Response for starting a draft session."""

    session_id: str
    our_side: Side
    state: DraftState
    win_probability: Optional[WinProbability] = None
    initial_recommendations: list[DraftRecommendation] = Field(default_factory=list)
    opponent_tendencies: list[str] = Field(default_factory=list)
    priority_bans: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class DraftUpdateRequest(BaseModel):
    """Request to update draft state."""

    session_id: str
    action: DraftAction
    champion_name: str
    team: Side
    role: Optional[Role] = None
    player_id: Optional[str] = None


class DraftUpdateResponse(BaseModel):
    """Response after draft update."""

    session_id: str
    state: DraftState
    recommendations: list[DraftRecommendation] = Field(default_factory=list)
    win_probability: WinProbability
    opponent_predictions: list[OpponentPrediction] = Field(default_factory=list)
    analysis: str = ""
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class LoLTeamResult(BaseModel):
    """Single LoL team in search results."""

    team_id: str
    team_name: str
    name_shortened: Optional[str] = None
    logo_url: Optional[str] = None


class LoLTeamsResponse(BaseModel):
    """Response for LoL teams search."""

    query: Optional[str] = None
    teams: list[LoLTeamResult] = Field(default_factory=list)
    total_count: int = 0


class DraftHistoryEntry(BaseModel):
    """Single draft in history."""

    series_id: str
    opponent_name: str
    date: Optional[str] = None
    result: str
    our_picks: list[str] = Field(default_factory=list)
    our_bans: list[str] = Field(default_factory=list)
    enemy_picks: list[str] = Field(default_factory=list)
    enemy_bans: list[str] = Field(default_factory=list)


class DraftHistoryResponse(BaseModel):
    """Response for draft history."""

    team_id: str
    team_name: str
    drafts: list[DraftHistoryEntry] = Field(default_factory=list)
    most_picked: list[str] = Field(default_factory=list)
    most_banned: list[str] = Field(default_factory=list)
    first_pick_priority: list[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=datetime.utcnow)


class DraftSimulateRequest(BaseModel):
    """Request for draft simulation."""

    our_team_id: str
    opponent_team_id: str
    our_side: Side
    auto_opponent: bool = True


class DraftSimulateResponse(BaseModel):
    """Response for draft simulation."""

    session_id: str
    our_side: Side
    final_state: DraftState
    win_probability: WinProbability
    composition_type: str = ""
    win_condition: str = ""
    power_spikes: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=datetime.utcnow)


class ChampionSearchResult(BaseModel):
    """Single champion in search results."""

    id: str
    name: str
    roles: list[Role] = Field(default_factory=list)
    tier: str = "A"
    win_rate: float = 0.5
    counters: list[str] = Field(default_factory=list)
    countered_by: list[str] = Field(default_factory=list)
    synergies: list[str] = Field(default_factory=list)


class ChampionSearchResponse(BaseModel):
    """Response for champion search."""

    query: str
    results: list[ChampionSearchResult] = Field(default_factory=list)


class CompositionAnalyzeRequest(BaseModel):
    """Request for composition analysis."""

    champions: list[str] = Field(..., min_length=1, max_length=5)


class CompositionAnalyzeResponse(BaseModel):
    """Response for composition analysis."""

    champions: list[str] = Field(default_factory=list)
    composition_type: str = ""
    composition_description: str = ""
    win_condition: str = ""
    power_spikes: list[str] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    suggested_counters: list[str] = Field(default_factory=list)
    synergy_score: float = 0.0
    generated_at: datetime = Field(default_factory=datetime.utcnow)
