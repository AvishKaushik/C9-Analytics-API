"""Analytics utilities for statistical analysis."""

from typing import Any, TypeVar
from statistics import mean, stdev, median
from collections import defaultdict

T = TypeVar("T")


def calculate_statistics(values: list[float]) -> dict[str, float]:
    """Calculate basic statistics for a list of values.

    Args:
        values: List of numeric values

    Returns:
        Dictionary containing mean, median, std_dev, min, max
    """
    if not values:
        return {
            "mean": 0.0,
            "median": 0.0,
            "std_dev": 0.0,
            "min": 0.0,
            "max": 0.0,
            "count": 0,
        }

    return {
        "mean": mean(values),
        "median": median(values),
        "std_dev": stdev(values) if len(values) > 1 else 0.0,
        "min": min(values),
        "max": max(values),
        "count": len(values),
    }


def detect_outliers(
    values: list[float],
    threshold: float = 2.0,
) -> list[tuple[int, float]]:
    """Detect statistical outliers using z-score method.

    Args:
        values: List of numeric values
        threshold: Z-score threshold for outlier detection (default 2.0)

    Returns:
        List of (index, value) tuples for outliers
    """
    if len(values) < 3:
        return []

    avg = mean(values)
    std = stdev(values)

    if std == 0:
        return []

    outliers = []
    for i, value in enumerate(values):
        z_score = abs((value - avg) / std)
        if z_score > threshold:
            outliers.append((i, value))

    return outliers


def calculate_correlations(
    data: list[dict[str, float]],
    key1: str,
    key2: str,
) -> float:
    """Calculate Pearson correlation coefficient between two variables.

    Args:
        data: List of dictionaries containing the variables
        key1: First variable key
        key2: Second variable key

    Returns:
        Correlation coefficient (-1 to 1)
    """
    if len(data) < 3:
        return 0.0

    values1 = [d.get(key1, 0.0) for d in data]
    values2 = [d.get(key2, 0.0) for d in data]

    avg1 = mean(values1)
    avg2 = mean(values2)

    numerator = sum((v1 - avg1) * (v2 - avg2) for v1, v2 in zip(values1, values2))
    denominator1 = sum((v1 - avg1) ** 2 for v1 in values1) ** 0.5
    denominator2 = sum((v2 - avg2) ** 2 for v2 in values2) ** 0.5

    if denominator1 == 0 or denominator2 == 0:
        return 0.0

    return numerator / (denominator1 * denominator2)


def aggregate_player_stats(
    performances: list[dict[str, Any]],
) -> dict[str, Any]:
    """Aggregate player performance data across multiple games.

    Args:
        performances: List of per-game performance dictionaries

    Returns:
        Aggregated statistics dictionary
    """
    if not performances:
        return {}

    numeric_fields = [
        "kills", "deaths", "assists", "cs", "gold",
        "damage_dealt", "vision_score", "acs", "adr",
        "first_bloods", "first_deaths", "clutches",
    ]

    aggregated: dict[str, Any] = {
        "games_played": len(performances),
        "wins": sum(1 for p in performances if p.get("win", False)),
    }

    for field in numeric_fields:
        values = [p.get(field, 0) for p in performances if field in p]
        if values:
            aggregated[f"total_{field}"] = sum(values)
            aggregated[f"average_{field}"] = mean(values)
            aggregated[f"max_{field}"] = max(values)

    # Champion/agent frequency
    champion_counts: dict[str, int] = defaultdict(int)
    for p in performances:
        champ = p.get("champion") or p.get("agent")
        if champ:
            champion_counts[champ] += 1

    aggregated["most_played"] = sorted(
        champion_counts.items(),
        key=lambda x: x[1],
        reverse=True,
    )[:5]

    return aggregated


def aggregate_team_stats(
    games: list[dict[str, Any]],
) -> dict[str, Any]:
    """Aggregate team statistics across multiple games.

    Args:
        games: List of per-game team statistics

    Returns:
        Aggregated team statistics dictionary
    """
    if not games:
        return {}

    aggregated: dict[str, Any] = {
        "games_played": len(games),
        "wins": sum(1 for g in games if g.get("win", False)),
        "losses": sum(1 for g in games if not g.get("win", False)),
    }

    # Objective stats (LoL)
    objective_fields = [
        "dragons", "barons", "heralds", "towers",
        "first_blood", "first_tower", "first_dragon",
    ]

    for field in objective_fields:
        values = [g.get(field, 0) for g in games if field in g]
        if values:
            if field.startswith("first_"):
                aggregated[f"{field}_rate"] = sum(1 for v in values if v) / len(values)
            else:
                aggregated[f"average_{field}"] = mean(values)

    # Round stats (VALORANT)
    round_fields = [
        "rounds_won", "rounds_lost", "attack_rounds_won",
        "defense_rounds_won", "pistol_rounds_won",
    ]

    for field in round_fields:
        values = [g.get(field, 0) for g in games if field in g]
        if values:
            aggregated[f"total_{field}"] = sum(values)
            aggregated[f"average_{field}"] = mean(values)

    # Duration stats
    durations = [g.get("duration", 0) for g in games if g.get("duration")]
    if durations:
        aggregated["average_duration"] = mean(durations)

    return aggregated


def find_patterns(
    data: list[dict[str, Any]],
    conditions: list[tuple[str, str, Any]],
) -> list[dict[str, Any]]:
    """Find data points matching specific conditions.

    Args:
        data: List of data dictionaries
        conditions: List of (key, operator, value) tuples
                   Operators: 'eq', 'gt', 'lt', 'gte', 'lte', 'contains'

    Returns:
        Filtered list of matching data points
    """
    operators = {
        "eq": lambda a, b: a == b,
        "gt": lambda a, b: a > b,
        "lt": lambda a, b: a < b,
        "gte": lambda a, b: a >= b,
        "lte": lambda a, b: a <= b,
        "contains": lambda a, b: b in a if isinstance(a, (list, str)) else False,
    }

    results = []
    for item in data:
        match = True
        for key, op, value in conditions:
            item_value = item.get(key)
            if item_value is None:
                match = False
                break
            if not operators.get(op, lambda a, b: False)(item_value, value):
                match = False
                break
        if match:
            results.append(item)

    return results


def calculate_win_correlation(
    data: list[dict[str, Any]],
    factor_key: str,
    win_key: str = "win",
) -> dict[str, float]:
    """Calculate how a factor correlates with winning.

    Args:
        data: List of game data dictionaries
        factor_key: Key of the factor to analyze
        win_key: Key indicating win/loss

    Returns:
        Dictionary with correlation analysis results
    """
    wins = [d for d in data if d.get(win_key, False)]
    losses = [d for d in data if not d.get(win_key, False)]

    win_values = [d.get(factor_key, 0) for d in wins if factor_key in d]
    loss_values = [d.get(factor_key, 0) for d in losses if factor_key in d]

    return {
        "win_average": mean(win_values) if win_values else 0.0,
        "loss_average": mean(loss_values) if loss_values else 0.0,
        "difference": (mean(win_values) if win_values else 0.0) -
                     (mean(loss_values) if loss_values else 0.0),
        "win_sample_size": len(win_values),
        "loss_sample_size": len(loss_values),
    }
