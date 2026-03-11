"""VALORANT match/series queries for GRID API.

NOTE: In GRID API, matches are called "Series". A Series contains multiple Games (maps).
- Central Data API: Series metadata (teams, tournament, schedule)
- Series State API: Detailed game stats (player performance, rounds, economy)

Title IDs:
- League of Legends: 3
- VALORANT: 6
"""

from typing import Any, Optional
from ..client import GridClient

# VALORANT title ID in GRID API
VALORANT_TITLE_ID = "6"


class ValorantMatchQueries:
    """Query builder for VALORANT match/series data."""

    # Central Data API: Get series metadata
    # Hackathon API has limited permissions
    SERIES_INFO_QUERY = """
    query GetSeriesInfo($seriesId: ID!) {
        series(id: $seriesId) {
            id
            startTimeScheduled
            type
            title {
                id
                name
            }
            tournament {
                id
                name
            }
            format {
                name
                nameShortened
            }
            teams {
                baseInfo {
                    id
                    name
                    logoUrl
                }
                scoreAdvantage
            }
            players {
                id
                nickname
                roles {
                    id
                    name
                }
            }
        }
    }
    """

    # Central Data API: Get multiple series with filtering
    # Hackathon API has limited permissions
    SERIES_LIST_QUERY = """
    query GetSeriesList(
        $first: Int!
        $after: String
        $filter: SeriesFilter
        $orderBy: SeriesOrderBy!
        $orderDirection: OrderDirection!
    ) {
        allSeries(
            first: $first
            after: $after
            filter: $filter
            orderBy: $orderBy
            orderDirection: $orderDirection
        ) {
            totalCount
            edges {
                cursor
                node {
                    id
                    startTimeScheduled
                    type
                    title {
                        id
                        name
                    }
                    tournament {
                        id
                        name
                    }
                    format {
                        name
                        nameShortened
                    }
                    teams {
                        baseInfo {
                            id
                            name
                            logoUrl
                        }
                        scoreAdvantage
                    }
                }
            }
            pageInfo {
                hasNextPage
                hasPreviousPage
                startCursor
                endCursor
            }
        }
    }
    """

    # Central Data API: Get series ID by external ID
    SERIES_BY_EXTERNAL_ID_QUERY = """
    query GetSeriesByExternalId($dataProviderName: String!, $externalSeriesId: ID!) {
        seriesIdByExternalId(
            dataProviderName: $dataProviderName
            externalSeriesId: $externalSeriesId
        )
    }
    """

    # Series State API: Get detailed match stats (requires separate API endpoint)
    # NOTE: map.id requires API version 3.13+, using map.name only
    SERIES_STATE_QUERY = """
    query GetSeriesState($seriesId: ID!) {
        seriesState(id: $seriesId) {
            id
            title {
                nameShortened
            }
            started
            finished
            teams {
                id
                name
                score
                players {
                    id
                    name
                }
            }
            games {
                id
                sequenceNumber
                started
                finished
                map {
                    name
                }
                teams {
                    id
                    name
                    score
                    side
                    players {
                        id
                        name
                        character {
                            id
                            name
                        }
                        kills
                        deaths
                        killAssistsGiven
                        netWorth
                        ... on GamePlayerStateValorant {
                            headshots
                            damageDealt
                            damageTaken
                            objectives {
                                type
                                completionCount
                            }
                        }
                    }
                }
            }
        }
    }
    """

    def __init__(self, client: GridClient):
        self.client = client

    async def get_series_info(self, series_id: str) -> dict[str, Any]:
        """Get series metadata from Central Data API.

        Returns series with: id, teams, tournament, format, players, schedule,
        productServiceLevels, streams, externalLinks

        NOTE: For detailed game stats (kills, deaths, rounds), use
        get_series_state() which queries the Series State API.
        """
        return await self.client.execute(
            self.SERIES_INFO_QUERY,
            variables={"seriesId": series_id},
            cache_key=f"val_series_{series_id}",
        )

    async def get_series_list(
        self,
        limit: int = 20,
        after: Optional[str] = None,
        team_ids: Optional[list[str]] = None,
        title_ids: Optional[list[str]] = None,
        tournament_ids: Optional[list[str]] = None,
        player_ids: Optional[list[str]] = None,
        start_time_gte: Optional[str] = None,
        start_time_lte: Optional[str] = None,
        series_types: Optional[list[str]] = None,
        order_by: str = "StartTimeScheduled",
        order_direction: str = "DESC",
    ) -> dict[str, Any]:
        """Get multiple series with filtering and pagination.

        Args:
            limit: Max number of series to return
            after: Cursor for pagination
            team_ids: Filter by team IDs
            title_ids: Filter by title IDs (defaults to VALORANT = "6")
            tournament_ids: Filter by tournament IDs
            player_ids: Filter by participating player IDs
            start_time_gte: Filter by scheduled start time >= (ISO datetime)
            start_time_lte: Filter by scheduled start time <= (ISO datetime)
            series_types: Filter by types (ESPORTS, SCRIM, COMPETITIVE, LOOPFEED)
            order_by: Sort field (ID, StartTimeScheduled, UpdatedAt)
            order_direction: Sort direction (ASC, DESC)

        Returns:
            SeriesConnection with edges containing Series nodes
        """
        # Default to VALORANT title if not specified
        if title_ids is None:
            title_ids = [VALORANT_TITLE_ID]

        # Build filter
        filter_obj = {"titleIds": {"in": title_ids}}

        if team_ids:
            filter_obj["teamIds"] = {"in": team_ids}
        if tournament_ids:
            filter_obj["tournament"] = {"id": {"in": tournament_ids}}
        if player_ids:
            filter_obj["livePlayerIds"] = {"in": player_ids}
        if series_types:
            filter_obj["types"] = series_types
        else:
            filter_obj["types"] = ["ESPORTS"]  # Default to esports

        # Time range filter
        if start_time_gte or start_time_lte:
            filter_obj["startTimeScheduled"] = {}
            if start_time_gte:
                filter_obj["startTimeScheduled"]["gte"] = start_time_gte
            if start_time_lte:
                filter_obj["startTimeScheduled"]["lte"] = start_time_lte

        variables = {
            "first": limit,
            "filter": filter_obj,
            "orderBy": order_by,
            "orderDirection": order_direction,
        }
        if after:
            variables["after"] = after

        return await self.client.execute(
            self.SERIES_LIST_QUERY,
            variables=variables,
        )

    async def get_series_by_external_id(
        self,
        data_provider: str,
        external_id: str,
    ) -> dict[str, Any]:
        """Get GRID series ID by external provider's ID.

        Args:
            data_provider: Name of data provider (e.g., "RIOT", "STEAM")
            external_id: ID used by the external provider

        Returns:
            GRID series ID if found
        """
        return await self.client.execute(
            self.SERIES_BY_EXTERNAL_ID_QUERY,
            variables={
                "dataProviderName": data_provider,
                "externalSeriesId": external_id,
            },
        )

    async def get_series_state(self, series_id: str) -> dict[str, Any]:
        """Get detailed match stats from Series State API.

        This returns the actual game data including:
        - Game-by-game (map) results
        - Player stats (kills, deaths, assists)
        - Agent/character picks
        - Team scores
        - Map information

        NOTE: This uses a different API endpoint (Series State API).
        """
        return await self.client.execute(
            self.SERIES_STATE_QUERY,
            variables={"seriesId": series_id},
            use_series_state=True,
        )

    async def get_matches_by_team(
        self,
        team_id: str,
        limit: int = 20,
        after: Optional[str] = None,
    ) -> dict[str, Any]:
        """Get matches (series) for a specific team with pagination.

        Args:
            team_id: GRID team ID
            limit: Max number of series to return
            after: Cursor for pagination

        Returns:
            SeriesConnection with edges containing Series nodes
        """
        return await self.get_series_list(
            limit=limit,
            after=after,
            team_ids=[team_id],
        )

    async def get_match_with_stats(self, series_id: str) -> dict[str, Any]:
        """Get complete match data including metadata and game stats.

        This combines:
        1. Series metadata from Central Data API
        2. Game stats from Series State API

        Returns:
            Dict with series metadata and game state
        """
        # Fetch both in parallel conceptually (but await sequentially here)
        series_info = await self.get_series_info(series_id)
        series_state = await self.get_series_state(series_id)

        return {
            "series": series_info.get("series", {}),
            "state": series_state.get("seriesState", {}),
        }

    # Legacy method aliases for backwards compatibility
    async def get_match_details(self, match_id: str) -> dict[str, Any]:
        """DEPRECATED: Use get_series_info() or get_match_with_stats() instead.

        In GRID API, 'matches' are called 'series'.
        """
        import warnings
        warnings.warn(
            "get_match_details() is deprecated. Use get_series_info() or get_match_with_stats().",
            DeprecationWarning,
        )
        return await self.get_match_with_stats(match_id)

    async def get_round_details(
        self,
        match_id: str,
        game_number: int,
        round_number: int,
    ) -> dict[str, Any]:
        """DEPRECATED: Round-level data available in Series State API.

        Use get_series_state() to get game-by-game data including rounds.
        """
        import warnings
        warnings.warn(
            "get_round_details() is deprecated. Use get_series_state() instead.",
            DeprecationWarning,
        )
        return await self.get_series_state(match_id)
