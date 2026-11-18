"""Étude 2 — Quelle part du xG vient des phases arrêtées ?

Définitions (posées avant de regarder les résultats) :
- on exclut les penalties (type de tir « Penalty ») et les séances de tirs au
  but (période 5) ;
- un tir vient d'une phase arrêtée si sa possession a commencé par un corner,
  un coup franc ou une touche (`play_pattern` StatsBomb) ;
- version « sans touches » : corners et coups francs seulement ;
- fenêtre stricte : le tir est l'une des 3 premières actions avec ballon de
  l'équipe dans la possession (sinon, un but marqué 20 secondes après un
  corner dégagé compterait comme « corner ») ;
- version « moitié adverse » : la remise en jeu (corner, coup franc, touche)
  qui ouvre la possession est jouée dans la moitié adverse (x ≥ 60 sur un
  terrain StatsBomb de 120 × 80). C'est la définition la plus proche des
  « phases arrêtées offensives » d'un staff ;
- détail : coup franc direct (tir de type « Free Kick ») et corner direct
  (tir de type « Corner »).
Intervalle de confiance à 95 % : bootstrap sur les matchs (on tire des
matchs avec remise, pas des tirs, car les tirs d'un même match ne sont pas
indépendants).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

SET_PIECES = {"From Corner": "corner", "From Free Kick": "coup franc", "From Throw In": "touche"}
STRICT_ACTIONS = 3
HALF_X = 60


def prepare(shots: pd.DataFrame) -> pd.DataFrame:
    """Filtre et ajoute les catégories."""
    d = shots[(shots["shot_type"] != "Penalty") & (shots["period"] != 5)].copy()
    d["goal"] = (d["outcome"] == "Goal").astype(int)
    d["origine"] = d["play_pattern"].map(SET_PIECES).fillna("jeu courant")
    d["cpa"] = d["origine"] != "jeu courant"
    d["cpa_sans_touche"] = d["origine"].isin(["corner", "coup franc"])
    strict = d["rank_in_possession"].notna() & (d["rank_in_possession"] <= STRICT_ACTIONS)
    d["cpa_strict"] = d["cpa"] & strict
    rx = d["restart_x"] if "restart_x" in d else pd.Series(np.nan, index=d.index)
    d["cpa_adverse"] = d["cpa"] & (rx >= HALF_X)
    d["coup_franc_direct"] = d["shot_type"] == "Free Kick"
    d["corner_direct"] = d["shot_type"] == "Corner"
    return d


def shares(d: pd.DataFrame, flag: str = "cpa") -> dict:
    """Part du xG, des tirs et des buts portée par `flag`."""
    xg = d["xg"].sum()
    goals = d["goal"].sum()
    return {
        "part_xg": d.loc[d[flag], "xg"].sum() / xg if xg > 0 else np.nan,
        "part_tirs": d[flag].mean() if len(d) else np.nan,
        "part_buts": d.loc[d[flag], "goal"].sum() / goals if goals > 0 else np.nan,
    }


def bootstrap_share(d: pd.DataFrame, flag: str = "cpa", value: str = "xg",
                    n_boot: int = 1000, seed: int = 1) -> tuple[float, float, float]:
    """Part de `value` (xg ou goal) portée par `flag`, avec IC 95 % par bootstrap
    sur les matchs. Renvoie (estimation, borne basse, borne haute)."""
    g = d.groupby("match_id").apply(
        lambda x: pd.Series({"num": x.loc[x[flag], value].sum(), "den": x[value].sum()}),
        include_groups=False)
    num, den = g["num"].to_numpy(), g["den"].to_numpy()
    est = num.sum() / den.sum() if den.sum() > 0 else np.nan
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(g), size=(n_boot, len(g)))
    bn, bd = num[idx].sum(axis=1), den[idx].sum(axis=1)
    boot = np.where(bd > 0, bn / np.where(bd > 0, bd, 1), np.nan)
    lo, hi = np.nanpercentile(boot, [2.5, 97.5])
    return float(est), float(lo), float(hi)


def summary(d: pd.DataFrame, n_boot: int = 1000) -> dict:
    """Résumé complet pour un groupe de matchs (une compétition, ou un regroupement)."""
    out = {"matchs": d["match_id"].nunique(), "tirs": len(d), "buts": int(d["goal"].sum()),
           "xg_total": d["xg"].sum()}
    for flag, name in [("cpa", "cpa"), ("cpa_sans_touche", "cpa_sans_touche"), ("cpa_strict", "cpa_strict"),
                       ("cpa_adverse", "cpa_adverse")]:
        est, lo, hi = bootstrap_share(d, flag, "xg", n_boot)
        out[f"{name}_part_xg"], out[f"{name}_ic_bas"], out[f"{name}_ic_haut"] = est, lo, hi
        s = shares(d, flag)
        out[f"{name}_part_tirs"], out[f"{name}_part_buts"] = s["part_tirs"], s["part_buts"]
    for o in ["corner", "coup franc", "touche"]:
        out[f"part_xg_{o}"] = d.loc[d["origine"] == o, "xg"].sum() / d["xg"].sum()
    cf = d[d["origine"] == "coup franc"]
    out["coup_franc_direct_part_xg_cf"] = cf.loc[cf["coup_franc_direct"], "xg"].sum() / cf["xg"].sum() if len(cf) else np.nan
    co = d[d["origine"] == "corner"]
    out["corner_direct_part_xg_corner"] = co.loc[co["corner_direct"], "xg"].sum() / co["xg"].sum() if len(co) else np.nan
    out["xg_par_tir_cpa"] = d.loc[d["cpa"], "xg"].mean()
    out["xg_par_tir_jeu"] = d.loc[~d["cpa"], "xg"].mean()
    return out
