"""Turn the usage ledger into money.

`ops/usage_hook.js` records every model call's token counts; this prices them with
the DeepSeek Flash rate card (2026-09-10) and can attribute them to a time window,
which is how a Phase 6 group's cost is separated from another's.

Rate card, CNY per 1M tokens (off-peak; peak doubles on weekdays 09:00-12:00 and
14:00-18:00 Beijing time, Chinese public holidays excluded):

    input, cache miss   1.00
    input, cache hit    0.02
    output              4.00

Usage:
  python ops/cost_report.py [--usage FILE] [--since ISO] [--until ISO] [--json]
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os

RATES_PER_MILLION = {"input_miss": 1.00, "input_hit": 0.02, "output": 4.00}
BEIJING = dt.timezone(dt.timedelta(hours=8))
PEAK_HOURS = ((9, 12), (14, 18))


def is_peak(when: dt.datetime) -> bool:
    local = when.astimezone(BEIJING)
    if local.weekday() >= 5:
        return False
    return any(start <= local.hour < end for start, end in PEAK_HOURS)


def price_line(line: dict) -> float:
    prompt = float(line.get("prompt_tokens") or 0)
    cached = float(line.get("cached_tokens") or 0)
    output = float(line.get("completion_tokens") or 0)
    when = dt.datetime.fromisoformat(line["ts"].replace("Z", "+00:00"))
    multiplier = 2.0 if is_peak(when) else 1.0
    cost = ((prompt - cached) * RATES_PER_MILLION["input_miss"]
            + cached * RATES_PER_MILLION["input_hit"]
            + output * RATES_PER_MILLION["output"]) / 1_000_000
    return cost * multiplier


def load(path: str, since: str | None, until: str | None) -> list[dict]:
    if not os.path.exists(path):
        return []
    start = dt.datetime.fromisoformat(since.replace("Z", "+00:00")) if since else None
    end = dt.datetime.fromisoformat(until.replace("Z", "+00:00")) if until else None
    rows = []
    for raw in open(path, encoding="utf-8"):
        raw = raw.strip()
        if not raw:
            continue
        line = json.loads(raw)
        if line.get("event") or not line.get("prompt_tokens"):
            continue
        when = dt.datetime.fromisoformat(line["ts"].replace("Z", "+00:00"))
        if start and when < start:
            continue
        if end and when > end:
            continue
        rows.append(line)
    return rows


def summarise(rows: list[dict]) -> dict:
    total = {"calls": len(rows),
             "prompt_tokens": sum(int(r.get("prompt_tokens") or 0) for r in rows),
             "cached_tokens": sum(int(r.get("cached_tokens") or 0) for r in rows),
             "completion_tokens": sum(int(r.get("completion_tokens") or 0) for r in rows)}
    total["cost_cny"] = round(sum(price_line(r) for r in rows), 4)
    total["cost_cny_peak"] = round(total["cost_cny"] * 2, 4)  # upper bound if every call landed in peak
    return total


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ops cost_report")
    parser.add_argument("--usage", default=None)
    parser.add_argument("--since", default=None)
    parser.add_argument("--until", default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = args.usage or os.path.join(root, "scientific", ".artifacts", "usage.jsonl")

    rows = load(path, args.since, args.until)
    summary = summarise(rows)
    summary["usage_file"] = path
    summary["window"] = {"since": args.since, "until": args.until}
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
