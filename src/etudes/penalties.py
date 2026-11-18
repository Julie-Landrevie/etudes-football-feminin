"""Étude 3 — Les penalties : où, de quel pied, avec quelle réussite ?

Repère StatsBomb : terrain 120 × 80, attaque vers x = 120, y = 0 du côté
gauche de la tireuse. Le but va de y = 36 à y = 44 et de z = 0 à z = 2,67.
Zones (vues de la tireuse) : tiers du but en largeur (gauche, centre, droite)
× deux moitiés en hauteur (bas, haut). Un tir hors des montants est « hors
cadre ». Pour un tir arrêté, StatsBomb note le point où la gardienne touche
le ballon : une approximation de la zone visée.
Côté naturel : pour une droitière, sa gauche (elle ouvre le pied) ; pour une
gaucher, sa droite.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

POST_LEFT, POST_RIGHT, BAR = 36.0, 44.0, 8 / 3
WIDTHS = [POST_LEFT + (POST_RIGHT - POST_LEFT) / 3, POST_LEFT + 2 * (POST_RIGHT - POST_LEFT) / 3]


def side(y: float) -> str | None:
    if y is None or (isinstance(y, float) and math.isnan(y)):
        return None
    if y < POST_LEFT or y > POST_RIGHT:
        return "hors cadre"
    return "gauche" if y < WIDTHS[0] else ("centre" if y <= WIDTHS[1] else "droite")


def height(z: float) -> str | None:
    if z is None or (isinstance(z, float) and math.isnan(z)):
        return None
    return "bas" if z < BAR / 2 else "haut"


def natural(side_: str | None, foot: str | None) -> str | None:
    """Côté naturel, opposé ou centre, selon le pied de frappe."""
    if side_ in (None, "hors cadre") or foot not in ("Right Foot", "Left Foot"):
        return None
    if side_ == "centre":
        return "centre"
    nat = "gauche" if foot == "Right Foot" else "droite"
    return "naturel" if side_ == nat else "opposé"


def prepare(shots: pd.DataFrame) -> pd.DataFrame:
    p = shots[shots["shot_type"] == "Penalty"].copy()
    p["but"] = (p["outcome"] == "Goal").astype(int)
    p["seance"] = p["period"] == 5
    p["cote"] = p["end_y"].map(side)
    p["hauteur"] = p["end_z"].map(height)
    p["zone"] = np.where(p["cote"] == "hors cadre", "hors cadre",
                         p["cote"].fillna("?") + " " + p["hauteur"].fillna("?"))
    p["cote_pied"] = [natural(s, f) for s, f in zip(p["cote"], p["body_part"])]
    return p


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float, float]:
    """Proportion et intervalle de Wilson (adapté aux petits effectifs)."""
    if n == 0:
        return float("nan"), float("nan"), float("nan")
    ph = k / n
    den = 1 + z * z / n
    c = (ph + z * z / (2 * n)) / den
    h = z * math.sqrt(ph * (1 - ph) / n + z * z / (4 * n * n)) / den
    return ph, c - h, c + h


def diff_ci(k1: int, n1: int, k2: int, n2: int, z: float = 1.96) -> tuple[float, float, float]:
    """Écart de deux proportions, intervalle de Newcombe (combinaison de Wilson)."""
    p1, l1, u1 = wilson(k1, n1, z)
    p2, l2, u2 = wilson(k2, n2, z)
    d = p1 - p2
    return d, d - math.sqrt((p1 - l1) ** 2 + (u2 - p2) ** 2), d + math.sqrt((u1 - p1) ** 2 + (p2 - l2) ** 2)


def n_per_group(p1: float, p2: float, alpha_z: float = 1.96, power_z: float = 0.8416) -> int:
    """Penalties nécessaires par groupe pour détecter l'écart p1 − p2
    (test bilatéral à 5 %, puissance 80 %)."""
    pb = (p1 + p2) / 2
    num = (alpha_z * math.sqrt(2 * pb * (1 - pb)) + power_z * math.sqrt(p1 * (1 - p1) + p2 * (1 - p2))) ** 2
    return math.ceil(num / (p1 - p2) ** 2)


def rate_table(p: pd.DataFrame, by: str) -> pd.DataFrame:
    rows = []
    for k, g in p.groupby(by):
        r, lo, hi = wilson(int(g["but"].sum()), len(g))
        rows.append({by: k, "penalties": len(g), "part": len(g) / len(p), "reussite": r, "ic_bas": lo, "ic_haut": hi})
    return pd.DataFrame(rows)
