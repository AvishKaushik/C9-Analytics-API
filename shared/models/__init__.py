"""Shared Pydantic models for esports analytics.

This package contains two types of models:

1. **API Response Models** (grid_api.py):
   Models that match the GRID API schema for deserializing API responses.

2. **Computed Stats Models** (lol.py, valorant.py):
   Models for aggregated statistics computed from Series State API data.
"""

# API Response Models (match GRID API schema)
from .grid_api import (
    # Enums
    SeriesType,
    ServiceLevel,
    TournamentVenueType,
    OrderDirection,
    # Common types
    Nationality,
    ExternalEntity,
    DataProvider,
    ExternalLink,
    Money,
    # Core entities
    Title,
    PlayerRole,
    Team,
    TeamRelation,
    OrganizationRelation,
    Organization,
    Player,
    Tournament,
    SeriesFormat,
    ProductServiceLevel,
    VideoStream,
    TeamParticipant,
    Series,
    # Pagination
    PageInfo,
    PlayerEdge,
    PlayerConnection,
    TeamEdge,
    TeamConnection,
    SeriesEdge,
    SeriesConnection,
    TournamentEdge,
    TournamentConnection,
    OrganizationEdge,
    OrganizationConnection,
)

# LoL Computed Stats Models
from .lol import (
    LoLMatch,
    LoLGame,
    LoLPlayer,
    LoLPlayerPerformance,
    LoLTeam,
    LoLTeamStats,
    LoLTeamGameStats,
    LoLDraftState,
    LoLDraftPick,
    LoLChampion,
    LoLObjective,
    LoLItem,
    LoLComposition,
    Role,
    Side,
    ObjectiveType,
)

# VALORANT Computed Stats Models
from .valorant import (
    ValorantMatch,
    ValorantGame,
    ValorantPlayer,
    ValorantPlayerPerformance,
    ValorantTeam,
    ValorantTeamStats,
    ValorantTeamGameStats,
    ValorantRound,
    ValorantRoundEconomy,
    ValorantPlant,
    ValorantDefuse,
    ValorantAgent,
    ValorantMap,
    ValorantMapStats,
    ValorantComposition,
    ValorantDefaultSetup,
    AgentRole,
    WinCondition,
    EconomyType,
)
# Valorant Side enum is imported as ValorantSide to avoid conflict with LoL Side
from .valorant import Side as ValorantSide

__all__ = [
    # ============ API Response Models ============
    # Enums
    "SeriesType",
    "ServiceLevel",
    "TournamentVenueType",
    "OrderDirection",
    # Common types
    "Nationality",
    "ExternalEntity",
    "DataProvider",
    "ExternalLink",
    "Money",
    # Core entities
    "Title",
    "PlayerRole",
    "Team",
    "TeamRelation",
    "OrganizationRelation",
    "Organization",
    "Player",
    "Tournament",
    "SeriesFormat",
    "ProductServiceLevel",
    "VideoStream",
    "TeamParticipant",
    "Series",
    # Pagination
    "PageInfo",
    "PlayerEdge",
    "PlayerConnection",
    "TeamEdge",
    "TeamConnection",
    "SeriesEdge",
    "SeriesConnection",
    "TournamentEdge",
    "TournamentConnection",
    "OrganizationEdge",
    "OrganizationConnection",
    # ============ LoL Computed Stats Models ============
    "LoLMatch",
    "LoLGame",
    "LoLPlayer",
    "LoLPlayerPerformance",
    "LoLTeam",
    "LoLTeamStats",
    "LoLTeamGameStats",
    "LoLDraftState",
    "LoLDraftPick",
    "LoLChampion",
    "LoLObjective",
    "LoLItem",
    "LoLComposition",
    "Role",
    "Side",
    "ObjectiveType",
    # ============ VALORANT Computed Stats Models ============
    "ValorantMatch",
    "ValorantGame",
    "ValorantPlayer",
    "ValorantPlayerPerformance",
    "ValorantTeam",
    "ValorantTeamStats",
    "ValorantTeamGameStats",
    "ValorantRound",
    "ValorantRoundEconomy",
    "ValorantPlant",
    "ValorantDefuse",
    "ValorantAgent",
    "ValorantMap",
    "ValorantMapStats",
    "ValorantComposition",
    "ValorantDefaultSetup",
    "AgentRole",
    "ValorantSide",
    "WinCondition",
    "EconomyType",
]
