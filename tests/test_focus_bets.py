from __future__ import annotations

import contextlib
import json
import os
import tempfile
import unittest
from unittest import mock

import focus_bets


class RunWithoutOpenAIKeyTest(unittest.TestCase):
    def test_run_without_openai_key_uses_fallback_without_http(self):
        captured_logs = []
        captured_daily: list[str] = []
        dummy_ticket = {
            "text": "Ticket 1",
            "payload": {
                "date": "2024-01-01",
                "target_odds": 2.0,
                "total_odds": 2.1,
                "legs": [],
            },
            "target_key": "2plus",
        }

        def capture_log(msg: str) -> None:
            captured_logs.append(msg)

        def capture_daily(_: str, tickets: list[str]) -> None:
            captured_daily.extend(tickets)

        with contextlib.ExitStack() as stack:
            stack.enter_context(mock.patch.object(focus_bets, "OPENAI_API_KEY", None))
            stack.enter_context(mock.patch.object(focus_bets, "DRY_RUN", True))
            stack.enter_context(
                mock.patch.object(
                    focus_bets,
                    "build_three_tickets",
                    autospec=True,
                    return_value=[dummy_ticket],
                )
            )
            stack.enter_context(
                mock.patch.object(
                    focus_bets,
                    "write_daily_log",
                    autospec=True,
                    side_effect=capture_daily,
                )
            )
            stack.enter_context(
                mock.patch.object(
                    focus_bets,
                    "write_public_feeds",
                    autospec=True,
                )
            )
            stack.enter_context(
                mock.patch.object(
                    focus_bets,
                    "post_to_telegram",
                    autospec=True,
                )
            )
            stack.enter_context(
                mock.patch.object(
                    focus_bets,
                    "airtable_insert_rows",
                    autospec=True,
                    return_value={"ok": True, "status": 0},
                )
            )
            stack.enter_context(
                mock.patch.object(
                    focus_bets,
                    "_log",
                    autospec=True,
                    side_effect=capture_log,
                )
            )
            stack.enter_context(
                mock.patch.object(
                    focus_bets.httpx.Client,
                    "post",
                    autospec=True,
                    side_effect=AssertionError(
                        "OpenAI HTTP request should not be attempted when the API key is missing"
                    ),
                )
            )

            result = focus_bets.run(date_str="2024-01-01")

        self.assertEqual(result["tickets_count"], 1)
        self.assertTrue(captured_daily, "daily log should capture ticket output")
        self.assertIn(focus_bets.REASONING_FALLBACK, captured_daily[0])

        disabled_logs = [msg for msg in captured_logs if "OpenAI reasoning disabled" in msg]
        self.assertEqual(len(disabled_logs), 1, disabled_logs)


class WritePublicFeedsTest(unittest.TestCase):
    def test_write_public_feeds_creates_expected_files(self):
        ticket = {
            "text": "Ticket 1",
            "target_key": "2plus",
            "payload": {
                "date": "2024-02-02",
                "target_odds": 2.0,
                "total_odds": 2.5,
                "legs": [
                    {
                        "fixture_id": 123,
                        "market": "Over/Under",
                        "pick": "Over 2.5",
                        "odd": 1.25,
                        "league": "🏟 League",
                        "teams": "⚽ Team A vs Team B",
                        "time": "⏰ 2024-02-02 20:00",
                        "pick_display": "• Over/Under → Over 2.5: 1.25",
                    }
                ],
            },
        }

        with tempfile.TemporaryDirectory() as tmp:
            cwd = os.getcwd()
            os.chdir(tmp)
            try:
                focus_bets.write_public_feeds("2024-02-02", [ticket])
                with open("public/2plus.json", "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.assertEqual(data["date"], "2024-02-02")
                self.assertEqual(data["legs"][0]["fixture_id"], 123)
                self.assertEqual(data["legs"][0]["pick"], "Over 2.5")
                self.assertEqual(data["legs"][0]["pick_display"], "• Over/Under → Over 2.5: 1.25")
                self.assertEqual(data["target_odds"], 2.0)
                with open("public/3plus.json", "r", encoding="utf-8") as f:
                    data3 = json.load(f)
                self.assertEqual(data3["date"], "2024-02-02")
                self.assertEqual(data3["legs"], [])
            finally:
                os.chdir(cwd)


if __name__ == "__main__":
    unittest.main()
