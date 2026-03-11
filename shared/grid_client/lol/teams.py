"""League of Legends team queries for GRID API.

NOTE: The GRID Central Data API provides team metadata but NOT aggregated stats.
Stats must be computed from Series State API data or stored externally.

Title IDs:
- League of Legends: 3
- VALORANT: 6
"""

from typing import Any, Optional
from ..client import GridClient

# League of Legends title ID in GRID API
LOL_TITLE_ID = "3"


class LoLTeamQueries:
    """Query builder for LoL team data from Central Data API."""

    # Get team info - Hackathon API has limited permissions
    TEAM_INFO_QUERY = """
    query GetTeamInfo($teamId: ID!) {
        team(id: $teamId) {
            id
            name
            nameShortened
            colorPrimary
            colorSecondary
            logoUrl
        }
    }
    """

    # Get multiple teams with filtering - Hackathon API has limited permissions
    TEAMS_LIST_QUERY = """
    query GetTeams($first: Int!, $after: String, $filter: TeamFilter) {
        teams(first: $first, after: $after, filter: $filter) {
            totalCount
            edges {
                cursor
                node {
                    id
                    name
                    nameShortened
                    colorPrimary
                    colorSecondary
                    logoUrl
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

    # Get team's recent series (to find players and match history)
    # Hackathon API has limited permissions
    TEAM_SERIES_QUERY = """
    query GetTeamSeries($teamId: ID!, $first: Int!, $titleIds: [ID!]) {
        allSeries(
            first: $first
            filter: {
                teamIds: { in: [$teamId] }
                titleIds: { in: $titleIds }
                types: [ESPORTS]
            }
            orderBy: StartTimeScheduled
            orderDirection: DESC
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
            pageInfo {
                hasNextPage
                hasPreviousPage
                startCursor
                endCursor
            }
        }
    }
    """

    # Get team by external ID (e.g., from another data provider)
    TEAM_BY_EXTERNAL_ID_QUERY = """
    query GetTeamByExternalId($dataProviderName: String!, $externalTeamId: ID!, $titleId: ID!) {
        teamIdByExternalId(
            dataProviderName: $dataProviderName
            externalTeamId: $externalTeamId
            titleId: $titleId
        )
    }
    """

    def __init__(self, client: GridClient):
        self.client = client

    async def get_team_info(self, team_id: str) -> dict[str, Any]:
        """Get team metadata from Central Data API.

        Returns team with: id, name, nameShortened, colors, logoUrl, rating,
        organization, title(s), externalLinks, private, updatedAt

        NOTE: This does NOT include roster or stats. Use get_team_series()
        to find recent series and extract player rosters from there.
        """
        return await self.client.execute(
            self.TEAM_INFO_QUERY,
            variables={"teamId": team_id},
            cache_key=f"lol_team_{team_id}",
        )

    async def get_teams(
        self,
        limit: int = 20,
        after: Optional[str] = None,
        title_id: Optional[str] = None,
        name_contains: Optional[str] = None,
        organization_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Get multiple teams with filtering and pagination.

        Args:
            limit: Max number of teams to return
            after: Cursor for pagination
            title_id: Filter by title (game) ID
            name_contains: Filter by team name (case-insensitive contains)
            organization_id: Filter by organization ID

        Returns:
            TeamConnection with edges containing Team nodes
        """
        # Build filter
        filter_obj = {}
        if title_id:
            filter_obj["titleId"] = title_id
        if name_contains:
            filter_obj["name"] = {"contains": name_contains}
        if organization_id:
            filter_obj["organizationId"] = organization_id

        variables = {"first": limit}
        if after:
            variables["after"] = after
        if filter_obj:
            variables["filter"] = filter_obj

        return await self.client.execute(
            self.TEAMS_LIST_QUERY,
            variables=variables,
        )

    async def get_team_series(
        self,
        team_id: str,
        limit: int = 20,
        title_ids: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """Get recent series for a team.

        This is the primary way to get:
        - Team's match history
        - Current roster (from players in recent series)
        - Tournament participation

        Args:
            team_id: GRID team ID
            limit: Max number of series to return
            title_ids: Filter by title IDs (defaults to LoL = "3")

        Returns:
            SeriesConnection with edges containing Series nodes
        """
        if title_ids is None:
            title_ids = [LOL_TITLE_ID]

        return await self.client.execute(
            self.TEAM_SERIES_QUERY,
            variables={
                "teamId": team_id,
                "first": limit,
                "titleIds": title_ids,
            },
        )

    async def get_team_by_external_id(
        self,
        data_provider: str,
        external_id: str,
        title_id: str = LOL_TITLE_ID,
    ) -> dict[str, Any]:
        """Get GRID team ID by external provider's ID.

        Args:
            data_provider: Name of data provider (e.g., "RIOT", "STEAM")
            external_id: ID used by the external provider
            title_id: Title ID for the game

        Returns:
            GRID team ID if found
        """
        return await self.client.execute(
            self.TEAM_BY_EXTERNAL_ID_QUERY,
            variables={
                "dataProviderName": data_provider,
                "externalTeamId": external_id,
                "titleId": title_id,
            },
        )

    async def get_team_roster(self, team_id: str, limit: int = 5) -> dict[str, Any]:
        """Get team's current roster from recent series.

        This extracts unique players from the team's recent series participations.

        Args:
            team_id: GRID team ID
            limit: Number of recent series to check for players

        Returns:
            Dict with team info and players list
        """
        # Get team info
        team_info = await self.get_team_info(team_id)
        team_data = team_info.get("team", {})

        # Get recent series to extract players
        series_response = await self.get_team_series(team_id, limit=limit)
        edges = series_response.get("allSeries", {}).get("edges", [])

        # Extract unique players from series
        players_seen = {}
        for edge in edges:
            series = edge.get("node", {})
            for player in series.get("players", []):
                player_id = player.get("id")
                if player_id and player_id not in players_seen:
                    players_seen[player_id] = {
                        "id": player_id,
                        "nickname": player.get("nickname"),
                        "roles": player.get("roles", []),
                    }

        return {
            "team": {
                **team_data,
                "players": list(players_seen.values()),
            }
        }

    # Legacy method aliases for backwards compatibility
    async def get_team_stats(
        self,
        team_id: str,
        match_ids: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """DEPRECATED: Stats not available from Central Data API.

        Use get_team_series() and compute stats from Series State API data.
        """
        import warnings
        warnings.warn(
            "get_team_stats() is deprecated. Stats must be computed from Series State API data.",
            DeprecationWarning,
        )
        return await self.get_team_info(team_id)

    async def get_team_compositions(
        self,
        team_id: str,
        match_ids: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """DEPRECATED: Compositions not available from Central Data API.

        Use get_team_series() and compute compositions from Series State API data.
        """
        import warnings
        warnings.warn(
            "get_team_compositions() is deprecated. Compositions must be computed from Series State API data.",
            DeprecationWarning,
        )
        return await self.get_team_info(team_id)

    async def get_draft_history(
        self,
        team_id: str,
        limit: int = 50,
    ) -> dict[str, Any]:
        """DEPRECATED: Draft history not available from Central Data API.

        Use get_team_series() and fetch draft data from Series State API.
        """
        import warnings
        warnings.warn(
            "get_draft_history() is deprecated. Draft history must be fetched from Series State API.",
            DeprecationWarning,
        )
        return await self.get_team_series(team_id, limit=limit)
