"""Étude 1 — fiabilité des statistiques par 90 min sur une saison.
Principal : FA WSL (4 saisons). Contrôle féminin : les autres championnats
2023/24 + NWSL 2023. Comparaison masculine : Premier League 2015/16 (contrôle :
Liga 2015/16). Données : StatsBomb Open Data.
Sorties : resultats/etude1_*.csv
"""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from etudes.donnees import competitions, player_matches_for_competition  # noqa: E402
from etudes.fiabilite import STATS, lecture, split_half  # noqa: E402

GROUPES = {
    "WSL": [(37, 4), (37, 42), (37, 90), (37, 281)],
    "Autres championnats féminins": [(135, 281), (182, 281), (131, 281), (49, 107)],
    "Premier League 2015/16": [(2, 27)],
    "Liga 2015/16": [(11, 27)],
}
SEUILS = [600, 900, 1500]
N_SPLITS = 200


def load(pairs, comp):
    rows = []
    for cid, sid in pairs:
        c = comp[(cid, sid)]
        print(f"  {c['competition_name']} {c['season_name']}…", flush=True)
        d = pd.DataFrame(player_matches_for_competition(cid, sid))
        d["saison"] = f"{c['competition_name']} {c['season_name']}"
        rows.append(d)
    d = pd.concat(rows, ignore_index=True)
    d = d[d["poste"] != "gardienne"]
    d["unit"] = d["saison"] + "|" + d["player_id"].astype(str)
    return d


def reliability(d, min_minutes, label, poste_=None):
    tot = d.groupby("unit")["minutes"].sum()
    keep = tot[tot >= min_minutes].index
    x = d[d["unit"].isin(keep)]
    if poste_:
        main = x.groupby(["unit", "poste"])["minutes"].sum().reset_index().sort_values("minutes").drop_duplicates("unit", keep="last")
        x = x[x["unit"].isin(main.loc[main["poste"] == poste_, "unit"])]
    rows = []
    for s, lab in STATS.items():
        r = split_half(x, s, n_splits=N_SPLITS)
        rows.append({"groupe": label, "seuil_minutes": min_minutes, "poste": poste_ or "tous", "stat": s, "libelle": lab,
                     **r, "lecture": lecture(r["fiabilite_saison"])})
    return rows


def main():
    comp = {(c["competition_id"], c["season_id"]): c for c in competitions()}
    data = {g: load(p, comp) for g, p in GROUPES.items()}
    out = ROOT / "resultats"
    rows = []
    for g, d in data.items():
        for m in SEUILS:
            rows += reliability(d, m, g)
    for p in ["défense", "milieu", "attaque"]:
        rows += reliability(data["WSL"], 900, "WSL", p)
        rows += reliability(data["Premier League 2015/16"], 900, "Premier League 2015/16", p)
    res = pd.DataFrame(rows)
    res.to_csv(out / "etude1_fiabilite.csv", index=False)
    pd.concat([d.assign(groupe=g) for g, d in data.items()]).to_csv(out / "etude1_joueuses_matchs.csv.gz", index=False)
    main_ = res[(res.seuil_minutes == 900) & (res.poste == "tous")]
    print("minutes moyennes par demi-saison :", main_.groupby("groupe")["minutes_moitie"].mean().round(0).to_dict())
    w = main_.pivot(index="libelle", columns="groupe", values="fiabilite_1000_min").round(2)
    w = w[list(GROUPES)].sort_values("WSL", ascending=False)
    print(main_.groupby("groupe")["joueuses"].max())
    with pd.option_context("display.width", 200):
        print(w.to_string())
        for g in GROUPES:
            x = main_[main_.groupe == g]
            print(g, "(saison) fiables :", (x.lecture == "fiable").sum(), "/", len(x), "· prudence :", (x.lecture == "prudence").sum(),
                  "· bruit :", (x.lecture == "bruit").sum())


if __name__ == "__main__":
    main()
