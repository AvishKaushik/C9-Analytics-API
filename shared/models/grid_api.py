"""Pydantic models matching the GRID API schema.

These models represent the actual data structures returned by the GRID API.
Use these for deserializing API responses.

For computed/aggregated stats, use the game-specific models in lol.py and valorant.py.
"""

from datetime import datetime, date
from typing import Optional
from enum import Enum
from pydantic import BaseModel, Field


# ============================================================================
# Enums
# ============================================================================

class SeriesType(str, Enum):
    """Type of series."""
    SCRIM = "SCRIM"
    ESPORTS = "ESPORTS"
    LOOPFEED = "LOOPFEED"
    COMPETITIVE = "COMPETITIVE"


class ServiceLevel(str, Enum):
    """Product service level availability."""
    FULL = "FULL"
    LIMITED = "LIMITED"
    NONE = "NONE"


class TournamentVenueType(str, Enum):
    """Tournament venue type."""
    UNKNOWN = "UNKNOWN"
    ONLINE = "ONLINE"
    LAN = "LAN"
    HYBRID = "HYBRID"


class OrderDirection(str, Enum):
    """Sort direction."""
    ASC = "ASC"
    DESC = "DESC"


# ============================================================================
# Common nested types
# ============================================================================

class Nationality(BaseModel):
    """Player nationality."""
    code: str  # ISO 3166-1 Alpha-3 (e.g., "USA")
    name: str  # Full name (e.g., "United States")


class ExternalEntity(BaseModel):
    """External provider entity info."""
    id: str


class DataProvider(BaseModel):
    """External data provider info."""
    name: str
    description: Optional[str] = None


class ExternalLink(BaseModel):
    """Link to external data provider."""
    dataProvider: DataProvider
    externalEntity: ExternalEntity


class Money(BaseModel):
    """Monetary value."""
    amount: float  # In USD


# ============================================================================
# Title (Game)
# ============================================================================

class Title(BaseModel):
    """A title (game) in GRID."""
    id: str
    name: str
    nameShortened: str = Field(description="Max 20 characters")
    logoUrl: str
    private: bool = False


# ============================================================================
# Player Role
# ============================================================================

class PlayerRole(BaseModel):
    """Player role (e.g., MID, SUPPORT for LoL)."""
    id: str
    name: str
    title: Optional[Title] = None
    private: bool = False


# ============================================================================
# Team
# ============================================================================

class OrganizationRelation(BaseModel):
    """Organization reference (without team list to avoid cycles)."""
    id: str
    name: str


class Team(BaseModel):
    """A team in GRID."""
    id: str
    name: str
    nameShortened: Optional[str] = None
    colorPrimary: str = "#000000"
    colorSecondary: str = "#FFFFFF"
    logoUrl: str = ""
    rating: Optional[float] = None
    private: bool = False
    updatedAt: Optional[datetime] = None
    title: Optional[Title] = None
    titles: list[Title] = Field(default_factory=list)
    organization: Optional[OrganizationRelation] = None
    externalLinks: list[ExternalLink] = Field(default_factory=list)


class TeamRelation(BaseModel):
    """Team reference in organization (without organization to avoid cycles)."""
    id: str
    name: str
    nameShortened: Optional[str] = None
    colorPrimary: str = "#000000"
    colorSecondary: str = "#FFFFFF"
    logoUrl: str = ""
    rating: Optional[float] = None
    titles: list[Title] = Field(default_factory=list)


# ============================================================================
# Organization
# ============================================================================

class Organization(BaseModel):
    """An organization in GRID."""
    id: str
    name: str
    private: bool = False
    updatedAt: Optional[datetime] = None
    teams: list[TeamRelation] = Field(default_factory=list)


# ============================================================================
# Player
# ============================================================================

class Player(BaseModel):
    """A player in GRID."""
    id: str
    nickname: str
    fullName: Optional[str] = None
    age: Optional[int] = None
    imageUrl: str = ""
    private: bool = False
    updatedAt: Optional[datetime] = None
    nationality: list[Nationality] = Field(default_factory=list)
    roles: list[PlayerRole] = Field(default_factory=list)
    team: Optional[Team] = None
    title: Optional[Title] = None
    externalLinks: list[ExternalLink] = Field(default_factory=list)


# ============================================================================
# Tournament
# ============================================================================

class Tournament(BaseModel):
    """A tournament in GRID."""
    id: str
    name: str
    nameShortened: str = Field(description="Max 30 characters")
    logoUrl: str = ""
    startDate: Optional[date] = None
    endDate: Optional[date] = None
    prizePool: Optional[Money] = None
    private: bool = False
    venueType: TournamentVenueType = TournamentVenueType.UNKNOWN
    updatedAt: Optional[datetime] = None
    parent: Optional["Tournament"] = None
    children: list["Tournament"] = Field(default_factory=list)
    titles: list[Title] = Field(default_factory=list)
    teams: list[Team] = Field(default_factory=list)
    externalLinks: list[ExternalLink] = Field(default_factory=list)


# Enable forward references for Tournament self-reference
Tournament.model_rebuild()


# ============================================================================
# Series Format
# ============================================================================

class SeriesFormat(BaseModel):
    """Series format (e.g., BO1, BO3, BO5)."""
    id: Optional[str] = None
    name: str
    nameShortened: str = Field(description="Max 5 characters")


# ============================================================================
# Product Service Level
# ============================================================================

class ProductServiceLevel(BaseModel):
    """Availability of a product for a series."""
    productName: str
    serviceLevel: ServiceLevel


# ============================================================================
# Video Stream
# ============================================================================

class VideoStream(BaseModel):
    """Live video stream details."""
    url: str


# ============================================================================
# Team Participant (in Series)
# ============================================================================

class TeamParticipant(BaseModel):
    """Team participating in a series."""
    baseInfo: Team
    scoreAdvantage: int = 0


# ============================================================================
# Series
# ============================================================================

class Series(BaseModel):
    """A series (match) in GRID."""
    id: str
    startTimeScheduled: datetime
    updatedAt: Optional[datetime] = None
    type: SeriesType = SeriesType.ESPORTS
    private: bool = False
    title: Title
    tournament: Tournament
    format: SeriesFormat
    teams: list[TeamParticipant] = Field(default_factory=list)
    players: list[Player] = Field(default_factory=list)
    productServiceLevels: list[ProductServiceLevel] = Field(default_factory=list)
    streams: list[VideoStream] = Field(default_factory=list)
    externalLinks: list[ExternalLink] = Field(default_factory=list)


# ============================================================================
# Pagination
# ============================================================================

class PageInfo(BaseModel):
    """Pagination information."""
    hasPreviousPage: bool
    hasNextPage: bool
    startCursor: Optional[str] = None
    endCursor: Optional[str] = None


class PlayerEdge(BaseModel):
    """Player with cursor for pagination."""
    cursor: str
    node: Player


class PlayerConnection(BaseModel):
    """Paginated player results."""
    totalCount: int
    edges: list[PlayerEdge]
    pageInfo: PageInfo


class TeamEdge(BaseModel):
    """Team with cursor for pagination."""
    cursor: str
    node: Team


class TeamConnection(BaseModel):
    """Paginated team results."""
    totalCount: int
    edges: list[TeamEdge]
    pageInfo: PageInfo


class SeriesEdge(BaseModel):
    """Series with cursor for pagination."""
    cursor: str
    node: Series


class SeriesConnection(BaseModel):
    """Paginated series results."""
    totalCount: int
    edges: list[SeriesEdge]
    pageInfo: PageInfo


class TournamentEdge(BaseModel):
    """Tournament with cursor for pagination."""
    cursor: str
    node: Tournament


class TournamentConnection(BaseModel):
    """Paginated tournament results."""
    totalCount: int
    edges: list[TournamentEdge]
    pageInfo: PageInfo


class OrganizationEdge(BaseModel):
    """Organization with cursor for pagination."""
    cursor: str
    node: Organization


class OrganizationConnection(BaseModel):
    """Paginated organization results."""
    totalCount: int
    edges: list[OrganizationEdge]
    pageInfo: PageInfo
