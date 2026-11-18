"""Étude 3 — penalties : zones, pied, réussite, femmes contre hommes.
Lit resultats/etude2_tirs.csv.gz (produit par etude2_cpa.py, qui contient tous les tirs).
Sorties : resultats/etude3_*.csv
"""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from etudes.penalties import diff_ci, n_per_group, prepare, rate_table, wilson  # noqa: E402


def pct(x):
    return f"{100 * x:.1f} %"


def main():
    out = ROOT / "resultats"
    p = prepare(pd.read_csv(out / "etude2_tirs.csv.gz"))
    groups = {"femmes, en match": p[(p.genre == "femmes") & ~p.seance],
              "femmes, séances de tirs au but": p[(p.genre == "femmes") & p.seance],
              "hommes, en match": p[(p.genre == "hommes") & ~p.seance]}
    rows, zones, pieds = [], [], []
    for name, g in groups.items():
        r, lo, hi = wilson(int(g.but.sum()), len(g))
        rows.append({"groupe": name, "penalties": len(g), "reussite": r, "ic_bas": lo, "ic_haut": hi,
                     "hors_cadre": (g.cote == "hors cadre").mean(), "pied_gauche": (g.body_part == "Left Foot").mean(),
                     "bas": (g.hauteur == "bas").mean(), "centre": (g.cote == "centre").mean()})
        zones.append(rate_table(g, "zone").assign(groupe=name))
        pieds.append(rate_table(g.dropna(subset=["cote_pied"]), "cote_pied").assign(groupe=name))
    tab = pd.DataFrame(rows)
    z = pd.concat(zones)
    pi = pd.concat(pieds)
    f, h = groups["femmes, en match"], groups["hommes, en match"]
    d, lo, hi = diff_ci(int(f.but.sum()), len(f), int(h.but.sum()), len(h))
    fs = groups["femmes, séances de tirs au but"]
    d2, lo2, hi2 = diff_ci(int(fs.but.sum()), len(fs), int(f.but.sum()), len(f))
    fh, fb = f[f.hauteur == "haut"], f[f.hauteur == "bas"]
    d3, lo3, hi3 = diff_ci(int(fh.but.sum()), len(fh), int(fb.but.sum()), len(fb))
    hh, hb = h[h.hauteur == "haut"], h[h.hauteur == "bas"]
    d4, lo4, hi4 = diff_ci(int(hh.but.sum()), len(hh), int(hb.but.sum()), len(hb))
    fn, fo = f[f.cote_pied == "naturel"], f[f.cote_pied == "opposé"]
    d5, lo5, hi5 = diff_ci(int(fn.but.sum()), len(fn), int(fo.but.sum()), len(fo))
    base = (f.but.mean() + h.but.mean()) / 2
    need = n_per_group(base, base + 0.05)
    comp = pd.DataFrame([
        {"comparaison": "femmes − hommes (en match)", "ecart": d, "ic_bas": lo, "ic_haut": hi},
        {"comparaison": "séances − match (femmes)", "ecart": d2, "ic_bas": lo2, "ic_haut": hi2},
        {"comparaison": f"haut − bas, femmes en match ({len(fh)} contre {len(fb)})", "ecart": d3, "ic_bas": lo3, "ic_haut": hi3},
        {"comparaison": f"haut − bas, hommes en match ({len(hh)} contre {len(hb)})", "ecart": d4, "ic_bas": lo4, "ic_haut": hi4},
        {"comparaison": "côté naturel − côté opposé, femmes en match", "ecart": d5, "ic_bas": lo5, "ic_haut": hi5},
        {"comparaison": "penalties nécessaires par groupe pour détecter 5 points", "ecart": need, "ic_bas": None, "ic_haut": None},
    ])
    tab.to_csv(out / "etude3_reussite.csv", index=False)
    z.to_csv(out / "etude3_zones.csv", index=False)
    pi.to_csv(out / "etude3_cote_pied.csv", index=False)
    comp.to_csv(out / "etude3_comparaisons.csv", index=False)
    with pd.option_context("display.width", 200):
        print(tab.round(3).to_string(index=False))
        print(comp.round(3).to_string(index=False))
        print(z.round(3).to_string(index=False))
        print(pi.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
