"""Étude 2 — part du xG issue des phases arrêtées, compétitions féminines et
comparaison masculine (championnats 2015/16). Données : StatsBomb Open Data.

Usage : python scripts/etude2_cpa.py
Sorties : resultats/etude2_par_competition.csv, resultats/etude2_tirs.csv.gz
"""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from etudes.coups_pieds_arretes import prepare, summary  # noqa: E402
from etudes.donnees import competitions, shots_for_competition  # noqa: E402

FEMMES = [(37, 4), (37, 42), (37, 90), (37, 281), (135, 281), (182, 281), (131, 281),
          (49, 3), (49, 107), (53, 106), (53, 315), (72, 30), (72, 107)]
HOMMES = [(2, 27), (11, 27), (12, 27), (7, 27), (9, 27)]   # Bundesliga 2015/16 : 34 matchs seulement


def main():
    comp = {(c["competition_id"], c["season_id"]): c for c in competitions()}
    rows = []
    for cid, sid in FEMMES + HOMMES:
        c = comp[(cid, sid)]
        print(f"  {c['competition_name']} {c['season_name']}…", flush=True)
        s = pd.DataFrame(shots_for_competition(cid, sid))
        s["competition"] = f"{c['competition_name']} {c['season_name']}"
        s["genre"] = "femmes" if c["competition_gender"] == "female" else "hommes"
        s["type"] = "tournoi" if c["competition_international"] else "championnat"
        rows.append(s)
    shots = pd.concat(rows, ignore_index=True)
    out = ROOT / "resultats"
    out.mkdir(exist_ok=True)
    shots.to_csv(out / "etude2_tirs.csv.gz", index=False)
    d = prepare(shots)
    res = []
    for (comp_name, genre, typ), g in d.groupby(["competition", "genre", "type"]):
        res.append({"competition": comp_name, "genre": genre, "type": typ, **summary(g)})
    for genre, g in d.groupby("genre"):
        res.append({"competition": f"Ensemble {genre}", "genre": genre, "type": "ensemble", **summary(g)})
    f = d[d["genre"] == "femmes"]
    for typ, g in f.groupby("type"):
        res.append({"competition": f"Femmes, {typ}s", "genre": "femmes", "type": "ensemble", **summary(g)})
    tab = pd.DataFrame(res)
    tab.to_csv(out / "etude2_par_competition.csv", index=False)
    cols = ["competition", "matchs", "tirs", "cpa_part_xg", "cpa_ic_bas", "cpa_ic_haut",
            "cpa_sans_touche_part_xg", "cpa_strict_part_xg", "cpa_adverse_part_xg", "cpa_adverse_ic_bas",
            "cpa_adverse_ic_haut", "cpa_adverse_part_buts"]
    with pd.option_context("display.width", 200, "display.max_columns", 20):
        print(tab[cols].round(3).to_string(index=False))


if __name__ == "__main__":
    main()
