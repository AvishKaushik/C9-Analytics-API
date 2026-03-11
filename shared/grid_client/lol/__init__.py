"""League of Legends specific GRID API queries.

Title ID: 3

Usage:
    from shared.grid_client import GridClient
    from shared.grid_client.lol import LoLPlayerQueries, LoLTeamQueries, LoLMatchQueries

    client = GridClient(api_key="your-api-key")
    player_queries = LoLPlayerQueries(client)
    player_info = await player_queries.get_player_info("player-id")
"""

from .matches import LoLMatchQueries
from .players import LoLPlayerQueries, LOL_TITLE_ID
from .teams import LoLTeamQueries

__all__ = [
    "LoLMatchQueries",
    "LoLPlayerQueries",
    "LoLTeamQueries",
    "LOL_TITLE_ID",
]
