"""Common/shared queries for GRID API.

These queries work across all titles (games) and provide access to:
- Tournaments
- Organizations
- Titles (games)
- Player roles
- Data providers
- Series formats
"""

from typing import Any, Optional
from .client import GridClient


class TournamentQueries:
    """Query builder for tournament data."""

    # Hackathon API has limited permissions
    TOURNAMENT_INFO_QUERY = """
    query GetTournamentInfo($tournamentId: ID!) {
        tournament(id: $tournamentId) {
            id
            name
            nameShortened
            logoUrl
            startDate
            endDate
            venueType
        }
    }
    """

    # Hackathon API has limited permissions
    TOURNAMENTS_LIST_QUERY = """
    query GetTournaments(
        $first: Int!
        $after: String
        $filter: TournamentFilter
    ) {
        tournaments(first: $first, after: $after, filter: $filter) {
            totalCount
            edges {
                cursor
                node {
                    id
                    name
                    nameShortened
                    logoUrl
                    startDate
                    endDate
                    venueType
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

    TOURNAMENT_BY_EXTERNAL_ID_QUERY = """
    query GetTournamentByExternalId($dataProviderName: String!, $externalTournamentId: ID!) {
        tournamentIdByExternalId(
            dataProviderName: $dataProviderName
            externalTournamentId: $externalTournamentId
        )
    }
    """

    def __init__(self, client: GridClient):
        self.client = client

    async def get_tournament(self, tournament_id: str) -> dict[str, Any]:
        """Get tournament info by ID.

        Returns tournament with: id, name, dates, prizePool, titles, teams,
        parent/children hierarchy, venueType, externalLinks
        """
        return await self.client.execute(
            self.TOURNAMENT_INFO_QUERY,
            variables={"tournamentId": tournament_id},
            cache_key=f"tournament_{tournament_id}",
        )

    async def get_tournaments(
        self,
        limit: int = 20,
        after: Optional[str] = None,
        title_ids: Optional[list[str]] = None,
        name_contains: Optional[str] = None,
        start_date_gte: Optional[str] = None,
        start_date_lte: Optional[str] = None,
        end_date_gte: Optional[str] = None,
        end_date_lte: Optional[str] = None,
        venue_types: Optional[list[str]] = None,
        has_parent: Optional[bool] = None,
        has_children: Optional[bool] = None,
    ) -> dict[str, Any]:
        """Get tournaments with filtering and pagination.

        Args:
            limit: Max number of tournaments to return
            after: Cursor for pagination
            title_ids: Filter by title (game) IDs
            name_contains: Filter by name (case-insensitive contains)
            start_date_gte: Filter by start date >= (ISO date)
            start_date_lte: Filter by start date <= (ISO date)
            end_date_gte: Filter by end date >= (ISO date)
            end_date_lte: Filter by end date <= (ISO date)
            venue_types: Filter by venue types (ONLINE, LAN, HYBRID, UNKNOWN)
            has_parent: Filter tournaments that have/don't have parents
            has_children: Filter tournaments that have/don't have children

        Returns:
            TournamentConnection with edges containing Tournament nodes
        """
        filter_obj = {}

        if title_ids:
            filter_obj["title"] = {"id": {"in": title_ids}}
        if name_contains:
            filter_obj["name"] = {"contains": name_contains}
        if venue_types:
            filter_obj["venueType"] = venue_types
        if has_parent is not None:
            filter_obj["hasParent"] = {"equals": has_parent}
        if has_children is not None:
            filter_obj["hasChildren"] = {"equals": has_children}

        # Date filters
        if start_date_gte or start_date_lte:
            filter_obj["startDate"] = {}
            if start_date_gte:
                filter_obj["startDate"]["gte"] = start_date_gte
            if start_date_lte:
                filter_obj["startDate"]["lte"] = start_date_lte

        if end_date_gte or end_date_lte:
            filter_obj["endDate"] = {}
            if end_date_gte:
                filter_obj["endDate"]["gte"] = end_date_gte
            if end_date_lte:
                filter_obj["endDate"]["lte"] = end_date_lte

        variables = {"first": limit}
        if after:
            variables["after"] = after
        if filter_obj:
            variables["filter"] = filter_obj

        return await self.client.execute(
            self.TOURNAMENTS_LIST_QUERY,
            variables=variables,
        )

    async def get_tournament_by_external_id(
        self,
        data_provider: str,
        external_id: str,
    ) -> dict[str, Any]:
        """Get GRID tournament ID by external provider's ID."""
        return await self.client.execute(
            self.TOURNAMENT_BY_EXTERNAL_ID_QUERY,
            variables={
                "dataProviderName": data_provider,
                "externalTournamentId": external_id,
            },
        )


class OrganizationQueries:
    """Query builder for organization data."""

    # Hackathon API has limited permissions
    ORGANIZATION_INFO_QUERY = """
    query GetOrganizationInfo($organizationId: ID!) {
        organization(id: $organizationId) {
            id
            name
            teams {
                id
                name
                logoUrl
            }
        }
    }
    """

    # Hackathon API has limited permissions
    ORGANIZATIONS_LIST_QUERY = """
    query GetOrganizations(
        $first: Int!
        $after: String
        $filter: OrganizationFilter
    ) {
        organizations(first: $first, after: $after, filter: $filter) {
            totalCount
            edges {
                cursor
                node {
                    id
                    name
                    teams {
                        id
                        name
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

    def __init__(self, client: GridClient):
        self.client = client

    async def get_organization(self, organization_id: str) -> dict[str, Any]:
        """Get organization info by ID.

        Returns organization with: id, name, teams (with all details)
        """
        return await self.client.execute(
            self.ORGANIZATION_INFO_QUERY,
            variables={"organizationId": organization_id},
            cache_key=f"organization_{organization_id}",
        )

    async def get_organizations(
        self,
        limit: int = 20,
        after: Optional[str] = None,
        name_contains: Optional[str] = None,
    ) -> dict[str, Any]:
        """Get organizations with filtering and pagination.

        Args:
            limit: Max number of organizations to return
            after: Cursor for pagination
            name_contains: Filter by name (case-insensitive contains)

        Returns:
            OrganizationConnection with edges containing Organization nodes
        """
        filter_obj = {}
        if name_contains:
            filter_obj["name"] = {"contains": name_contains}

        variables = {"first": limit}
        if after:
            variables["after"] = after
        if filter_obj:
            variables["filter"] = filter_obj

        return await self.client.execute(
            self.ORGANIZATIONS_LIST_QUERY,
            variables=variables,
        )


class TitleQueries:
    """Query builder for title (game) data."""

    # Hackathon API has limited permissions
    TITLE_INFO_QUERY = """
    query GetTitleInfo($titleId: ID!) {
        title(id: $titleId) {
            id
            name
            nameShortened
        }
    }
    """

    # Hackathon API has limited permissions
    TITLES_LIST_QUERY = """
    query GetTitles($filter: TitleFilter) {
        titles(filter: $filter) {
            id
            name
            nameShortened
        }
    }
    """

    def __init__(self, client: GridClient):
        self.client = client

    async def get_title(self, title_id: str) -> dict[str, Any]:
        """Get title (game) info by ID.

        Known title IDs:
        - League of Legends: 3
        - VALORANT: 6
        """
        return await self.client.execute(
            self.TITLE_INFO_QUERY,
            variables={"titleId": title_id},
            cache_key=f"title_{title_id}",
        )

    async def get_titles(self, include_private: bool = False) -> dict[str, Any]:
        """Get all available titles (games).

        Args:
            include_private: Whether to include private/hidden titles

        Returns:
            List of Title objects
        """
        filter_obj = {}
        if not include_private:
            filter_obj["private"] = {"equals": False}

        variables = {}
        if filter_obj:
            variables["filter"] = filter_obj

        return await self.client.execute(
            self.TITLES_LIST_QUERY,
            variables=variables if variables else None,
        )


class PlayerRoleQueries:
    """Query builder for player role data."""

    # Hackathon API has limited permissions
    PLAYER_ROLE_INFO_QUERY = """
    query GetPlayerRoleInfo($roleId: ID!) {
        playerRole(id: $roleId) {
            id
            name
        }
    }
    """

    # Hackathon API has limited permissions
    PLAYER_ROLES_LIST_QUERY = """
    query GetPlayerRoles($filter: PlayerRoleFilter) {
        playerRoles(filter: $filter) {
            id
            name
        }
    }
    """

    def __init__(self, client: GridClient):
        self.client = client

    async def get_player_role(self, role_id: str) -> dict[str, Any]:
        """Get player role by ID."""
        return await self.client.execute(
            self.PLAYER_ROLE_INFO_QUERY,
            variables={"roleId": role_id},
        )

    async def get_player_roles(
        self,
        title_ids: Optional[list[str]] = None,
        name_contains: Optional[str] = None,
    ) -> dict[str, Any]:
        """Get player roles with optional filtering.

        Args:
            title_ids: Filter by title (game) IDs
            name_contains: Filter by role name

        Returns:
            List of PlayerRole objects
        """
        filter_obj = {}
        if title_ids:
            filter_obj["title"] = {"id": {"in": title_ids}}
        if name_contains:
            filter_obj["name"] = {"contains": name_contains}

        variables = {}
        if filter_obj:
            variables["filter"] = filter_obj

        return await self.client.execute(
            self.PLAYER_ROLES_LIST_QUERY,
            variables=variables if variables else None,
        )


class DataProviderQueries:
    """Query builder for data provider info."""

    DATA_PROVIDERS_QUERY = """
    query GetDataProviders {
        dataProviders {
            name
            description
        }
    }
    """

    SERIES_FORMATS_QUERY = """
    query GetSeriesFormats {
        seriesFormats {
            id
            name
            nameShortened
        }
    }
    """

    def __init__(self, client: GridClient):
        self.client = client

    async def get_data_providers(self) -> dict[str, Any]:
        """Get list of supported external data providers.

        Examples: RIOT, STEAM, etc.
        """
        return await self.client.execute(
            self.DATA_PROVIDERS_QUERY,
            cache_key="data_providers",
        )

    async def get_series_formats(self) -> dict[str, Any]:
        """Get list of supported series formats.

        Examples: BO1, BO3, BO5, etc.
        """
        return await self.client.execute(
            self.SERIES_FORMATS_QUERY,
            cache_key="series_formats",
        )


class PlayersQueries:
    """Query builder for player list queries (cross-title)."""

    # Hackathon API has limited permissions
    PLAYERS_LIST_QUERY = """
    query GetPlayers(
        $first: Int!
        $after: String
        $filter: PlayerFilter
    ) {
        players(first: $first, after: $after, filter: $filter) {
            totalCount
            edges {
                cursor
                node {
                    id
                    nickname
                    roles {
                        id
                        name
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

    PLAYER_BY_EXTERNAL_ID_QUERY = """
    query GetPlayerByExternalId($dataProviderName: String!, $externalPlayerId: ID!, $titleId: ID) {
        playerIdByExternalId(
            dataProviderName: $dataProviderName
            externalPlayerId: $externalPlayerId
            titleId: $titleId
        )
    }
    """

    def __init__(self, client: GridClient):
        self.client = client

    async def get_players(
        self,
        limit: int = 20,
        after: Optional[str] = None,
        title_id: Optional[str] = None,
        nickname_contains: Optional[str] = None,
    ) -> dict[str, Any]:
        """Get players with filtering and pagination.

        Note: Hackathon API has limited permissions, so only basic filters work.

        Args:
            limit: Max number of players to return
            after: Cursor for pagination
            title_id: Filter by title (game) ID
            nickname_contains: Filter by nickname (case-insensitive)

        Returns:
            PlayerConnection with edges containing Player nodes
        """
        filter_obj = {}

        if title_id:
            filter_obj["titleId"] = title_id
        if nickname_contains:
            filter_obj["nickname"] = {"contains": nickname_contains}

        variables = {"first": limit}
        if after:
            variables["after"] = after
        if filter_obj:
            variables["filter"] = filter_obj

        return await self.client.execute(
            self.PLAYERS_LIST_QUERY,
            variables=variables,
        )

    async def get_player_by_external_id(
        self,
        data_provider: str,
        external_id: str,
        title_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Get GRID player ID by external provider's ID.

        Args:
            data_provider: Name of data provider (e.g., "RIOT", "STEAM")
            external_id: ID used by the external provider
            title_id: Optional title ID to narrow the search

        Returns:
            GRID player ID if found
        """
        variables = {
            "dataProviderName": data_provider,
            "externalPlayerId": external_id,
        }
        if title_id:
            variables["titleId"] = title_id

        return await self.client.execute(
            self.PLAYER_BY_EXTERNAL_ID_QUERY,
            variables=variables,
        )
