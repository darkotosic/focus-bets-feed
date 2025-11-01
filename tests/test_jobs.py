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
            103: {"status": "NS", "home_goals": None, "away_goals": None},
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
    assert labels["3plus"]["all_hit"] is False
    leg_results = [leg["result"]["hit"] for leg in labels["2plus"]["legs"]]
    assert leg_results == [True, True]

    assert labels["3plus"]["legs"][0]["result"]["emoji"] == "❌"

    ticket_file = out_dir / "eval_2plus.json"
    assert ticket_file.exists()
    with ticket_file.open("r", encoding="utf-8") as fh:
        ticket_eval = json.load(fh)

    assert ticket_eval == {
        "ticket_result": "win",
        "legs": [
            {"fixture_id": 101, "result": "win", "score_ft": "2-0"},
            {"fixture_id": 102, "result": "win", "score_ft": "1-1"},
        ],
    }

    three_plus = out_dir / "eval_3plus.json"
    assert three_plus.exists()
    with three_plus.open("r", encoding="utf-8") as fh:
        data = json.load(fh)

    assert data["ticket_result"] == "pending"
    assert data["legs"] == [{"fixture_id": 103, "result": "pending"}]

    four_plus = out_dir / "eval_4plus.json"
    with four_plus.open("r", encoding="utf-8") as fh:
        data = json.load(fh)

    assert data == {"ticket_result": "pending", "legs": []}


def test_ticket_eval_loss_file(tmp_path, monkeypatch):
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
            101: {"status": "FT", "home_goals": 0, "away_goals": 1},
            102: {"status": "FT", "home_goals": 1, "away_goals": 0},
            103: {"status": "FT", "home_goals": 0, "away_goals": 3},
        }[fid]

    monkeypatch.setattr(evaluate_results, "fetch_fixture_result", fake_fetch)

    evaluate_results.main()

    ticket_file = out_dir / "eval_2plus.json"
    with ticket_file.open("r", encoding="utf-8") as fh:
        ticket_eval = json.load(fh)

    assert ticket_eval["ticket_result"] == "lose"
    assert ticket_eval["legs"][0]["result"] == "lose"
    assert ticket_eval["legs"][1]["result"] == "lose"
    assert ticket_eval["legs"][0]["score_ft"] == "0-1"


def test_evening_evaluation_extended_markets(tmp_path, monkeypatch):
    out_dir = tmp_path / "public"
    out_dir.mkdir(parents=True, exist_ok=True)

    snapshot = {
        "date": "2024-04-02",
        "tickets": [
            {
                "name": "custom",
                "target": 2.0,
                "total_odds": 1.0,
                "legs": [
                    {
                        "fid": 201,
                        "league": "League X",
                        "teams": "Team X vs Team Y",
                        "time": "2024-04-02 18:00",
                        "market": "1st Half Goals",
                        "pick": "Over 0.5",
                        "odds": 1.2,
                    },
                    {
                        "fid": 202,
                        "league": "League X",
                        "teams": "Team X vs Team Y",
                        "time": "2024-04-02 18:00",
                        "market": "Home Team Goals",
                        "pick": "Over 0.5",
                        "odds": 1.2,
                    },
                    {
                        "fid": 203,
                        "league": "League X",
                        "teams": "Team X vs Team Y",
                        "time": "2024-04-02 18:00",
                        "market": "Away Team Goals",
                        "pick": "Over 0.5",
                        "odds": 1.2,
                    },
                    {
                        "fid": 204,
                        "league": "League X",
                        "teams": "Team X vs Team Y",
                        "time": "2024-04-02 18:00",
                        "market": "Over/Under",
                        "pick": "Under 3.5",
                        "odds": 1.4,
                    },
                ],
            }
        ],
    }

    with (out_dir / "feed_snapshot.json").open("w", encoding="utf-8") as fh:
        json.dump(snapshot, fh)

    evaluate_results = importlib.import_module("evaluate_results")
    evaluate_results.PUBLIC = out_dir

    def fake_fetch(fid):
        data = {
            201: {
                "status": "FT",
                "home_goals": 2,
                "away_goals": 1,
                "halftime_home": 1,
                "halftime_away": 0,
            },
            202: {
                "status": "FT",
                "home_goals": 1,
                "away_goals": 0,
                "halftime_home": 0,
                "halftime_away": 0,
            },
            203: {
                "status": "FT",
                "home_goals": 3,
                "away_goals": 0,
                "halftime_home": 2,
                "halftime_away": 0,
            },
            204: {
                "status": "FT",
                "home_goals": 1,
                "away_goals": 1,
                "halftime_home": 1,
                "halftime_away": 1,
            },
        }
        return data[fid]

    monkeypatch.setattr(evaluate_results, "fetch_fixture_result", fake_fetch)

    evaluate_results.main()

    evaluation_path = out_dir / "evaluation.json"
    with evaluation_path.open("r", encoding="utf-8") as fh:
        evaluation = json.load(fh)

    ticket = evaluation["tickets"][0]
    results = {leg["market"]: leg["result"]["hit"] for leg in ticket["legs"]}

    assert results["1st Half Goals"] is True
    assert results["Home Team Goals"] is True
    assert results["Away Team Goals"] is False
    assert results["Over/Under"] is True
