import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from etudes.fiabilite import minutes_needed, reliability_at, player_match_table, poste, spearman_brown, split_half  # noqa: E402

A = {"id": 1, "name": "A"}


def ev(t, minute, player=None, **kw):
    e = {"type": {"name": t}, "minute": minute, "second": 0, "team": A, **kw}
    if player:
        e["player"] = {"id": player, "name": f"J{player}"}
    return e


def match_events():
    return [
        ev("Starting XI", 0, tactics={"lineup": [{"player": {"id": 1, "name": "J1"}, "position": {"name": "Center Back"}},
                                                  {"player": {"id": 2, "name": "J2"}, "position": {"name": "Center Forward"}}]}),
        ev("Pass", 10, 1, position={"name": "Center Back"}, location=[40, 40],
           **{"pass": {"end_location": [70, 40], "length": 30}}),                       # progressive, réussie
        ev("Pass", 20, 1, position={"name": "Center Back"}, location=[40, 40],
           **{"pass": {"end_location": [45, 40], "length": 5, "outcome": {"name": "Incomplete"}}}),
        ev("Pass", 25, 1, position={"name": "Center Back"}, location=[40, 0],
           **{"pass": {"end_location": [60, 0], "length": 20, "type": {"name": "Throw-in"}}}),  # touche : ignorée
        ev("Shot", 30, 2, position={"name": "Center Forward"}, location=[110, 40],
           shot={"type": {"name": "Open Play"}, "statsbomb_xg": 0.2, "outcome": {"name": "Goal"}}),
        ev("Shot", 35, 2, position={"name": "Center Forward"}, location=[108, 40],
           shot={"type": {"name": "Penalty"}, "statsbomb_xg": 0.78, "outcome": {"name": "Goal"}}),
        ev("Substitution", 60, 2, substitution={"replacement": {"id": 3, "name": "J3"}}),
        ev("Foul Committed", 80, 1, foul_committed={"card": {"name": "Red Card"}}),
        ev("Pressure", 90, 3, position={"name": "Right Wing"}),
    ]


def test_minutes_remplacement_et_carton_rouge():
    t = {r["player_id"]: r for r in player_match_table(match_events())}
    assert t[1]["minutes"] == pytest.approx(80)   # exclue à la 80e
    assert t[2]["minutes"] == pytest.approx(60)   # remplacée à la 60e
    assert t[3]["minutes"] == pytest.approx(30)   # entrée à la 60e, fin à la 90e


def test_comptes_et_postes():
    t = {r["player_id"]: r for r in player_match_table(match_events())}
    assert t[1]["passes"] == 2 and t[1]["passes_reussies"] == 1 and t[1]["passes_progressives"] == 1
    assert t[1]["fautes_commises"] == 1 and t[1]["poste"] == "défense"
    assert t[2]["tirs"] == 1 and t[2]["xg"] == pytest.approx(0.2)   # penalty exclu
    assert t[3]["pressions"] == 1 and t[3]["poste"] == "attaque"
    assert poste("Goalkeeper") == "gardienne" and poste("Left Defensive Midfield") == "milieu"


def test_spearman_brown_et_minutes():
    assert spearman_brown(0.5, 2) == pytest.approx(2 / 3)
    # r = 0,5 sur 450 min par moitié : 0,7 demande 2,33 fois plus de minutes
    assert minutes_needed(0.5, 450) == pytest.approx(0.7 * 0.5 / (0.5 * 0.3) * 450)


def simulate(signal, n_players=120, n_matches=20, seed=0):
    r = np.random.default_rng(seed)
    rows = []
    for p in range(n_players):
        rate = max(0.1, 3 + signal * r.normal())
        for m in range(n_matches):
            rows.append({"unit": p, "minutes": 90, "x": r.poisson(rate)})
    return pd.DataFrame(rows)


def test_split_half_retrouve_le_signal():
    fort = split_half(simulate(2.0), "x", n_splits=30)["fiabilite_saison"]
    faible = split_half(simulate(0.2), "x", n_splits=30)["fiabilite_saison"]
    assert fort > 0.9 and faible < 0.5


def test_fiabilite_a_minutes_egales():
    # même demi-saison projetée à 2 fois ses minutes = Spearman-Brown classique
    assert reliability_at(0.5, 500, 1000) == pytest.approx(spearman_brown(0.5, 2))
    # projeter à moins de minutes fait baisser la fiabilité
    assert reliability_at(0.6, 1000, 500) < 0.6
