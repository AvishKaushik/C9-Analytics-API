"""League of Legends Pydantic models.

These models are for computed/aggregated stats from Series State API data.
For raw API response models, see shared/models/grid_api.py.

NOTE: The GRID Central Data API does NOT provide aggregated stats directly.
Stats must be computed by fetching data from the Series State API and aggregating.
"""

from datetime import datetime
from typing import Optional
from enum import Enum
from pydantic import BaseModel, Field


class Role(str, Enum):
    """LoL roles."""
    TOP = "top"
    JUNGLE = "jungle"
    MID = "mid"
    ADC = "adc"
    SUPPORT = "support"


class Side(str, Enum):
    """LoL map sides."""
    BLUE = "blue"
    RED = "red"


class ObjectiveType(str, Enum):
    """LoL objective types."""
    DRAGON = "dragon"
    BARON = "baron"
    HERALD = "herald"
    TOWER = "tower"
    INHIBITOR = "inhibitor"


class LoLChampion(BaseModel):
    """Champion information and stats."""

    id: str
    name: str
    role: Optional[Role] = None
    games_played: int = 0
    wins: int = 0
    losses: int = 0
    win_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    average_kda: float = 0.0
    ban_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    pick_rate: float = Field(default=0.0, ge=0.0, le=1.0)

    # Synergy and counter data
    synergies: dict[str, float] = Field(default_factory=dict)
    counters: dict[str, float] = Field(default_factory=dict)
    countered_by: dict[str, float] = Field(default_factory=dict)


class LoLObjective(BaseModel):
    """Game objective information."""

    type: ObjectiveType
    count: int = 0
    first_timestamp: Optional[int] = None
    secured: bool = False


class LoLItem(BaseModel):
    """Item information."""

    id: str
    name: str
    gold: int = 0


class LoLPlayerPerformance(BaseModel):
    """Player performance in a single game."""

    player_id: str
    player_name: str
    champion: LoLChampion
    role: Role
    kills: int = 0
    deaths: int = 0
    assists: int = 0
    cs: int = 0
    cs_per_minute: float = 0.0
    gold: int = 0
    gold_per_minute: float = 0.0
    damage_dealt: int = 0
    damage_per_minute: float = 0.0
    vision_score: int = 0
    wards_placed: int = 0
    wards_destroyed: int = 0
    items: list[LoLItem] = Field(default_factory=list)
    first_blood: bool = False
    first_tower: bool = False
    kill_participation: float = Field(default=0.0, ge=0.0, le=1.0)

    @property
    def kda(self) -> float:
        """Calculate KDA ratio."""
        if self.deaths == 0:
            return float(self.kills + self.assists)
        return (self.kills + self.assists) / self.deaths


class LoLPlayer(BaseModel):
    """Player information and aggregated stats."""

    id: str
    name: str
    nickname: Optional[str] = None
    team_id: Optional[str] = None
    team_name: Optional[str] = None
    role: Optional[Role] = None

    # Aggregated stats
    games_played: int = 0
    wins: int = 0
    losses: int = 0
    average_kills: float = 0.0
    average_deaths: float = 0.0
    average_assists: float = 0.0
    average_cs: float = 0.0
    average_vision_score: float = 0.0
    average_damage_dealt: float = 0.0
    average_gold: float = 0.0
    kill_participation: float = Field(default=0.0, ge=0.0, le=1.0)

    # Champion pool
    champion_pool: list[LoLChampion] = Field(default_factory=list)

    @property
    def win_rate(self) -> float:
        """Calculate win rate."""
        if self.games_played == 0:
            return 0.0
        return self.wins / self.games_played


class LoLDraftPick(BaseModel):
    """Single draft pick or ban."""

    champion: LoLChampion
    order: int
    player_id: Optional[str] = None
    player_name: Optional[str] = None
    role: Optional[Role] = None


class LoLDraftState(BaseModel):
    """Draft state for a team."""

    team_id: str
    team_name: str
    side: Side
    bans: list[LoLDraftPick] = Field(default_factory=list)
    picks: list[LoLDraftPick] = Field(default_factory=list)

    @property
    def banned_champions(self) -> list[str]:
        """Get list of banned champion names."""
        return [ban.champion.name for ban in self.bans]

    @property
    def picked_champions(self) -> list[str]:
        """Get list of picked champion names."""
        return [pick.champion.name for pick in self.picks]


class LoLTeamGameStats(BaseModel):
    """Team stats for a single game."""

    team_id: str
    team_name: str
    side: Side
    score: int = 0
    players: list[LoLPlayerPerformance] = Field(default_factory=list)
    objectives: list[LoLObjective] = Field(default_factory=list)
    draft: Optional[LoLDraftState] = None

    @property
    def total_kills(self) -> int:
        """Get total team kills."""
        return sum(p.kills for p in self.players)

    @property
    def total_deaths(self) -> int:
        """Get total team deaths."""
        return sum(p.deaths for p in self.players)


class LoLGame(BaseModel):
    """Single game in a match."""

    id: str
    sequence_number: int = 1
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    duration: int = 0  # in seconds
    winner_id: Optional[str] = None
    winner_name: Optional[str] = None
    teams: list[LoLTeamGameStats] = Field(default_factory=list)
    events: list[dict] = Field(default_factory=list)


class LoLMatch(BaseModel):
    """Complete match information."""

    id: str
    series_id: Optional[str] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    games: list[LoLGame] = Field(default_factory=list)

    @property
    def total_games(self) -> int:
        """Get total number of games played."""
        return len(self.games)


class LoLTeamStats(BaseModel):
    """Aggregated team statistics."""

    team_id: str
    team_name: str
    games_played: int = 0
    wins: int = 0
    losses: int = 0
    average_game_duration: float = 0.0
    first_blood_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    first_tower_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    first_dragon_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    first_herald_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    first_baron_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    average_dragons: float = 0.0
    average_barons: float = 0.0
    average_towers: float = 0.0
    average_kills: float = 0.0
    average_deaths: float = 0.0

    @property
    def win_rate(self) -> float:
        """Calculate win rate."""
        if self.games_played == 0:
            return 0.0
        return self.wins / self.games_played


class LoLTeam(BaseModel):
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
    players: list[LoLPlayer] = Field(default_factory=list)
    stats: Optional[LoLTeamStats] = None


class LoLComposition(BaseModel):
    """Team composition pattern."""

    champions: list[LoLChampion] = Field(default_factory=list)
    games_played: int = 0
    wins: int = 0
    losses: int = 0
    average_game_duration: float = 0.0
    strategy: Optional[str] = None  # e.g., "teamfight", "split-push", "pick"

    @property
    def win_rate(self) -> float:
        """Calculate win rate."""
        if self.games_played == 0:
            return 0.0
        return self.wins / self.games_played
