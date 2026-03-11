"""VALORANT player queries for GRID API.

Uses both Central Data API (metadata) and Series State API (match stats).

Title IDs:
- League of Legends: 3
- VALORANT: 6
"""

from typing import Any, Optional
from ..client import GridClient

# VALORANT title ID in GRID API
VALORANT_TITLE_ID = "6"


class ValorantPlayerQueries:
    """Query builder for VALORANT player data."""

    # Central Data API: Get player info
    # Note: Hackathon API key only has access to basic fields (id, nickname, roles)
    PLAYER_INFO_QUERY = """
    query GetPlayerInfo($playerId: ID!) {
        player(id: $playerId) {
            id
            nickname
            roles {
                id
                name
            }
        }
    }
    """

    # Central Data API: Get recent series for a player (VALORANT title ID = 6)
    # Hackathon API has limited permissions
    PLAYER_SERIES_QUERY = """
    query GetPlayerSeries($playerId: ID!, $first: Int!, $titleIds: [ID!]) {
        allSeries(
            first: $first
            filter: {
                livePlayerIds: { in: [$playerId] }
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

    # Series State API: Get detailed player stats from a series
    # NOTE: Some fields may require specific API versions
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

    async def get_player_info(self, player_id: str) -> dict[str, Any]:
        """Get player info from Central Data API.

        Returns player with: id, nickname, imageUrl, nationality,
        roles, team, title, externalLinks, private, updatedAt
        """
        return await self.client.execute(
            self.PLAYER_INFO_QUERY,
            variables={"playerId": player_id},
            cache_key=f"val_player_{player_id}",
        )

    async def get_player_series(
        self,
        player_id: str,
        limit: int = 10,
        title_ids: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """Get recent series where player participated.

        Args:
            player_id: GRID player ID
            limit: Max number of series to return
            title_ids: Filter by title IDs (defaults to VALORANT = "6")

        Returns:
            SeriesConnection with edges containing Series nodes
        """
        # Default to VALORANT title ID if not specified
        if title_ids is None:
            title_ids = [VALORANT_TITLE_ID]

        return await self.client.execute(
            self.PLAYER_SERIES_QUERY,
            variables={
                "playerId": player_id,
                "first": limit,
                "titleIds": title_ids,
            },
        )

    async def get_series_state(self, series_id: str) -> dict[str, Any]:
        """Get detailed match stats from Series State API."""
        return await self.client.execute(
            self.SERIES_STATE_QUERY,
            variables={"seriesId": series_id},
            use_series_state=True,
        )

    async def get_player_stats(
        self,
        player_id: str,
        match_ids: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """Get player info. For stats, use get_player_performance instead."""
        return await self.get_player_info(player_id)

    async def get_player_performance(
        self,
        player_id: str,
        match_ids: Optional[list[str]] = None,
        limit: int = 10,
    ) -> dict[str, Any]:
        """Get player performance data across multiple series.

        Args:
            player_id: GRID player ID
            match_ids: Optional list of series IDs to fetch (if None, fetches recent)
            limit: Max number of series to fetch if match_ids not provided

        Returns:
            Dict with player info and performances list
        """
        # Get player info
        player_info = await self.get_player_info(player_id)
        player_data = player_info.get("player", {})

        # Get series IDs and dates
        series_dates = {}  # Map series_id -> date
        if match_ids:
            series_ids = match_ids
        else:
            # Fetch recent series
            series_response = await self.get_player_series(player_id, limit=limit)
            edges = series_response.get("allSeries", {}).get("edges", [])
            series_ids = [edge["node"]["id"] for edge in edges]
            # Store dates for each series
            for edge in edges:
                node = edge.get("node", {})
                series_dates[node.get("id")] = node.get("startTimeScheduled")

        # Fetch stats from each series
        performances = []
        for series_id in series_ids:
            try:
                series_state = await self.get_series_state(series_id)
                state = series_state.get("seriesState", {})

                if not state.get("finished"):
                    continue

                # Extract player's performance from each game
                for game in state.get("games", []):
                    if not game.get("finished"):
                        continue

                    for team in game.get("teams", []):
                        for player in team.get("players", []):
                            # Compare as strings to handle int/string type mismatches
                            if str(player.get("id")) == str(player_id):
                                # Determine if won (team with higher score wins)
                                teams = game.get("teams", [])
                                team_score = team.get("score", 0)
                                opponent_score = max(
                                    (t.get("score", 0) for t in teams if t.get("id") != team.get("id")),
                                    default=0
                                )
                                won = team_score > opponent_score

                                performances.append({
                                    "seriesId": series_id,
                                    "gameId": game.get("id"),
                                    "teamId": team.get("id"),
                                    "teamName": team.get("name"),
                                    "agent": player.get("character", {}),
                                    "kills": player.get("kills", 0),
                                    "deaths": player.get("deaths", 0),
                                    "assists": player.get("killAssistsGiven", 0),
                                    "netWorth": player.get("netWorth", 0),
                                    "win": won,
                                    "date": series_dates.get(series_id),
                                    # Additional Valorant stats from Grid API
                                    "headshots": player.get("headshots", 0),
                                    "damageDealt": player.get("damageDealt", 0),
                                    "damageTaken": player.get("damageTaken", 0),
                                    "objectives": player.get("objectives", []),
                                })
            except Exception as e:
                # Log but continue with other series
                import logging
                logging.getLogger(__name__).warning(f"Failed to fetch series {series_id}: {e}")
                continue

        return {
            "player": {
                **player_data,
                "performances": performances,
            }
        }

    async def get_agent_mastery(self, player_id: str) -> dict[str, Any]:
        """Get player's agent pool and mastery data."""
        # Fetch recent performances and aggregate by agent
        perf_data = await self.get_player_performance(player_id, limit=20)
        performances = perf_data.get("player", {}).get("performances", [])

        # Aggregate by agent
        agent_stats: dict[str, dict] = {}
        for perf in performances:
            agent = perf.get("agent", {})
            agent_id = agent.get("id", "unknown")
            agent_name = agent.get("name", "Unknown")

            if agent_id not in agent_stats:
                agent_stats[agent_id] = {
                    "agent": {"id": agent_id, "name": agent_name},
                    "gamesPlayed": 0,
                    "wins": 0,
                    "losses": 0,
                    "totalKills": 0,
                    "totalDeaths": 0,
                    "totalAssists": 0,
                }

            stats = agent_stats[agent_id]
            stats["gamesPlayed"] += 1
            if perf.get("win"):
                stats["wins"] += 1
            else:
                stats["losses"] += 1
            stats["totalKills"] += perf.get("kills", 0)
            stats["totalDeaths"] += perf.get("deaths", 0)
            stats["totalAssists"] += perf.get("assists", 0)

        # Calculate derived stats
        mastery = []
        for agent_id, stats in agent_stats.items():
            games = stats["gamesPlayed"]
            deaths = stats["totalDeaths"] or 1
            mastery.append({
                "agent": stats["agent"],
                "gamesPlayed": games,
                "wins": stats["wins"],
                "losses": stats["losses"],
                "winRate": stats["wins"] / games if games > 0 else 0,
                "averageKDA": (stats["totalKills"] + stats["totalAssists"]) / deaths,
            })

        return {
            "player": {
                **perf_data.get("player", {}),
                "agentMastery": sorted(mastery, key=lambda x: x["gamesPlayed"], reverse=True),
            }
        }
