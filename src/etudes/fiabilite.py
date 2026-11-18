"""Étude 1 — Quelles statistiques par 90 minutes sont fiables sur une saison ?

1. Table joueuse × match : minutes jouées (titularisation, remplacements,
   cartons rouges) et comptes d'actions tirés des événements StatsBomb.
2. Fiabilité par moitiés : pour chaque joueuse (≥ `min_minutes` sur la
   saison), les matchs sont répartis au hasard en deux moitiés ; on calcule
   la statistique par 90 min sur chaque moitié, puis la corrélation entre les
   deux moitiés sur l'ensemble des joueuses. La formule de Spearman-Brown
   ramène cette corrélation à une saison entière. 200 tirages, médiane.
3. Lecture : ≥ 0,7 fiable ; 0,5-0,7 à utiliser avec prudence ; < 0,5 bruit.
4. Minutes nécessaires pour atteindre 0,7 : projection de Spearman-Brown à
   partir de la fiabilité d'une demi-saison et de ses minutes moyennes.
"""
from __future__ import annotations

from collections import defaultdict

import numpy as np
import pandas as pd

STATS = {
    "passes": "Passes tentées",
    "passes_reussies": "Passes réussies",
    "passes_progressives": "Passes progressives",
    "passes_surface": "Passes dans la surface",
    "passes_longues": "Passes longues",
    "centres": "Centres",
    "passes_cles": "Passes menant à un tir",
    "conduites": "Conduites de balle",
    "conduites_progressives": "Conduites progressives",
    "dribbles": "Dribbles tentés",
    "dribbles_reussis": "Dribbles réussis",
    "tirs": "Tirs (hors penalty)",
    "xg": "xG (hors penalty)",
    "pressions": "Pressions",
    "tacles": "Tacles",
    "interceptions": "Interceptions",
    "recuperations": "Récupérations",
    "degagements": "Dégagements",
    "contres": "Contres",
    "duels_aeriens": "Duels aériens",
    "duels_aeriens_gagnes": "Duels aériens gagnés",
    "fautes_commises": "Fautes commises",
    "fautes_subies": "Fautes subies",
    "pertes": "Pertes de balle",
}


def poste(position: str | None) -> str | None:
    if not position:
        return None
    if position == "Goalkeeper":
        return "gardienne"
    if "Back" in position:
        return "défense"
    if "Midfield" in position:
        return "milieu"
    if "Wing" in position or "Forward" in position or "Striker" in position:
        return "attaque"
    return None


def _t(e) -> float:
    return e["minute"] + e.get("second", 0) / 60


def player_match_table(events: list[dict]) -> list[dict]:
    """Une ligne par joueuse ayant joué : minutes, poste principal, comptes."""
    end = max((_t(e) for e in events), default=0.0)
    on, off, team, name = {}, {}, {}, {}
    for e in events:
        t = e["type"]["name"]
        if t == "Starting XI":
            for l in e["tactics"]["lineup"]:
                pid = l["player"]["id"]
                on[pid], team[pid], name[pid] = 0.0, e["team"]["name"], l["player"]["name"]
        elif t == "Substitution":
            out_id, in_p = e["player"]["id"], e["substitution"]["replacement"]
            off[out_id] = _t(e)
            on[in_p["id"]], team[in_p["id"]], name[in_p["id"]] = _t(e), e["team"]["name"], in_p["name"]
        else:
            card = (e.get("foul_committed", {}).get("card") or e.get("bad_behaviour", {}).get("card") or {}).get("name")
            if card in ("Red Card", "Second Yellow") and "player" in e:
                off[e["player"]["id"]] = min(off.get(e["player"]["id"], end), _t(e))
    c = defaultdict(lambda: defaultdict(float))
    pos = defaultdict(lambda: defaultdict(int))
    for e in events:
        if "player" not in e:
            continue
        pid, t = e["player"]["id"], e["type"]["name"]
        if "position" in e:
            pos[pid][e["position"]["name"]] += 1
        k = c[pid]
        x0 = (e.get("location") or [None])[0]
        if t == "Pass":
            p = e.get("pass", {})
            ok = "outcome" not in p
            k["passes"] += 1
            if p.get("type", {}).get("name") == "Throw-in":
                k["passes"] -= 1          # les touches ne comptent pas comme passes
                continue
            ex, ey = (p.get("end_location") or [x0 or 0, 40])[:2]
            k["passes_reussies"] += ok
            k["passes_progressives"] += ok and x0 is not None and ex - x0 >= 10 and ex >= 60
            k["passes_surface"] += ok and ex >= 102 and 18 <= ey <= 62 and not (x0 >= 102 and 18 <= e["location"][1] <= 62)
            k["passes_longues"] += p.get("length", 0) >= 35
            k["centres"] += bool(p.get("cross"))
            k["passes_cles"] += bool(p.get("shot_assist") or p.get("goal_assist"))
            k["duels_aeriens_gagnes"] += bool(p.get("aerial_won"))
            k["duels_aeriens"] += bool(p.get("aerial_won"))
        elif t == "Carry":
            k["conduites"] += 1
            ex = (e.get("carry", {}).get("end_location") or [x0 or 0])[0]
            k["conduites_progressives"] += x0 is not None and ex - x0 >= 10 and ex >= 60
        elif t == "Dribble":
            k["dribbles"] += 1
            k["dribbles_reussis"] += e.get("dribble", {}).get("outcome", {}).get("name") == "Complete"
        elif t == "Shot":
            s = e.get("shot", {})
            if s.get("type", {}).get("name") != "Penalty":
                k["tirs"] += 1
                k["xg"] += s.get("statsbomb_xg", 0) or 0
            k["duels_aeriens_gagnes"] += bool(s.get("aerial_won"))
            k["duels_aeriens"] += bool(s.get("aerial_won"))
        elif t == "Pressure":
            k["pressions"] += 1
        elif t == "Duel":
            dt = e.get("duel", {}).get("type", {}).get("name")
            k["tacles"] += dt == "Tackle"
            k["duels_aeriens"] += dt == "Aerial Lost"
        elif t == "Interception":
            k["interceptions"] += 1
        elif t == "Ball Recovery":
            k["recuperations"] += not e.get("ball_recovery", {}).get("recovery_failure", False)
        elif t == "Clearance":
            k["degagements"] += 1
            k["duels_aeriens_gagnes"] += bool(e.get("clearance", {}).get("aerial_won"))
            k["duels_aeriens"] += bool(e.get("clearance", {}).get("aerial_won"))
        elif t == "Block":
            k["contres"] += 1
        elif t == "Foul Committed":
            k["fautes_commises"] += 1
        elif t == "Foul Won":
            k["fautes_subies"] += 1
        elif t in ("Dispossessed", "Miscontrol"):
            k["pertes"] += 1
            if t == "Miscontrol":
                k["duels_aeriens_gagnes"] += bool(e.get("miscontrol", {}).get("aerial_won"))
                k["duels_aeriens"] += bool(e.get("miscontrol", {}).get("aerial_won"))
    rows = []
    for pid, start in on.items():
        minutes = max(0.0, off.get(pid, end) - start)
        if minutes <= 0:
            continue
        main = max(pos[pid], key=pos[pid].get) if pos[pid] else None
        row = {"player_id": pid, "player": name[pid], "team": team[pid], "minutes": round(minutes, 2),
               "position": main, "poste": poste(main)}
        row.update({s: float(c[pid].get(s, 0.0)) for s in STATS})
        rows.append(row)
    return rows


def spearman_brown(r: float, k: float) -> float:
    return k * r / (1 + (k - 1) * r) if r is not None and not np.isnan(r) else np.nan


def minutes_needed(r_half: float, minutes_half: float, target: float = 0.7) -> float:
    """Minutes pour atteindre `target`, projetées depuis une demi-saison."""
    if r_half is None or np.isnan(r_half) or r_half <= 0:
        return np.nan
    return target * (1 - r_half) / (r_half * (1 - target)) * minutes_half


def reliability_at(r_half: float, minutes_half: float, minutes: float = 1000) -> float:
    """Fiabilité projetée pour `minutes` jouées (Spearman-Brown depuis une demi-saison).
    Permet de comparer des championnats dont les saisons n'ont pas la même longueur."""
    if r_half is None or np.isnan(r_half) or not minutes_half:
        return np.nan
    return spearman_brown(r_half, minutes / minutes_half)


def split_half(df: pd.DataFrame, stat: str, n_splits: int = 200, seed: int = 1,
               unit: str = "unit") -> dict:
    """Fiabilité par moitiés d'une statistique par 90 min.
    `df` : une ligne par unité (joueuse-saison) et par match, colonnes `unit`, minutes, stat."""
    rng = np.random.default_rng(seed)
    groups = [(g["minutes"].to_numpy(), g[stat].to_numpy()) for _, g in df.groupby(unit)]
    rs, mins = [], []
    for _ in range(n_splits):
        a, b, ma = [], [], []
        for m, v in groups:
            idx = rng.permutation(len(m))
            h1, h2 = idx[: len(m) // 2], idx[len(m) // 2:]
            m1, m2 = m[h1].sum(), m[h2].sum()
            if m1 <= 0 or m2 <= 0:
                continue
            a.append(v[h1].sum() / m1 * 90)
            b.append(v[h2].sum() / m2 * 90)
            ma.append((m1 + m2) / 2)
        a, b = np.array(a), np.array(b)
        if len(a) < 10 or a.std() == 0 or b.std() == 0:
            continue
        rs.append(np.corrcoef(a, b)[0, 1])
        mins.append(np.mean(ma))
    if not rs:
        return {"r_moitie": np.nan, "fiabilite_saison": np.nan, "minutes_moitie": np.nan, "joueuses": len(groups)}
    r = float(np.median(rs))
    return {"r_moitie": r, "fiabilite_saison": spearman_brown(r, 2), "minutes_moitie": float(np.mean(mins)),
            "joueuses": len(groups), "minutes_pour_0_7": minutes_needed(r, float(np.mean(mins))),
            "fiabilite_1000_min": reliability_at(r, float(np.mean(mins)), 1000)}


def lecture(f: float) -> str:
    if f is None or np.isnan(f):
        return "?"
    return "fiable" if f >= 0.7 else ("prudence" if f >= 0.5 else "bruit")
