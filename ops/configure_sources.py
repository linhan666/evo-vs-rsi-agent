#!/usr/bin/env python3
"""Configure the two Source instances through the documented Management API.

Run on the host that serves the panel (127.0.0.1:3082). Standard library only,
so it works on the server's Python 3.12 without pip.

  github : disabled, but keeps the repository and the agent CLI that setup probes.
  local  : enabled, inbox/outbox under the repository's gitignored .artifacts/.

A settings save that changes setup fields restarts the runtime; the Source kinds
are re-registered during that window, so every read waits for the kind to appear.
"""
import json
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "http://127.0.0.1:3082/orchestrator/api/"
HEADERS = {"x-orchestrator-request": "1", "Content-Type": "application/json"}
REPOSITORY = "linhan666/evo-vs-rsi-agent"
CLI = "/home/linhan_cluster/.local/bin/gh-agent"
ROOT = "/home/linhan_cluster/evo_vs_rsi/.artifacts"


def call(path, method="GET", body=None):
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(BASE + path, data=data, headers=HEADERS, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", "replace")
        raise SystemExit(f"{method} {path} -> {error.code}: {detail}")


def sources_by_id(wanted=("github", "local")):
    """Read the Source instances, waiting for every wanted kind to be registered."""
    missing = list(wanted)
    for _ in range(40):
        by_id = {source["id"]: source for source in call("settings")["sources"]}
        missing = [kind for kind in wanted if kind not in by_id]
        if not missing:
            return by_id
        time.sleep(1)
    raise SystemExit(f"kinds not registered after 40s: {missing}")


def main():
    by_id = sources_by_id()
    print("sources:", {key: (value["value"]["enabled"], value["revision"]) for key, value in by_id.items()})

    github = by_id["github"]
    print("github saved:", call("settings/" + urllib.parse.quote("source:github", safe=""), "PUT", {
        "value": {"enabled": False, "config": {"repository": REPOSITORY, "cli": CLI}},
        "revision": github["revision"],
    }))
    time.sleep(3)

    by_id = sources_by_id()
    local = by_id["local"]
    print("local saved:", call("settings/" + urllib.parse.quote("source:local", safe=""), "PUT", {
        "value": {"enabled": True, "config": {
            "inboxDir": f"{ROOT}/inbox",
            "outboxDir": f"{ROOT}/outbox",
            "pollSeconds": 5,
            "archive": True,
        }},
        "revision": local["revision"],
    }))
    time.sleep(5)

    state = call("state")
    print("setup:", json.dumps(state.get("setup"), ensure_ascii=False))
    print("health:", json.dumps(state.get("health"), ensure_ascii=False))


if __name__ == "__main__":
    main()
