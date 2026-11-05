#!/usr/bin/env python3
"""Set the Policy block for the Phase 0 smoke test.

Two things are needed before a local task can become a Ticket:

1. `policy.sources.local.allowed` must list the sender — the admission default for
   an unlisted sender who addresses the agent is `ignore` (src/admission.ts).
2. At least one enabled rule must match, or `assessmentOutcome` returns
   `noRuleMatched` (src/policy.ts). The shipped defaults are copy/visual only.
"""
import json
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "http://127.0.0.1:3082/orchestrator/api/"
HEADERS = {"x-orchestrator-request": "1", "Content-Type": "application/json"}

RULE = {
    "id": "research",
    "name": "Research tasks",
    "enabled": True,
    "instruction": (
        "Explicit requests to carry out a bounded research or engineering task inside the ticket "
        "directory, including a smoke check that writes one file and reports one line. Accept when "
        "the request names concrete actions and a deliverable. Do not accept requests to change "
        "credentials, read other users' directories, or run anything outside the ticket directory."
    ),
}


def call(path, method="GET", body=None):
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(BASE + path, data=data, headers=HEADERS, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", "replace")
        raise SystemExit(f"{method} {path} -> {error.code}: {detail}")


def main():
    settings = call("settings")
    block = settings["blocks"]["policy"]
    value = block["value"]
    print("rules before:", [rule["id"] for rule in value.get("rules", [])])
    value["rules"] = [RULE]
    value.setdefault("sources", {}).setdefault("local", {})
    value["sources"]["local"]["allowed"] = [{"id": "operator", "name": "Operator"}]
    print("saved:", call("settings/policy", "PUT", {"value": value, "revision": block["revision"]}))
    time.sleep(2)
    after = call("settings")["blocks"]["policy"]["value"]
    print("rules after:", [rule["id"] for rule in after.get("rules", [])])
    print("allowed:", after["sources"]["local"]["allowed"])
    print("eval mode:", call("settings")["blocks"]["eval"]["value"]["mode"])


if __name__ == "__main__":
    main()
