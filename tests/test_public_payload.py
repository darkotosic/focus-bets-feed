import unittest
from unittest.mock import patch

import focus_bets
import evaluate_results


class TestPublicPayloadSchema(unittest.TestCase):
    def test_leg_payload_compatible_with_evaluate_results(self) -> None:
        leg_source = {
            "fid": 101,
            "country": "England",
            "league": "🏟 England — Premier League",
            "teams": "⚽ Arsenal vs Chelsea",
            "time": "⏰ 2024-05-01 18:30",
            "market": "Double Chance",
            "pick_name": "1X",
            "odd": 1.65,
        }
        public_leg = focus_bets._serialize_leg_for_public(leg_source)
        self.assertEqual(public_leg["fixture_id"], 101)
        self.assertEqual(public_leg["market"], "Double Chance")
        self.assertEqual(public_leg["pick"], "1X")
        self.assertEqual(public_leg["odd"], 1.65)

        ticket_payload = {
            "date": "2024-05-01",
            "target_odds": 2.0,
            "total_odds": 2.0,
            "legs": [public_leg],
        }

        fx_stub = {
            "fixture": {"status": {"short": "FT"}},
            "goals": {"home": 2, "away": 1},
            "score": {"halftime": {"home": 1, "away": 0}},
        }

        with patch("evaluate_results._get_fixture", return_value=fx_stub):
            result = evaluate_results.evaluate_ticket(ticket_payload)

        self.assertEqual(result["legs"][0]["result"], "win")
        self.assertEqual(result["ticket_result"], "win")


if __name__ == "__main__":
    unittest.main()
