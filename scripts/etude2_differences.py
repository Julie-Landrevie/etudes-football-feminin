"""Différences de part du xG (phases arrêtées) entre groupes, IC 95 % par
bootstrap sur les matchs (2 000 tirages). Lit resultats/etude2_tirs.csv.gz."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from etudes.coups_pieds_arretes import prepare  # noqa: E402


def per_match(g, flag):
    m = g.groupby("match_id").apply(lambda x: pd.Series({"n": x.loc[x[flag], "xg"].sum(), "d": x["xg"].sum()}),
                                    include_groups=False)
    return m["n"].to_numpy(), m["d"].to_numpy()


def diff(a, b, flag, n_boot=2000, seed=2):
    na, da = per_match(a, flag)
    nb, db = per_match(b, flag)
    r = np.random.default_rng(seed)
    ia, ib = r.integers(0, len(na), (n_boot, len(na))), r.integers(0, len(nb), (n_boot, len(nb)))
    boot = na[ia].sum(1) / da[ia].sum(1) - nb[ib].sum(1) / db[ib].sum(1)
    lo, hi = np.percentile(boot, [2.5, 97.5])
    return na.sum() / da.sum() - nb.sum() / db.sum(), lo, hi


def main():
    d = prepare(pd.read_csv(ROOT / "resultats" / "etude2_tirs.csv.gz"))
    F, H = d[d.genre == "femmes"], d[d.genre == "hommes"]
    FC, FT = F[F.type == "championnat"], F[F.type == "tournoi"]
    rows = []
    for flag in ["cpa", "cpa_sans_touche", "cpa_strict", "cpa_adverse"]:
        for name, a, b in [("femmes − hommes", F, H), ("championnats féminins − hommes", FC, H),
                           ("tournois − championnats féminins", FT, FC)]:
            est, lo, hi = diff(a, b, flag)
            rows.append({"definition": flag, "comparaison": name, "ecart_points": 100 * est,
                         "ic_bas": 100 * lo, "ic_haut": 100 * hi})
    det = []
    for name, g in [("femmes", F), ("hommes", H)]:
        t, a = g["xg"].sum(), g[g.cpa_adverse]
        cf = a[a.origine == "coup franc"]
        det.append({"genre": name, **{f"part_xg_{o}": 100 * a.loc[a.origine == o, "xg"].sum() / t
                                       for o in ["corner", "coup franc", "touche"]},
                    "coup_franc_direct_part_xg_cf": 100 * cf.loc[cf.coup_franc_direct, "xg"].sum() / cf["xg"].sum(),
                    "xg_par_tir_cpa_adverse": a["xg"].mean(), "xg_par_tir_jeu_courant": g.loc[~g.cpa, "xg"].mean()})
    out = pd.DataFrame(rows)
    out.to_csv(ROOT / "resultats" / "etude2_differences.csv", index=False)
    pd.DataFrame(det).to_csv(ROOT / "resultats" / "etude2_detail_moitie_adverse.csv", index=False)
    print(out.round(1).to_string(index=False))
    print(pd.DataFrame(det).round(3).to_string(index=False))


if __name__ == "__main__":
    main()
