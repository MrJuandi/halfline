"""Tests de la unión de fuentes (sin red ni ficheros)."""
import pandas as pd

from futdata.matches import attach, learn_names


def _frame(rows, id_col=None):
    cols = ["league", "season", "date", "home", "away", "home_goals", "away_goals"]
    df = pd.DataFrame(rows, columns=cols + ([id_col] if id_col else []))
    df["date"] = pd.to_datetime(df["date"])
    if id_col:
        df["kickoff_utc"] = df["date"].dt.tz_localize("UTC")
    return df


FD = _frame([
    ("SP1", 2024, "2024-08-15", "Ath Bilbao", "Getafe", 1, 1),
    ("SP1", 2024, "2024-08-22", "Getafe", "Ath Madrid", 0, 2),
    ("SP1", 2024, "2024-08-29", "Ath Madrid", "Ath Bilbao", 3, 1),
    ("SP1", 2024, "2024-09-05", "Ath Bilbao", "Ath Madrid", 2, 0),
    ("SP1", 2024, "2024-09-12", "Getafe", "Ath Bilbao", 1, 2),
    ("SP1", 2024, "2024-09-19", "Ath Madrid", "Getafe", 4, 0),
])
OTHER = _frame([
    # misma fecha o un día después (hora UTC), nombres distintos
    ("SP1", 2024, "2024-08-15", "Athletic Club", "Getafe", 1, 1, "a"),
    ("SP1", 2024, "2024-08-23", "Getafe", "Atlético Madrid", 0, 2, "b"),
    ("SP1", 2024, "2024-08-29", "Atlético Madrid", "Athletic Club", 3, 1, "c"),
    ("SP1", 2024, "2024-09-05", "Athletic Club", "Atlético Madrid", 2, 0, "d"),
    ("SP1", 2024, "2024-09-12", "Getafe", "Athletic Club", 1, 2, "e"),
    ("SP1", 2024, "2024-09-19", "Atlético Madrid", "Getafe", 4, 0, "f"),
], id_col="x_id")


def test_learn_names_maps_by_votes():
    names = learn_names(FD, OTHER, "x").set_index("name")
    assert names.loc["Athletic Club", "canonical"] == "Ath Bilbao"
    assert names.loc["Atlético Madrid", "canonical"] == "Ath Madrid"
    assert names.accepted.all()


def test_attach_joins_every_match_with_matching_score():
    out = attach(FD, OTHER, learn_names(FD, OTHER, "x"), "x_id")
    assert list(out["x_id"]) == ["a", "b", "c", "d", "e", "f"]
    assert out["x_id_score_ok"].all()


def _promoted(n_matches: int, rivals: list[tuple[str, int]]):
    """`Hull` juega n_matches; en cada fecha otros partidos de FD coinciden en marcador (rivals: equipo, veces)."""
    fd, other, days = [], [], pd.date_range("2026-08-15", periods=n_matches, freq="7D")
    noise = [t for t, k in rivals for _ in range(k)]
    for i, d in enumerate(days):
        fd.append(("E0", 2026, d, "Hull", f"R{i % 3}", 1, 0))
        other.append(("E0", 2026, d, "Hull City", f"R{i % 3}", 1, 0, f"h{i}"))
    for i, team in enumerate(noise):
        fd.append(("E0", 2026, days[i % n_matches], team, f"S{i}", 1, 0))
    return _frame(fd), _frame(other, "x_id")


def test_promoted_team_accepted_when_coincidences_are_spread():
    """Caso real (nov. 2026): 11 votos de 19 (57,9 %), pero el segundo candidato solo tiene 2."""
    fd, other = _promoted(11, [("A", 2)] + [(f"N{i}", 1) for i in range(6)])
    row = learn_names(fd, other, "x").set_index("name").loc["Hull City"]
    assert (row.canonical, row.votes, row.share) == ("Hull", 11, 0.579)
    assert row.accepted
    assert attach(fd, other, learn_names(fd, other, "x"), "x_id")["x_id"].notna().sum() == 11


def test_name_rejected_and_logged_when_second_candidate_competes(caplog):
    fd, other = _promoted(5, [("A", 3)])
    row = learn_names(fd, other, "x").set_index("name").loc["Hull City"]
    assert not row.accepted
    assert "nombres rechazados" in caplog.text


def test_name_rejected_with_too_few_votes():
    fd, other = _promoted(2, [])
    assert not learn_names(fd, other, "x").set_index("name").loc["Hull City", "accepted"]
