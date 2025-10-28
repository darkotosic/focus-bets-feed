from __future__ import annotations

import contextlib
import unittest
from unittest import mock

import focus_bets


class RunWithoutOpenAIKeyTest(unittest.TestCase):
    def test_run_without_openai_key_uses_fallback_without_http(self):
        captured_logs = []
        captured_daily: list[str] = []
        dummy_ticket = "Ticket 1"

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


if __name__ == "__main__":
    unittest.main()
