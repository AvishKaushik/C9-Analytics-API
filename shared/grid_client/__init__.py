"""GRID API client for esports data.

This package provides a GraphQL client for the GRID esports API with
specialized query builders for League of Legends and VALORANT.

Usage:
    from shared.grid_client import GridClient
    from shared.grid_client.lol import LoLPlayerQueries, LoLTeamQueries, LoLMatchQueries
    from shared.grid_client.valorant import ValorantPlayerQueries, ValorantTeamQueries, ValorantMatchQueries
    from shared.grid_client.common import TournamentQueries, OrganizationQueries

    # Initialize client
    client = GridClient(api_key="your-api-key")

    # Use query builders
    player_queries = LoLPlayerQueries(client)
    player_info = await player_queries.get_player_info("player-id")

Known Title IDs:
    - League of Legends: 3
    - VALORANT: 6

API Documentation:
    https://docs.grid.gg
"""

from .client import GridClient, GridClientError, get_grid_client
from .common import (
    TournamentQueries,
    OrganizationQueries,
    TitleQueries,
    PlayerRoleQueries,
    DataProviderQueries,
    PlayersQueries,
)

# Title ID constants
LOL_TITLE_ID = "3"
VALORANT_TITLE_ID = "6"

__all__ = [
    # Client
    "GridClient",
    "GridClientError",
    "get_grid_client",
    # Common queries
    "TournamentQueries",
    "OrganizationQueries",
    "TitleQueries",
    "PlayerRoleQueries",
    "DataProviderQueries",
    "PlayersQueries",
    # Constants
    "LOL_TITLE_ID",
    "VALORANT_TITLE_ID",
]
