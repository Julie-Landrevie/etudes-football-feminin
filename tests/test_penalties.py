import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from etudes.penalties import diff_ci, height, n_per_group, natural, prepare, side, wilson  # noqa: E402


def test_zones_du_but():
    assert side(36.5) == "gauche" and side(40.0) == "centre" and side(43.9) == "droite"
    assert side(35.0) == "hors cadre" and side(45.0) == "hors cadre"
    assert height(0.3) == "bas" and height(2.0) == "haut"


def test_cote_naturel_selon_le_pied():
    assert natural("gauche", "Right Foot") == "naturel"
    assert natural("droite", "Right Foot") == "opposé"
    assert natural("droite", "Left Foot") == "naturel"
    assert natural("centre", "Left Foot") == "centre"
    assert natural("hors cadre", "Right Foot") is None


def test_wilson_valeurs_connues():
    p, lo, hi = wilson(8, 10)
    assert p == pytest.approx(0.8)
    assert lo == pytest.approx(0.4902, abs=1e-3) and hi == pytest.approx(0.9433, abs=1e-3)
    assert wilson(0, 5)[1] == pytest.approx(0.0, abs=1e-9)   # jamais négatif


def test_ecart_et_puissance():
    d, lo, hi = diff_ci(75, 100, 75, 100)
    assert d == pytest.approx(0.0) and lo < 0 < hi
    # détecter 75 % contre 80 % demande plus de 1 000 penalties par groupe
    assert 1000 < n_per_group(0.75, 0.80) < 1200


def test_prepare_separe_match_et_seance():
    s = pd.DataFrame([
        {"shot_type": "Penalty", "outcome": "Goal", "period": 2, "end_y": 37.0, "end_z": 0.4, "body_part": "Right Foot"},
        {"shot_type": "Penalty", "outcome": "Saved", "period": 5, "end_y": 42.0, "end_z": 2.0, "body_part": "Left Foot"},
        {"shot_type": "Penalty", "outcome": "Off T", "period": 1, "end_y": 46.0, "end_z": 1.0, "body_part": "Right Foot"},
        {"shot_type": "Open Play", "outcome": "Goal", "period": 1, "end_y": 40.0, "end_z": 0.5, "body_part": "Head"},
    ])
    p = prepare(s)
    assert len(p) == 3
    assert list(p["zone"]) == ["gauche bas", "droite haut", "hors cadre"]
    assert list(p["seance"]) == [False, True, False]
    assert list(p["cote_pied"][:2]) == ["naturel", "naturel"] and pd.isna(p["cote_pied"].iloc[2])
