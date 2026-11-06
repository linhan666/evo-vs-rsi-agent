"""Cost accounting: the numbers behind Phase 6's llm_cost column."""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ops"))
from cost_report import is_peak, load, price_line, summarise  # noqa: E402


class PricingTests(unittest.TestCase):
    def test_off_peak_uncached_call_prices_to_the_rate_card(self):
        line = {"ts": "2026-11-08T12:00:00+00:00", "prompt_tokens": 1_000_000,
                "cached_tokens": 0, "completion_tokens": 100_000}
        # 1M input @1 + 0.1M output @4 = 1 + 0.4 = 1.40 CNY (Sunday 20:00 Beijing: off-peak)
        self.assertAlmostEqual(price_line(line), 1.40, places=4)

    def test_cached_input_costs_a_fiftieth(self):
        line = {"ts": "2026-11-08T12:00:00+00:00", "prompt_tokens": 1_000_000,
                "cached_tokens": 1_000_000, "completion_tokens": 0}
        self.assertAlmostEqual(price_line(line), 0.02, places=4)

    def test_beijing_peak_doubles_the_bill(self):
        off_peak = {"ts": "2026-11-08T12:00:00+00:00", "prompt_tokens": 1_000_000,
                    "cached_tokens": 0, "completion_tokens": 0}          # Sunday
        peak = {"ts": "2026-11-06T02:00:00+00:00", "prompt_tokens": 1_000_000,
                "cached_tokens": 0, "completion_tokens": 0}              # Friday 10:00 Beijing
        self.assertFalse(is_peak(__import__("datetime").datetime.fromisoformat(off_peak["ts"])))
        self.assertTrue(is_peak(__import__("datetime").datetime.fromisoformat(peak["ts"])))
        self.assertAlmostEqual(price_line(peak), 2 * price_line(off_peak), places=4)

    def test_ledger_summary_counts_calls_and_tokens(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "usage.jsonl")
            rows = [
                {"ts": "2026-11-08T12:00:00+00:00", "prompt_tokens": 1000, "cached_tokens": 200,
                 "completion_tokens": 100},
                {"ts": "2026-11-08T12:00:01+00:00", "prompt_tokens": 500, "cached_tokens": 0,
                 "completion_tokens": 50},
                {"ts": "2026-11-08T12:00:02+00:00", "event": "hook-installed"},   # not a call
            ]
            with open(path, "w", encoding="utf-8") as handle:
                for row in rows:
                    handle.write(json.dumps(row) + "\n")
            summary = summarise(load(path, None, None))
            self.assertEqual(summary["calls"], 2)
            self.assertEqual(summary["prompt_tokens"], 1500)
            self.assertEqual(summary["cached_tokens"], 200)
            self.assertGreater(summary["cost_cny"], 0)
            self.assertGreater(summary["cost_cny_peak"], summary["cost_cny"])

    def test_window_filters_by_time(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "usage.jsonl")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(json.dumps({"ts": "2026-11-01T00:00:00+00:00", "prompt_tokens": 1,
                                         "completion_tokens": 1}) + "\n")
                handle.write(json.dumps({"ts": "2026-11-08T00:00:00+00:00", "prompt_tokens": 1,
                                         "completion_tokens": 1}) + "\n")
            rows = load(path, "2026-11-05T00:00:00+00:00", None)
            self.assertEqual(len(rows), 1)


if __name__ == "__main__":
    unittest.main()
