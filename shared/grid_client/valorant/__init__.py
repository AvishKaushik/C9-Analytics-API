"""VALORANT specific GRID API queries.

Title ID: 6

Usage:
    from shared.grid_client import GridClient
    from shared.grid_client.valorant import ValorantPlayerQueries, ValorantTeamQueries, ValorantMatchQueries

    client = GridClient(api_key="your-api-key")
    player_queries = ValorantPlayerQueries(client)
    player_info = await player_queries.get_player_info("player-id")
"""

from .matches import ValorantMatchQueries
from .players import ValorantPlayerQueries, VALORANT_TITLE_ID
from .teams import ValorantTeamQueries

__all__ = [
    "ValorantMatchQueries",
    "ValorantPlayerQueries",
    "ValorantTeamQueries",
    "VALORANT_TITLE_ID",
]
