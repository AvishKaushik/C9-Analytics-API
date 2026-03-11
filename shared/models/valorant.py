"""VALORANT Pydantic models.

These models are for computed/aggregated stats from Series State API data.
For raw API response models, see shared/models/grid_api.py.

NOTE: The GRID Central Data API does NOT provide aggregated stats directly.
Stats must be computed by fetching data from the Series State API and aggregating.
"""

from datetime import datetime
from typing import Optional
from enum import Enum
from pydantic import BaseModel, Field


class AgentRole(str, Enum):
    """VALORANT agent roles."""
    DUELIST = "duelist"
    INITIATOR = "initiator"
    CONTROLLER = "controller"
    SENTINEL = "sentinel"


class Side(str, Enum):
    ATTACK = "attack"
    DEFENSE = "defense"


class WinCondition(str, Enum):
    ELIMINATION = "elimination"
    SPIKE_DETONATION = "spike_detonation"
    SPIKE_DEFUSE = "spike_defuse"
    TIME_EXPIRED = "time_expired"


class EconomyType(str, Enum):
    PISTOL = "pistol"
    ECO = "eco"
    FORCE = "force"
    FULL_BUY = "full_buy"
    BONUS = "bonus"


class ValorantMap(BaseModel):
    """Map information."""

    id: str
    name: str


class ValorantAgent(BaseModel):
    """Agent information and stats."""

    id: str
    name: str
    role: AgentRole
    games_played: int = 0
    wins: int = 0
    losses: int = 0
    win_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    average_acs: float = 0.0
    average_kast: float = Field(default=0.0, ge=0.0, le=1.0)
    pick_rate: float = Field(default=0.0, ge=0.0, le=1.0)


class ValorantPlayerPerformance(BaseModel):
    """Player performance in a single game."""

    player_id: str
    player_name: str
    agent: ValorantAgent
    kills: int = 0
    deaths: int = 0
    assists: int = 0
    acs: float = 0.0  # Average Combat Score
    kast: float = Field(default=0.0, ge=0.0, le=1.0)  # Kill/Assist/Survive/Trade %
    adr: float = 0.0  # Average Damage per Round
    first_bloods: int = 0
    first_deaths: int = 0
    clutches: int = 0
    clutches_attempted: int = 0
    plants: int = 0
    defuses: int = 0
    attack_round_kills: int = 0
    defense_round_kills: int = 0
    econ_rating: float = 0.0
    headshot_percentage: float = Field(default=0.0, ge=0.0, le=1.0)

    @property
    def kda(self) -> float:
        """Calculate KDA ratio."""
        if self.deaths == 0:
            return float(self.kills + self.assists)
        return (self.kills + self.assists) / self.deaths

    @property
    def clutch_rate(self) -> float:
        """Calculate clutch success rate."""
        if self.clutches_attempted == 0:
            return 0.0
        return self.clutches / self.clutches_attempted


class ValorantPlayer(BaseModel):
    """Player information and aggregated stats."""

    id: str
    name: str
    nickname: Optional[str] = None
    team_id: Optional[str] = None
    team_name: Optional[str] = None
    role: Optional[str] = None  # In-game role description

    # Aggregated stats
    games_played: int = 0
    wins: int = 0
    losses: int = 0
    rounds_played: int = 0
    average_acs: float = 0.0
    average_kast: float = Field(default=0.0, ge=0.0, le=1.0)
    average_adr: float = 0.0
    average_kills: float = 0.0
    average_deaths: float = 0.0
    average_assists: float = 0.0
    first_blood_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    first_death_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    clutch_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    headshot_percentage: float = Field(default=0.0, ge=0.0, le=1.0)

    # Agent pool
    agent_pool: list[ValorantAgent] = Field(default_factory=list)

    @property
    def win_rate(self) -> float:
        """Calculate win rate."""
        if self.games_played == 0:
            return 0.0
        return self.wins / self.games_played


class ValorantRoundEconomy(BaseModel):
    """Economy information for a round."""

    team_id: str
    loadout_value: int = 0
    spent: int = 0
    economy_type: Optional[EconomyType] = None


class ValorantPlant(BaseModel):
    """Spike plant information."""

    timestamp: int
    site: str
    player_id: str


class ValorantDefuse(BaseModel):
    """Spike defuse information."""

    timestamp: int
    player_id: str


class ValorantRound(BaseModel):
    """Single round in a game."""

    number: int
    winning_team_id: str
    win_condition: WinCondition
    attacking_team_id: str
    plant: Optional[ValorantPlant] = None
    defuse: Optional[ValorantDefuse] = None
    economy: list[ValorantRoundEconomy] = Field(default_factory=list)
    events: list[dict] = Field(default_factory=list)
    utility_usage: list[dict] = Field(default_factory=list)


class ValorantTeamGameStats(BaseModel):
    """Team stats for a single game."""

    team_id: str
    team_name: str
    rounds_won: int = 0
    rounds_lost: int = 0
    attack_rounds_won: int = 0
    defense_rounds_won: int = 0
    players: list[ValorantPlayerPerformance] = Field(default_factory=list)

    @property
    def total_kills(self) -> int:
        """Get total team kills."""
        return sum(p.kills for p in self.players)

    @property
    def total_deaths(self) -> int:
        """Get total team deaths."""
        return sum(p.deaths for p in self.players)

    @property
    def average_acs(self) -> float:
        """Get team average ACS."""
        if not self.players:
            return 0.0
        return sum(p.acs for p in self.players) / len(self.players)


class ValorantGame(BaseModel):
    """Single game (map) in a match."""

    id: str
    sequence_number: int = 1
    map: ValorantMap
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    winner_id: Optional[str] = None
    winner_name: Optional[str] = None
    teams: list[ValorantTeamGameStats] = Field(default_factory=list)
    rounds: list[ValorantRound] = Field(default_factory=list)

    @property
    def total_rounds(self) -> int:
        """Get total number of rounds played."""
        return len(self.rounds)


class ValorantMatch(BaseModel):
    """Complete match information."""

    id: str
    series_id: Optional[str] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    games: list[ValorantGame] = Field(default_factory=list)

    @property
    def total_games(self) -> int:
        """Get total number of games (maps) played."""
        return len(self.games)


class ValorantMapStats(BaseModel):
    """Team statistics on a specific map."""

    map: ValorantMap
    games_played: int = 0
    wins: int = 0
    losses: int = 0
    attack_round_win_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    defense_round_win_rate: float = Field(default=0.0, ge=0.0, le=1.0)

    @property
    def win_rate(self) -> float:
        """Calculate win rate."""
        if self.games_played == 0:
            return 0.0
        return self.wins / self.games_played


class ValorantTeamStats(BaseModel):
    """Aggregated team statistics."""

    team_id: str
    team_name: str
    games_played: int = 0
    wins: int = 0
    losses: int = 0
    rounds_played: int = 0
    round_win_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    attack_round_win_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    defense_round_win_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    pistol_round_win_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    eco_round_win_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    average_rounds_per_game: float = 0.0
    first_blood_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    first_death_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    map_stats: list[ValorantMapStats] = Field(default_factory=list)

    @property
    def win_rate(self) -> float:
        """Calculate win rate."""
        if self.games_played == 0:
            return 0.0
        return self.wins / self.games_played


class ValorantTeam(BaseModel):
    """Team information.

    NOTE: From Central Data API, only basic metadata is available.
    Stats and roster must be computed from Series State API data.
    """

    id: str
    name: str
    name_shortened: Optional[str] = None
    logo_url: Optional[str] = None
    color_primary: str = "#000000"
    color_secondary: str = "#FFFFFF"
    rating: Optional[float] = None
    organization_id: Optional[str] = None
    organization_name: Optional[str] = None
    players: list[ValorantPlayer] = Field(default_factory=list)
    stats: Optional[ValorantTeamStats] = None


class ValorantComposition(BaseModel):
    """Team composition pattern."""

    agents: list[ValorantAgent] = Field(default_factory=list)
    map: Optional[ValorantMap] = None
    games_played: int = 0
    wins: int = 0
    losses: int = 0
    attack_round_win_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    defense_round_win_rate: float = Field(default=0.0, ge=0.0, le=1.0)

    @property
    def win_rate(self) -> float:
        """Calculate win rate."""
        if self.games_played == 0:
            return 0.0
        return self.wins / self.games_played


class ValorantDefaultSetup(BaseModel):
    """Default site setup patterns."""

    map: ValorantMap
    attack_defaults: list[dict] = Field(default_factory=list)
    defense_defaults: list[dict] = Field(default_factory=list)
