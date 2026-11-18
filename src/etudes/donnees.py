"""Accès à StatsBomb Open Data (https://github.com/statsbomb/open-data).

Les fichiers sont téléchargés une fois puis gardés dans `donnees/` (non versionné).
Pour les événements, on ne garde que les tirs et les informations utiles à
l'étude, dans un fichier par match : quelques Ko au lieu de ~3 Mo.

Données : StatsBomb Open Data. Conditions d'utilisation :
https://github.com/statsbomb/open-data/blob/master/LICENSE.pdf
"""
from __future__ import annotations

import json
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

BASE = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"
CACHE = Path(__file__).resolve().parents[2] / "donnees"

# Actions avec ballon de l'équipe en possession, comptées pour la fenêtre stricte
ACTIONS_BALLON = {"Pass", "Carry", "Dribble", "Shot", "Miscontrol", "Dispossessed"}


def _get_json(url: str, tries: int = 4):
    for k in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                return json.load(r)
        except Exception:  # réseau : on réessaie
            if k == tries - 1:
                raise
            time.sleep(1.5 * (k + 1))


def _cached(path: Path, url: str):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    data = _get_json(url)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    return data


def competitions() -> list[dict]:
    return _cached(CACHE / "competitions.json", f"{BASE}/competitions.json")


def matches(competition_id: int, season_id: int) -> list[dict]:
    return _cached(CACHE / "matches" / f"{competition_id}_{season_id}.json",
                   f"{BASE}/matches/{competition_id}/{season_id}.json")


def extract_shots(events: list[dict]) -> list[dict]:
    """Tirs d'un match, avec le motif de la possession et la place du tir
    dans la possession (rang parmi les actions avec ballon de l'équipe)."""
    # rang de chaque action avec ballon de l'équipe en possession, par possession
    rank: dict[str, int] = {}
    count: dict[int, int] = {}
    for e in events:
        t = e["type"]["name"]
        if t in ACTIONS_BALLON and e.get("possession_team", {}).get("id") == e.get("team", {}).get("id"):
            p = e["possession"]
            count[p] = count.get(p, 0) + 1
            rank[e["id"]] = count[p]
    # lieu de la remise en jeu qui ouvre chaque possession (corner, coup franc, touche)
    restart_x: dict[int, float] = {}
    for e in events:
        t = e["type"]["name"]
        kind = (e.get("pass", {}).get("type", {}).get("name") if t == "Pass"
                else e.get("shot", {}).get("type", {}).get("name") if t == "Shot" else None)
        # la remise en jeu est une passe, ou le tir lui-même (coup franc ou corner direct)
        if kind in {"Corner", "Free Kick", "Throw-in"} and e["possession"] not in restart_x \
                and e.get("possession_team", {}).get("id") == e.get("team", {}).get("id"):
            restart_x[e["possession"]] = e["location"][0]
    out = []
    for e in events:
        if e["type"]["name"] != "Shot":
            continue
        s = e["shot"]
        out.append({
            "period": e["period"],
            "minute": e["minute"],
            "team": e["team"]["name"],
            "play_pattern": e["play_pattern"]["name"],
            "shot_type": s["type"]["name"],
            "outcome": s["outcome"]["name"],
            "body_part": s.get("body_part", {}).get("name"),
            "xg": s.get("statsbomb_xg", 0.0) or 0.0,
            "rank_in_possession": rank.get(e["id"]),
            "restart_x": restart_x.get(e["possession"]),
            # point d'arrivée du tir (x, y, z) : z = hauteur, absente pour certains tirs
            "end_x": (s.get("end_location") or [None])[0],
            "end_y": (s.get("end_location") or [None, None])[1],
            "end_z": (s.get("end_location") or [None, None, None])[2] if len(s.get("end_location") or []) > 2 else None,
            "player": e.get("player", {}).get("name"),
        })
    return out


def shots_for_match(match_id: int) -> list[dict]:
    path = CACHE / "shots_v4" / f"{match_id}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    ev = _get_json(f"{BASE}/events/{match_id}.json")
    shots = extract_shots(ev)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(shots), encoding="utf-8")
    return shots


def shots_for_competition(competition_id: int, season_id: int, workers: int = 8) -> list[dict]:
    """Tous les tirs d'une compétition-saison, avec l'identifiant du match."""
    ms = matches(competition_id, season_id)
    ids = [m["match_id"] for m in ms]
    with ThreadPoolExecutor(max_workers=workers) as ex:
        per_match = list(ex.map(shots_for_match, ids))
    rows = []
    for mid, shots in zip(ids, per_match):
        for s in shots:
            rows.append({"match_id": mid, **s})
    return rows


def player_matches_for_match(match_id: int) -> list[dict]:
    """Table joueuse × match d'un match (étude 1), en cache."""
    from .fiabilite import player_match_table
    path = CACHE / "joueuses_v1" / f"{match_id}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    rows = player_match_table(_get_json(f"{BASE}/events/{match_id}.json"))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows), encoding="utf-8")
    return rows


def player_matches_for_competition(competition_id: int, season_id: int, workers: int = 8) -> list[dict]:
    ms = matches(competition_id, season_id)
    ids = [m["match_id"] for m in ms]
    with ThreadPoolExecutor(max_workers=workers) as ex:
        per_match = list(ex.map(player_matches_for_match, ids))
    return [{"match_id": mid, **r} for mid, rows in zip(ids, per_match) for r in rows]
