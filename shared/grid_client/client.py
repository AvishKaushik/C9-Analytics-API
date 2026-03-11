"""Base GraphQL client for GRID API.

NOTE: The GraphQL queries in this module use placeholder field names.
You MUST update the queries to match the actual GRID API schema.
Consult your GRID API documentation at https://docs.grid.gg for correct field names.

To use mock data mode for development without the real API:
    SET USE_MOCK_DATA=true in your environment
"""

import os
import json
import logging
import asyncio
from pathlib import Path
from typing import Any, Optional
from functools import lru_cache
from dotenv import load_dotenv

# Load .env from multiple possible locations
_current_file = Path(__file__).resolve()
_project_root = _current_file.parent.parent.parent  # shared/grid_client/client.py -> project root
_env_paths = [
    _project_root / ".env",
    Path.cwd() / ".env",
    Path.cwd().parent / ".env",
]
for _env_path in _env_paths:
    if _env_path.exists():
        load_dotenv(_env_path, override=True)  # Override existing env vars
        break
else:
    load_dotenv(override=True)  # Try default locations

logger = logging.getLogger(__name__)


class GridClientError(Exception):
    """Exception raised for GRID API errors."""
    pass


class GridClient:
    """Async GraphQL client for GRID esports API.

    GRID has two main APIs:
    - Central Data API: Team/player metadata, series IDs
    - Series State API: Actual match statistics and player performance

    Set USE_MOCK_DATA=true environment variable to use mock data instead of real API.

    Authentication methods (set GRID_AUTH_METHOD env var):
    - "x-api-key" (default): Uses x-api-key header
    - "bearer": Uses Authorization: Bearer header
    """

    CENTRAL_DATA_URL = "https://api-op.grid.gg/central-data/graphql"
    SERIES_STATE_URL = "https://api-op.grid.gg/live-data-feed/series-state/graphql"

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://api-op.grid.gg/central-data/graphql",
        use_mock: Optional[bool] = None,
        mock_data_path: Optional[str] = None,
        auth_method: Optional[str] = None,
    ):
        self.api_key = api_key or os.getenv("GRID_API_KEY", "")
        self.base_url = base_url

        # Determine mock mode: explicit param > env var > default False
        if use_mock is not None:
            self.use_mock = use_mock
        else:
            env_mock = os.getenv("USE_MOCK_DATA", "false").lower()
            self.use_mock = env_mock == "true"

        self.mock_data_path = mock_data_path
        self.auth_method = auth_method or os.getenv("GRID_AUTH_METHOD", "x-api-key")
        self._client = None
        self._series_state_client = None
        self._cache: dict[str, Any] = {}
        self._mock_data: dict[str, Any] = {}
        self._client_lock = asyncio.Lock()
        # Limit concurrent requests to GRID API to prevent rate limiting/race conditions
        self._semaphore = asyncio.Semaphore(3)

        logger.info(f"GridClient initialized: use_mock={self.use_mock}, USE_MOCK_DATA env={os.getenv('USE_MOCK_DATA')}")

        if self.use_mock:
            self._load_mock_data()
            logger.info("Mock data loaded")

    def _load_mock_data(self) -> None:
        """Load mock data from JSON files."""
        # Default mock data
        self._mock_data = {
            "player": self._get_default_player_mock(),
            "team": self._get_default_team_mock(),
            "match": self._get_default_match_mock(),
        }

        # Try to load from files if path provided
        if self.mock_data_path:
            mock_path = Path(self.mock_data_path)
            if mock_path.exists():
                for json_file in mock_path.glob("*.json"):
                    try:
                        with open(json_file) as f:
                            data = json.load(f)
                            self._mock_data.update(data)
                    except Exception as e:
                        logger.warning(f"Failed to load mock data from {json_file}: {e}")

    def _build_headers(self) -> dict[str, str]:
        """Build authentication headers based on auth method."""
        headers = {"Content-Type": "application/json"}

        if self.auth_method == "bearer":
            headers["Authorization"] = f"Bearer {self.api_key}"
        else:  # default to x-api-key
            headers["x-api-key"] = self.api_key

        return headers

    async def _get_client(self, url: Optional[str] = None):
        """Get or create the GraphQL client for specified URL."""
        target_url = url or self.base_url

        # Use lock to prevent race conditions when creating clients
        async with self._client_lock:
            # Use different client instances for different endpoints
            if target_url == self.SERIES_STATE_URL:
                if self._series_state_client is None:
                    self._series_state_client = await self._create_client(target_url)
                return self._series_state_client
            else:
                if self._client is None:
                    self._client = await self._create_client(target_url)
                return self._client

    async def _create_client(self, url: str):
        """Create a new GraphQL client for the specified URL."""
        try:
            from gql import Client
            from gql.transport.httpx import HTTPXAsyncTransport

            headers = self._build_headers()
            logger.debug(f"Creating client for URL: {url}")

            transport = HTTPXAsyncTransport(
                url=url,
                headers=headers,
                timeout=30.0,
            )
            return Client(
                transport=transport,
                fetch_schema_from_transport=False,
            )
        except ImportError:
            raise GridClientError("gql library not installed. Run: pip install gql[httpx]")

    async def execute(
        self,
        query: str,
        variables: Optional[dict[str, Any]] = None,
        cache_key: Optional[str] = None,
        use_series_state: bool = False,
    ) -> dict[str, Any]:
        """Execute a GraphQL query.

        Args:
            query: GraphQL query string
            variables: Query variables
            cache_key: Optional cache key for response caching
            use_series_state: If True, use Series State API instead of Central Data API

        Returns:
            Query result as dictionary
        """
        # Return mock data if enabled
        if self.use_mock:
            return self._get_mock_response(query, variables)

        if cache_key and cache_key in self._cache:
            return self._cache[cache_key]

        target_url = self.SERIES_STATE_URL if use_series_state else self.base_url

        # Use semaphore to limit concurrent requests to GRID API
        async with self._semaphore:
            try:
                from gql import gql, Client
                from gql.transport.httpx import HTTPXAsyncTransport

                # Create fresh transport for each request to avoid "Transport already connected" errors
                headers = self._build_headers()
                transport = HTTPXAsyncTransport(
                    url=target_url,
                    headers=headers,
                    timeout=30.0,
                )
                client = Client(
                    transport=transport,
                    fetch_schema_from_transport=False,
                )

                async with client as session:
                    result = await session.execute(
                        gql(query),
                        variable_values=variables,
                    )

                if cache_key:
                    self._cache[cache_key] = result

                return result

            except Exception as e:
                error_msg = str(e)
                logger.error(f"GRID API error: {error_msg}")

                # Provide helpful error message for schema mismatches
                if "Cannot query field" in error_msg:
                    raise GridClientError(
                        f"GraphQL schema mismatch: {error_msg}\n\n"
                        "The GRID API schema may have changed. Please:\n"
                        "1. Check your GRID API documentation at https://docs.grid.gg\n"
                        "2. Update the queries in shared/grid_client/ to match the actual schema\n"
                        "3. Or set USE_MOCK_DATA=true to use mock data for development"
                    )
                raise GridClientError(f"GRID API error: {error_msg}")

    def _get_mock_response(
        self,
        query: str,
        variables: Optional[dict[str, Any]],
    ) -> dict[str, Any]:
        """Return mock data based on query type."""
        query_lower = query.lower()

        # Handle GetTeams (list)
        if "teams(" in query_lower:
            mock_team = self._mock_data.get("team", {})
            # Always return mock team for ANY search in mock mode
            return {
                "teams": {
                    "totalCount": 1,
                    "edges": [{"node": mock_team}]
                }
            }
        
        # Handle GetTeam (single)
        elif "team(" in query_lower:
            return {"team": self._mock_data.get("team", {})}
            
        # Handle GetSeries/AllSeries
        elif "allseries(" in query_lower:
            mock_match = self._mock_data.get("match", {})
            return {
                "allSeries": {
                    "totalCount": 1,
                    "edges": [{"node": mock_match}]
                }
            }
        elif "series(" in query_lower:
             # GetSeriesState uses series(id:...)
            if "seriesState" in query:
                 return {"series": {"seriesState": self._mock_data.get("match", {})}}
            return {"series": self._mock_data.get("match", {})}

        # Handle Player queries
        elif "player(" in query_lower or "players(" in query_lower:
             return {"player": self._mock_data.get("player", {})}

        return {}

    def _get_default_player_mock(self) -> dict[str, Any]:
        """Get default mock player data."""
        return {
            "id": "player_001",
            "nickname": "MockPlayer",
            "stats": {
                "gamesPlayed": 20,
                "wins": 12,
                "losses": 8,
                "averageKills": 5.5,
                "averageDeaths": 3.2,
                "averageAssists": 7.8,
                "averageCS": 220,
                "averageVisionScore": 35,
                "killParticipation": 0.68,
            },
            "performances": [
                {
                    "match": {"id": "match_001", "startedAt": "2024-01-15T14:00:00Z"},
                    "game": {"id": "game_001", "sequenceNumber": 1},
                    "champion": {"id": "azir", "name": "Azir"},
                    "role": "mid",
                    "kills": 6,
                    "deaths": 2,
                    "assists": 8,
                    "cs": 245,
                    "csPerMinute": 8.2,
                    "gold": 14500,
                    "damageDealt": 28000,
                    "visionScore": 32,
                    "firstBlood": False,
                    "win": True,
                }
            ],
            "championMastery": [
                {
                    "champion": {"id": "azir", "name": "Azir", "role": "mid"},
                    "gamesPlayed": 15,
                    "wins": 10,
                    "losses": 5,
                    "winRate": 0.67,
                    "averageKDA": 4.2,
                },
                {
                    "champion": {"id": "syndra", "name": "Syndra", "role": "mid"},
                    "gamesPlayed": 12,
                    "wins": 7,
                    "losses": 5,
                    "winRate": 0.58,
                    "averageKDA": 3.8,
                },
            ],
        }

    def _get_default_team_mock(self) -> dict[str, Any]:
        """Get default mock team data."""
        return {
            "id": "team_001",
            "name": "Mock Team",
            "shortName": "MT",
            "region": "NA",
            "players": [
                {"id": "p1", "nickname": "TopPlayer", "role": "top", "isActive": True},
                {"id": "p2", "nickname": "JunglePlayer", "role": "jungle", "isActive": True},
                {"id": "p3", "nickname": "MidPlayer", "role": "mid", "isActive": True},
                {"id": "p4", "nickname": "ADCPlayer", "role": "adc", "isActive": True},
                {"id": "p5", "nickname": "SupportPlayer", "role": "support", "isActive": True},
            ],
            "stats": {
                "gamesPlayed": 30,
                "wins": 20,
                "losses": 10,
                "winRate": 0.67,
                "averageGameDuration": 1950,
                "firstBloodRate": 0.55,
                "firstTowerRate": 0.60,
                "firstDragonRate": 0.58,
                "firstHeraldRate": 0.52,
                "firstBaronRate": 0.65,
                "averageDragons": 2.8,
                "averageBarons": 0.7,
                "averageTowers": 7.2,
                "averageKills": 14.5,
                "averageDeaths": 10.2,
            },
            "compositions": [],
            "draftHistory": [],
        }

    def _get_default_match_mock(self) -> dict[str, Any]:
        """Get default mock match data."""
        return {
            "id": "match_001",
            "seriesId": "series_001",
            "startedAt": "2024-01-15T14:00:00Z",
            "endedAt": "2024-01-15T14:35:00Z",
            "games": [
                {
                    "id": "game_001",
                    "sequenceNumber": 1,
                    "duration": 2100,
                    "winner": {"id": "team_001", "name": "Mock Team"},
                    "teams": [
                        {
                            "id": "team_001",
                            "name": "Mock Team",
                            "side": "blue",
                            "score": 1,
                            "objectives": [
                                {"type": "DRAGON", "count": 3},
                                {"type": "BARON", "count": 1},
                            ],
                            "players": [
                                {
                                    "id": "p1",
                                    "nickname": "TopPlayer",
                                    "champion": {"name": "K'Sante"},
                                    "role": "top",
                                    "kills": 3,
                                    "deaths": 2,
                                    "assists": 8,
                                    "cs": 220,
                                    "gold": 12000,
                                    "visionScore": 30,
                                },
                            ],
                        },
                    ],
                    "events": [],
                },
            ],
        }

    def clear_cache(self) -> None:
        """Clear the response cache."""
        self._cache.clear()

    async def close(self) -> None:
        """Close the client connection."""
        if self._client:
            self._client = None


@lru_cache()
def get_grid_client() -> GridClient:
    """Get singleton GridClient instance."""
    return GridClient()
