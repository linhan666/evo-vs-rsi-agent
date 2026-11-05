#!/usr/bin/env python3
"""Watch one local task travel Source → Engine → Executor → Report.

Polls the Management API and the outbox directory; prints only changes so the
output stays short. Exits 0 as soon as a reply file appears.
"""
import json
import os
import time
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:3082/orchestrator/api/"
HEADERS = {"x-orchestrator-request": "1"}
OUTBOX = "/home/linhan_cluster/evo_vs_rsi/.artifacts/outbox"
INBOX = "/home/linhan_cluster/evo_vs_rsi/.artifacts/inbox"


def call(path):
    request = urllib.request.Request(BASE + path, headers=HEADERS)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as error:
        return {"error": error.code, "detail": error.read().decode("utf-8", "replace")[:300]}


def snapshot():
    state = call("state")
    health = state.get("health", {})
    parts = {key: value.get("state") for key, value in health.items()}
    sources = call("sources")
    local = next((item for item in sources.get("sources", []) if item.get("id") == "local"), {}) if "sources" in sources else {}
    return {
        "setup": (state.get("setup") or {}).get("problem") if isinstance(state.get("setup"), dict) else state.get("setup"),
        "health": parts,
        "local_state": local.get("state"),
        "stats": local.get("stats"),
        "filtered": local.get("filtered"),
        "load": state.get("load"),
        "outbox": sorted(os.listdir(OUTBOX)) if os.path.isdir(OUTBOX) else [],
        "inbox": sorted(name for name in os.listdir(INBOX) if name.endswith(".json")) if os.path.isdir(INBOX) else [],
    }


def main():
    print("inbox before:", snapshot()["inbox"])
    previous = None
    for round_number in range(30):
        current = snapshot()
        brief = {key: current[key] for key in ("health", "local_state", "stats", "outbox", "inbox")}
        if brief != previous:
            print(f"[{round_number * 10:3d}s]", json.dumps(brief, ensure_ascii=False))
            previous = brief
        if current["outbox"]:
            print("REPLY FILE(S):", current["outbox"])
            for name in current["outbox"]:
                with open(os.path.join(OUTBOX, name), encoding="utf-8") as handle:
                    print(name, "->", handle.read()[:800])
            return
        time.sleep(10)
    print("NO REPLY within 300s")
    print("final:", json.dumps(snapshot(), ensure_ascii=False)[:1200])


if __name__ == "__main__":
    main()
