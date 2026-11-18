import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from etudes.coups_pieds_arretes import bootstrap_share, prepare, shares, summary  # noqa: E402
from etudes.donnees import extract_shots  # noqa: E402


def shot(match, pattern, xg, outcome="Off T", stype="Open Play", period=1, rank=5, rx=None):
    if rx is None and pattern != "Regular Play":
        rx = 110.0
    return {"match_id": match, "period": period, "minute": 10, "team": "A", "play_pattern": pattern,
            "shot_type": stype, "outcome": outcome, "body_part": "Right Foot", "xg": xg,
            "rank_in_possession": rank, "restart_x": rx}


def base():
    return pd.DataFrame([
        shot(1, "Regular Play", 0.3, "Goal"),
        shot(1, "From Corner", 0.1, rank=2),
        shot(1, "From Corner", 0.2, "Goal", rank=8),          # corner, hors fenêtre stricte
        shot(1, "Regular Play", 0.79, "Goal", stype="Penalty"),  # exclu
        shot(2, "From Throw In", 0.1, rank=1, rx=30.0),       # touche dans son camp
        shot(2, "From Free Kick", 0.1, "Goal", stype="Free Kick", rank=1),  # coup franc direct
        shot(2, "Regular Play", 0.2),
        shot(2, "Regular Play", 0.9, "Goal", period=5),        # séance de tirs au but, exclue
    ])


def test_exclusions_penalties_et_seances():
    d = prepare(base())
    assert len(d) == 6
    assert (d["shot_type"] != "Penalty").all() and (d["period"] != 5).all()


def test_parts_xg_tirs_buts():
    d = prepare(base())
    s = shares(d, "cpa")
    assert s["part_xg"] == pytest.approx(0.5 / 1.0)      # 0.1+0.2+0.1+0.1 sur 1.0
    assert s["part_tirs"] == pytest.approx(4 / 6)
    assert s["part_buts"] == pytest.approx(2 / 3)


def test_sans_touche_et_strict():
    d = prepare(base())
    assert shares(d, "cpa_sans_touche")["part_xg"] == pytest.approx(0.4)
    assert shares(d, "cpa_strict")["part_xg"] == pytest.approx(0.3)   # le corner au rang 8 sort


def test_bootstrap_encadre_estimation():
    d = prepare(pd.concat([base().assign(match_id=base()["match_id"] + 10 * k) for k in range(30)]))
    est, lo, hi = bootstrap_share(d, "cpa", "xg", n_boot=300)
    assert est == pytest.approx(0.5)
    assert lo <= est <= hi
    assert hi - lo < 0.2


def test_summary_detail_coup_franc_direct():
    s = summary(prepare(base()), n_boot=50)
    assert s["coup_franc_direct_part_xg_cf"] == pytest.approx(1.0)
    assert s["matchs"] == 2 and s["tirs"] == 6 and s["buts"] == 3


def test_extract_shots_rang_dans_la_possession():
    team, opp = {"id": 1, "name": "A"}, {"id": 2, "name": "B"}
    ev = [
        {"id": "a", "type": {"name": "Pass"}, "possession": 3, "possession_team": team, "team": team},
        {"id": "b", "type": {"name": "Ball Receipt*"}, "possession": 3, "possession_team": team, "team": team},
        {"id": "c", "type": {"name": "Pressure"}, "possession": 3, "possession_team": team, "team": opp},
        {"id": "d", "type": {"name": "Shot"}, "possession": 3, "possession_team": team, "team": team,
         "period": 1, "minute": 4, "play_pattern": {"name": "From Corner"},
         "shot": {"type": {"name": "Open Play"}, "outcome": {"name": "Goal"},
                  "body_part": {"name": "Head"}, "statsbomb_xg": 0.12}},
    ]
    s = extract_shots(ev)
    assert len(s) == 1
    assert s[0]["rank_in_possession"] == 2   # passe puis tir ; réception et pressing adverse non comptés
    assert s[0]["xg"] == pytest.approx(0.12) and s[0]["outcome"] == "Goal"


def test_moitie_adverse():
    d = prepare(base())
    assert shares(d, "cpa_adverse")["part_xg"] == pytest.approx(0.4)   # la touche à x = 30 sort


def test_extract_shots_lieu_de_la_remise_en_jeu():
    team = {"id": 1, "name": "A"}
    ev = [
        {"id": "a", "type": {"name": "Pass"}, "possession": 7, "possession_team": team, "team": team,
         "location": [118.0, 0.5], "pass": {"type": {"name": "Corner"}}},
        {"id": "b", "type": {"name": "Shot"}, "possession": 7, "possession_team": team, "team": team,
         "period": 1, "minute": 9, "play_pattern": {"name": "From Corner"},
         "shot": {"type": {"name": "Open Play"}, "outcome": {"name": "Saved"}, "statsbomb_xg": 0.05}},
    ]
    assert extract_shots(ev)[0]["restart_x"] == pytest.approx(118.0)


def test_coup_franc_direct_sans_passe_avant():
    team = {"id": 1, "name": "A"}
    ev = [{"id": "a", "type": {"name": "Shot"}, "possession": 4, "possession_team": team, "team": team,
           "location": [95.0, 40.0], "period": 2, "minute": 70, "play_pattern": {"name": "From Free Kick"},
           "shot": {"type": {"name": "Free Kick"}, "outcome": {"name": "Goal"}, "statsbomb_xg": 0.07}}]
    s = extract_shots(ev)[0]
    assert s["restart_x"] == pytest.approx(95.0) and s["rank_in_possession"] == 1
