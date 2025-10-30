import importlib
import json
import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))


@pytest.fixture(autouse=True)
def ensure_api_key(monkeypatch):
    monkeypatch.setenv("API_FOOTBALL_KEY", "test-key")


def sample_legs():
    return [
        {
            "fid": 101,
            "league": "League A",
            "teams": "Team A vs Team B",
            "time": "2024-04-01 18:00 • 101",
            "market": "Match Winner",
            "pick_name": "Home",
            "odd": 1.5,
        },
        {
            "fid": 102,
            "league": "League B",
            "teams": "Team C vs Team D",
            "time": "2024-04-01 20:00 • 102",
            "market": "BTTS",
            "pick_name": "Yes",
            "odd": 1.25,
        },
        {
            "fid": 103,
            "league": "League C",
            "teams": "Team E vs Team F",
            "time": "2024-04-01 22:00 • 103",
            "market": "Over/Under",
            "pick_name": "Over 2.5",
            "odd": 1.8,
        },
    ]


def test_write_pages_generates_snapshot(tmp_path, monkeypatch):
    focus_bets = importlib.import_module("focus_bets")
    out_dir = tmp_path / "public"
    focus_bets.OUT_DIR = out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    legs = sample_legs()
    tickets = [
        legs[:2],
        [legs[2]],
        [],
    ]

    meta = focus_bets.write_pages("2024-04-01", tickets)

    assert meta == {"count": 3, "files": ["2plus.json", "3plus.json", "4plus.json"]}

    snapshot_path = out_dir / "feed_snapshot.json"
    assert snapshot_path.exists()

    with snapshot_path.open("r", encoding="utf-8") as fh:
        snapshot = json.load(fh)

    assert snapshot["date"] == "2024-04-01"
    assert [t["name"] for t in snapshot["tickets"]] == ["2plus", "3plus", "4plus"]
    assert snapshot["tickets"][0]["total_odds"] == pytest.approx(1.88, rel=1e-2)
    assert snapshot["tickets"][1]["total_odds"] == pytest.approx(1.8, rel=1e-2)
    assert snapshot["tickets"][2]["total_odds"] == 0


def test_evening_evaluation_from_snapshot(tmp_path, monkeypatch):
    focus_bets = importlib.import_module("focus_bets")
    out_dir = tmp_path / "public"
    focus_bets.OUT_DIR = out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    legs = sample_legs()
    focus_bets.write_pages("2024-04-01", [legs[:2], [legs[2]], []])

    evaluate_results = importlib.import_module("evaluate_results")
    evaluate_results.PUBLIC = out_dir

    def fake_fetch(fid):
        return {
            101: {"status": "FT", "home_goals": 2, "away_goals": 0},
            102: {"status": "FT", "home_goals": 1, "away_goals": 1},
            103: {"status": "FT", "home_goals": 3, "away_goals": 0},
        }[fid]

    monkeypatch.setattr(evaluate_results, "fetch_fixture_result", fake_fetch)

    evaluate_results.main()

    evaluation_path = out_dir / "evaluation.json"
    assert evaluation_path.exists()

    with evaluation_path.open("r", encoding="utf-8") as fh:
        evaluation = json.load(fh)

    assert evaluation["date"] == "2024-04-01"
    labels = {t["name"]: t for t in evaluation["tickets"]}

    assert labels["2plus"]["all_hit"] is True
    assert labels["2plus"]["total_label"].endswith("✅")
    assert labels["3plus"]["all_hit"] is True
    leg_results = [leg["result"]["hit"] for leg in labels["2plus"]["legs"]]
    assert leg_results == [True, True]

    assert labels["3plus"]["legs"][0]["result"]["emoji"] == "✅"
