"""Offline sample-data backend that mimics the GRID GraphQL responses.

Used automatically by ``GridClient`` when the real GRID API rejects the key
(UNAUTHENTICATED / 401 / 403) or no key is configured. Everything here is
**synthetic**: team names are real organisations but players, results and stats
are invented and deterministic (seeded by series id), so the same request always
returns the same data.

Responses are supersets of every field the app's queries request; GraphQL
clients ignore unrequested fields, so a single payload serves all queries.
"""

from __future__ import annotations

import hashlib
import random
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

LOL_TITLE_ID = "3"
VAL_TITLE_ID = "6"

_C9_IDS = {LOL_TITLE_ID: "47351", VAL_TITLE_ID: "79"}

_BASE_DATE = datetime(2025, 10, 1, 18, 0, tzinfo=timezone.utc)
SERIES_PER_TEAM = 12

# ── Static catalogue ────────────────────────────────────────────────────────

_LOL_TEAMS = [
    ("Cloud9", "C9", "#0b9ee0", 0.62),
    ("Team Liquid", "TL", "#0c2340", 0.58),
    ("100 Thieves", "100T", "#d12027", 0.50),
    ("FlyQuest", "FLY", "#1c8a4b", 0.55),
    ("Dignitas", "DIG", "#f4b400", 0.45),
    ("Shopify Rebellion", "SR", "#6b8e23", 0.48),
    ("LYON", "LYN", "#8a2be2", 0.42),
    ("Disguised", "DSG", "#444444", 0.40),
    ("Immortals", "IMT", "#00a3a3", 0.46),
    ("Golden Guardians", "GG", "#b8860b", 0.41),
    ("T1", "T1", "#e2012d", 0.66),
    ("Gen.G", "GEN", "#aa8a00", 0.64),
    ("G2 Esports", "G2", "#222222", 0.56),
    ("FNATIC", "FNC", "#ff5900", 0.52),
]
_VAL_TEAMS = [
    ("Cloud9", "C9", "#0b9ee0", 0.57),
    ("Sentinels", "SEN", "#c8102e", 0.60),
    ("100 Thieves", "100T", "#d12027", 0.50),
    ("NRG", "NRG", "#f26522", 0.55),
    ("Evil Geniuses", "EG", "#1b1f6b", 0.44),
    ("LOUD", "LOUD", "#1fbf3a", 0.54),
    ("FNATIC", "FNC", "#ff5900", 0.52),
    ("G2 Esports", "G2", "#222222", 0.50),
    ("Leviatan", "LEV", "#6fb7ff", 0.51),
    ("KRU Esports", "KRU", "#5b2a86", 0.47),
    ("MIBR", "MIBR", "#1a8f3c", 0.43),
    ("Team Heretics", "TH", "#c9a227", 0.53),
    ("Paper Rex", "PRX", "#e8344d", 0.61),
    ("DRX", "DRX", "#2a6fdb", 0.56),
]

def _extend_handles(base: list[str], total: int, seed: str) -> list[str]:
    """Pad a curated handle list with generated, unique handles."""
    a = ["Ka", "Ry", "Zo", "Vi", "Mo", "Tak", "Lu", "Ne", "Ora", "Pyr", "Sol", "Dra", "Kel", "Bri"]
    b = ["x", "n", "ra", "ven", "zen", "lix", "mo", "ko", "rok", "tis", "dan", "ph"]
    combos = [x + y for x in a for y in b if x + y not in base]
    random.Random(seed).shuffle(combos)
    return base + combos[: total - len(base)]


_LOL_ROLES = ["top", "jungle", "mid", "bot", "support"]
_VAL_ROLES = ["duelist", "initiator", "controller", "sentinel", "flex"]

_LOL_HANDLES = [
    "Vexor", "Kaelith", "Ryuzen", "Orlix", "Nimbus", "Talon9", "Zephra", "Quill",
    "Brandt", "Solace", "Ironveil", "Mako", "Drift", "Halcyon", "Pyrrha", "Cobalt",
    "Wraith", "Lumen", "Sable", "Tundra", "Ember", "Fjord", "Gale", "Hollow",
    "Juno", "Kestrel", "Lyric", "Mirage", "Nova", "Onyx", "Pike", "Rook",
    "Slate", "Thorn", "Umbra", "Vesper", "Warden", "Xylo", "Yarrow", "Zenith",
]
_VAL_HANDLES = [
    "Apex", "Blitz", "Cipher", "Dagger", "Echo", "Flux", "Ghost", "Havoc",
    "Ion", "Jolt", "Kilo", "Lynx", "Maverick", "Nyx", "Oracle", "Phantom",
    "Quartz", "Razor", "Spectre", "Tempest", "Uplink", "Vortex", "Wisp", "Xeno",
    "Yeti", "Zero", "Arc", "Bolt", "Crow", "Dusk", "Edge", "Fang",
    "Glitch", "Halo", "Iris", "Jinx9", "Karma", "Loop", "Mosaic", "Nitro",
]

_LOL_HANDLES = _extend_handles(_LOL_HANDLES, 90, "lol-handles")
_VAL_HANDLES = _extend_handles(_VAL_HANDLES, 90, "val-handles")

_LOL_POOLS = {
    "top": ["K'Sante", "Jax", "Gnar", "Aatrox", "Renekton", "Ornn", "Sion", "Camille"],
    "jungle": ["Sejuani", "Viego", "Lee Sin", "Vi", "Jarvan IV", "Maokai", "Nidalee", "Elise"],
    "mid": ["Azir", "Ahri", "Syndra", "Orianna", "Viktor", "Taliyah", "Corki", "Sylas"],
    "bot": ["Jinx", "Kai'Sa", "Ezreal", "Aphelios", "Varus", "Caitlyn", "Xayah", "Zeri"],
    "support": ["Lulu", "Nautilus", "Rell", "Thresh", "Alistar", "Karma", "Leona", "Renata Glasc"],
}
_VAL_POOLS = {
    "duelist": ["Jett", "Raze", "Neon", "Reyna", "Yoru", "Phoenix"],
    "initiator": ["Sova", "Fade", "Skye", "KAY/O", "Breach", "Gekko"],
    "controller": ["Omen", "Astra", "Viper", "Brimstone", "Harbor", "Clove"],
    "sentinel": ["Killjoy", "Cypher", "Chamber", "Sage", "Vyse"],
    "flex": ["Jett", "Omen", "Sova", "Killjoy", "Skye", "Gekko"],
}
_VAL_MAPS = ["Ascent", "Bind", "Haven", "Split", "Lotus", "Sunset", "Icebox", "Abyss", "Pearl"]

_ROLE_KDA = {  # (kills, deaths, assists) base per game, LoL
    "top": (3.0, 2.6, 4.5), "jungle": (3.2, 2.8, 7.5), "mid": (4.6, 2.4, 6.0),
    "bot": (5.2, 2.2, 5.5), "support": (0.9, 3.0, 11.0),
}


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def _build_catalogue() -> dict[str, Any]:
    teams: dict[str, dict[str, Any]] = {}
    players: dict[str, dict[str, Any]] = {}
    for title, base_id, defs, roles, handles, pools in (
        (LOL_TITLE_ID, 90000, _LOL_TEAMS, _LOL_ROLES, _LOL_HANDLES, _LOL_POOLS),
        (VAL_TITLE_ID, 91000, _VAL_TEAMS, _VAL_ROLES, _VAL_HANDLES, _VAL_POOLS),
    ):
        pid_base = 80000 if title == LOL_TITLE_ID else 85000
        for ti, (name, short, color, strength) in enumerate(defs):
            tid = str(base_id + ti + 1)
            # The UI hardcodes Cloud9's real GRID team IDs; reuse them.
            if name == "Cloud9":
                tid = _C9_IDS[title]
            roster = []
            for ri, role in enumerate(roles):
                idx = ti * 5 + ri
                pid = str(pid_base + idx + 1)
                rng = random.Random(f"pool-{title}-{pid}")
                pool = list(pools[role])
                rng.shuffle(pool)
                p = {
                    "id": pid,
                    "nickname": handles[idx],
                    "roles": [{"id": str(ri + 1), "name": role}],
                    "_pool": pool,
                    "_role": role,
                    "_skill": 0.85 + rng.random() * 0.4,
                }
                players[pid] = p
                roster.append(pid)
            teams[tid] = {
                "id": tid,
                "name": name,
                "nameShortened": short,
                "colorPrimary": color,
                "colorSecondary": "#ffffff",
                "logoUrl": None,
                "_title": title,
                "_strength": strength,
                "_roster": roster,
            }
    return {"teams": teams, "players": players}


_CAT = _build_catalogue()
TEAMS: dict[str, dict[str, Any]] = _CAT["teams"]
PLAYERS: dict[str, dict[str, Any]] = _CAT["players"]


def _pub(d: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in d.items() if not k.startswith("_")}


def _titles_of(title: str) -> list[str]:
    return [tid for tid, t in TEAMS.items() if t["_title"] == title]


# ── Series generation ───────────────────────────────────────────────────────

def _series_id(title: str, a: str, b: str, n: int) -> str:
    return f"mock-{title}-{a}-{b}-{n}"


def _parse_series_id(sid: str) -> Optional[tuple[str, str, str, int]]:
    m = re.fullmatch(r"mock-(\d+)-(\d+)-(\d+)-(\d+)", str(sid))
    if not m:
        return None
    title, a, b, n = m.group(1), m.group(2), m.group(3), int(m.group(4))
    if a not in TEAMS or b not in TEAMS:
        return None
    return title, a, b, n


def _series_start(n: int) -> datetime:
    return _BASE_DATE - timedelta(days=4 * n + 1)


def _series_list_for_team(team_id: str) -> list[str]:
    t = TEAMS.get(team_id)
    if not t:
        return []
    title = t["_title"]
    opps = [x for x in _titles_of(title) if x != team_id]
    return [_series_id(title, team_id, opps[(n * 3 + 1) % len(opps)], n) for n in range(SERIES_PER_TEAM)]


def _series_node(sid: str) -> Optional[dict[str, Any]]:
    parsed = _parse_series_id(sid)
    if not parsed:
        return None
    title, a, b, n = parsed
    return {
        "id": sid,
        "startTimeScheduled": _series_start(n).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "type": "ESPORTS",
        "title": {"id": title, "name": "League of Legends" if title == LOL_TITLE_ID else "VALORANT"},
        "tournament": {"id": "9001", "name": "Sample Championship Series"},
        "format": {"name": "Best of 3", "nameShortened": "Bo3"},
        "teams": [
            {"baseInfo": {"id": x, "name": TEAMS[x]["name"], "logoUrl": None}, "scoreAdvantage": 0}
            for x in (a, b)
        ],
        "players": [
            {"id": pid, "nickname": PLAYERS[pid]["nickname"], "roles": PLAYERS[pid]["roles"]}
            for x in (a, b) for pid in TEAMS[x]["_roster"]
        ],
    }


def _series_state(sid: str) -> Optional[dict[str, Any]]:
    parsed = _parse_series_id(sid)
    if not parsed:
        return None
    title, a, b, n = parsed
    rng = random.Random(hashlib.sha256(sid.encode()).hexdigest())
    sa, sb = TEAMS[a]["_strength"], TEAMS[b]["_strength"]
    p_a = min(0.85, max(0.15, 0.5 + (sa - sb) * 1.4))
    wins = {a: 0, b: 0}
    games: list[dict[str, Any]] = []
    start = _series_start(n)
    seq = 0
    while max(wins.values()) < 2:
        seq += 1
        winner = a if rng.random() < p_a else b
        wins[winner] += 1
        g_start = start + timedelta(minutes=50 * (seq - 1))
        if title == LOL_TITLE_ID:
            games.append(_lol_game(rng, sid, seq, a, b, winner, g_start))
        else:
            games.append(_val_game(rng, sid, seq, a, b, winner, g_start))
    teams_state = [
        {
            "id": x,
            "name": TEAMS[x]["name"],
            "score": wins[x],
            "players": [{"id": pid, "name": PLAYERS[pid]["nickname"]} for pid in TEAMS[x]["_roster"]],
        }
        for x in (a, b)
    ]
    return {
        "id": sid,
        "title": {"nameShortened": "lol" if title == LOL_TITLE_ID else "val"},
        "started": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "finished": (start + timedelta(minutes=50 * len(games) + 10)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "teams": teams_state,
        "games": games,
    }


def _lol_game(rng: random.Random, sid: str, seq: int, a: str, b: str, winner: str, g_start: datetime) -> dict[str, Any]:
    duration = int(rng.gauss(1900, 260))
    blue = a if rng.random() < 0.5 else b
    teams = []
    taken: set[str] = set()
    for x in (a, b):
        won = x == winner
        players = []
        for pid in TEAMS[x]["_roster"]:
            p = PLAYERS[pid]
            champ = _pick(rng, p["_pool"], taken)
            taken.add(champ)
            k0, d0, a0 = _ROLE_KDA[p["_role"]]
            skill = p["_skill"] * (1.18 if won else 0.82)
            kills = max(0, round(rng.gauss(k0 * skill, 1.6)))
            deaths = max(0, round(rng.gauss(d0 / skill, 1.3)))
            assists = max(0, round(rng.gauss(a0 * skill, 2.2)))
            players.append({
                "id": pid, "name": p["nickname"],
                "character": {"id": _slug(champ), "name": champ},
                "kills": kills, "deaths": deaths, "killAssistsGiven": assists,
                "netWorth": int(8000 + kills * 320 + assists * 140 + duration * 4.2 + rng.randint(-800, 800)),
            })
        teams.append({
            "id": x, "name": TEAMS[x]["name"], "score": 1 if won else 0,
            "side": "blue" if x == blue else "red", "players": players,
        })
    return {
        "id": f"{sid}-g{seq}", "sequenceNumber": seq,
        "started": g_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "finished": True, "duration": duration,
        "teams": teams,
    }


def _val_game(rng: random.Random, sid: str, seq: int, a: str, b: str, winner: str, g_start: datetime) -> dict[str, Any]:
    map_name = _VAL_MAPS[rng.randrange(len(_VAL_MAPS))]
    loser_rounds = rng.randint(5, 11)
    ot = rng.random() < 0.12
    scores = {winner: 13 if not ot else 14, (b if winner == a else a): loser_rounds if not ot else 12}
    first_att = a if rng.random() < 0.5 else b
    teams = []
    for x in (a, b):
        won = x == winner
        taken: set[str] = set()
        players = []
        for pid in TEAMS[x]["_roster"]:
            p = PLAYERS[pid]
            agent = _pick(rng, p["_pool"], taken)
            taken.add(agent)
            rounds = scores[a] + scores[b]
            skill = p["_skill"] * (1.12 if won else 0.88)
            duelist = 1.2 if p["_role"] == "duelist" else 0.9
            kills = max(2, round(rng.gauss(rounds * 0.72 * skill * duelist / 1.0, 3)))
            deaths = max(2, round(rng.gauss(rounds * 0.68 / skill, 3)))
            assists = max(0, round(rng.gauss(rounds * 0.25, 2)))
            players.append({
                "id": pid, "name": p["nickname"],
                "character": {"id": _slug(agent), "name": agent},
                "kills": kills, "deaths": deaths, "killAssistsGiven": assists,
                "netWorth": int(rng.gauss(3800, 700)),
                "headshots": int(kills * rng.uniform(0.18, 0.34)),
                "damageDealt": int(kills * 145 + assists * 30 + rng.randint(200, 900)),
                "damageTaken": int(deaths * 130 + rng.randint(300, 1200)),
                "objectives": [
                    {"type": "plantBomb", "completionCount": rng.randint(0, 4) if p["_role"] in ("duelist", "flex") else rng.randint(0, 2)},
                    {"type": "defuseBomb", "completionCount": rng.randint(0, 2)},
                ],
            })
        teams.append({
            "id": x, "name": TEAMS[x]["name"], "score": scores[x],
            "side": "attacker" if x == first_att else "defender", "players": players,
        })
    return {
        "id": f"{sid}-g{seq}", "sequenceNumber": seq,
        "started": g_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "finished": True, "map": {"name": map_name},
        "teams": teams,
    }


def _pick(rng: random.Random, pool: list[str], taken: set[str]) -> str:
    weights = [0.38, 0.24, 0.15, 0.1, 0.07, 0.04, 0.02, 0.01]
    options = [(c, weights[i] if i < len(weights) else 0.01) for i, c in enumerate(pool) if c not in taken]
    if not options:
        return pool[0]
    return rng.choices([c for c, _ in options], weights=[w for _, w in options])[0]


# ── GraphQL-ish dispatcher ──────────────────────────────────────────────────

def _connection(nodes: list[dict[str, Any]], first: Optional[int]) -> dict[str, Any]:
    limit = first if isinstance(first, int) and first > 0 else len(nodes)
    sel = nodes[:limit]
    return {
        "totalCount": len(nodes),
        "edges": [{"cursor": str(i), "node": n} for i, n in enumerate(sel)],
        "pageInfo": {
            "hasNextPage": len(nodes) > limit, "hasPreviousPage": False,
            "startCursor": "0" if sel else None, "endCursor": str(len(sel) - 1) if sel else None,
        },
    }


def _in_list(filter_val: Any) -> Optional[list[str]]:
    if isinstance(filter_val, dict) and "in" in filter_val:
        return [str(x) for x in filter_val["in"]]
    return None


def _series_nodes(ids: list[str]) -> list[dict[str, Any]]:
    nodes = [_series_node(i) for i in ids]
    return sorted([n for n in nodes if n], key=lambda n: n["startTimeScheduled"], reverse=True)


def respond(query: str, variables: Optional[dict[str, Any]]) -> dict[str, Any]:
    """Return sample data for a GRID query (dispatch by operation name)."""
    variables = variables or {}
    m = re.search(r"\b(?:query)\s+(\w+)", query)
    op = m.group(1) if m else ""

    if op.startswith("GetSeriesState"):
        return {"seriesState": _series_state(str(variables.get("seriesId")))}

    if op == "GetTeamInfo":
        t = TEAMS.get(str(variables.get("teamId")))
        return {"team": _pub(t) if t else None}

    if op == "GetTeams":
        flt = variables.get("filter") or {}
        title = flt.get("titleId")
        needle = ((flt.get("name") or {}).get("contains") or "").lower()
        nodes = [
            _pub(t) for t in TEAMS.values()
            if (not title or t["_title"] == str(title)) and (not needle or needle in t["name"].lower())
        ]
        return {"teams": _connection(nodes, variables.get("first"))}

    if op == "GetTeamSeries":
        titles = [str(x) for x in variables.get("titleIds") or []]
        tid = str(variables.get("teamId"))
        if titles and TEAMS.get(tid, {}).get("_title") not in titles:
            return {"allSeries": _connection([], variables.get("first"))}
        return {"allSeries": _connection(_series_nodes(_series_list_for_team(tid)), variables.get("first"))}

    if op == "GetPlayerSeries":
        pid = str(variables.get("playerId"))
        owner = next((tid for tid, t in TEAMS.items() if pid in t["_roster"]), None)
        ids = _series_list_for_team(owner) if owner else []
        return {"allSeries": _connection(_series_nodes(ids), variables.get("first"))}

    if op == "GetSeriesList":
        flt = variables.get("filter") or {}
        titles = _in_list(flt.get("titleIds")) or [LOL_TITLE_ID]
        team_ids = _in_list(flt.get("teamIds"))
        player_ids = _in_list(flt.get("livePlayerIds"))
        ids: list[str] = []
        if team_ids:
            for tid in team_ids:
                ids += _series_list_for_team(tid)
        elif player_ids:
            for pid in player_ids:
                owner = next((tid for tid, t in TEAMS.items() if pid in t["_roster"]), None)
                if owner:
                    ids += _series_list_for_team(owner)
        else:
            for title in titles:
                for tid in _titles_of(title):
                    ids += _series_list_for_team(tid)
        ids = list(dict.fromkeys(ids))
        nodes = [n for n in _series_nodes(ids) if n["title"]["id"] in titles]
        gte, lte = (flt.get("startTimeScheduled") or {}).get("gte"), (flt.get("startTimeScheduled") or {}).get("lte")
        if gte:
            nodes = [n for n in nodes if n["startTimeScheduled"] >= gte]
        if lte:
            nodes = [n for n in nodes if n["startTimeScheduled"] <= lte]
        if str(variables.get("orderDirection")).upper() == "ASC":
            nodes.reverse()
        return {"allSeries": _connection(nodes, variables.get("first"))}

    if op == "GetSeriesInfo":
        return {"series": _series_node(str(variables.get("seriesId")))}

    if op == "GetPlayerInfo":
        p = PLAYERS.get(str(variables.get("playerId")))
        return {"player": _pub(p) if p else None}

    if op == "GetPlayers":
        flt = variables.get("filter") or {}
        needle = ((flt.get("nickname") or {}).get("contains") or "").lower()
        nodes = [_pub(p) for p in PLAYERS.values() if not needle or needle in p["nickname"].lower()]
        return {"players": _connection(nodes, variables.get("first"))}

    return {}
