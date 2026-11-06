"""P5-05 VersionManager: a ledger of what is actually running, and how to undo it.

Promotion used to be "change a default and write a JSON note". That leaves three
questions unanswered: which version is live, what evidence admitted it, and what
exactly to revert. This module keeps an append-only ledger of versions, each
pinned to a git SHA and to the gate verdict that let it in.

It never edits code. `rollback` marks the version and prints the exact revert for
a person to apply, because the red line is that promotion and rollback are human
actions; the tool's job is to make sure the human is looking at the right facts.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess

SCHEMA_VERSION = "1"


def ledger_path(explicit: str | None = None) -> str:
    if explicit:
        return explicit
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(root, "evolution", "versions.json")


def load(path: str) -> dict:
    if not os.path.exists(path):
        return {"schema_version": SCHEMA_VERSION, "entries": []}
    return json.loads(open(path, encoding="utf-8").read())


def save(path: str, ledger: dict) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(ledger, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def next_version(ledger: dict) -> str:
    numbers = [int(entry["version"][1:]) for entry in ledger["entries"]
               if entry.get("version", "").startswith("v") and entry["version"][1:].isdigit()]
    return "v{0}".format(max(numbers, default=0) + 1)


def active(ledger: dict) -> list[dict]:
    return [entry for entry in ledger["entries"] if entry.get("status") == "active"]


def current(ledger: dict) -> dict | None:
    entries = active(ledger)
    return entries[-1] if entries else None


def head_sha(cwd: str | None = None) -> str | None:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=cwd, capture_output=True,
                              text=True, check=True).stdout.strip()
    except Exception:
        return None


def applied(sha: str | None, cwd: str | None = None) -> bool:
    """True when `sha` is still in this branch's history.

    Equality with HEAD would be wrong: HEAD moves for unrelated reasons while the
    promoted change stays in place. What matters is that the commit the version was
    recorded at is an ancestor of HEAD — unless rollback marked it otherwise.
    """
    if not sha:
        return False
    try:
        return subprocess.run(["git", "merge-base", "--is-ancestor", sha, "HEAD"], cwd=cwd,
                              capture_output=True).returncode == 0
    except Exception:
        return False


def record(path: str, spec: dict, gate: dict, *, git_sha: str | None, note: str, force: bool = False) -> dict:
    verdict = gate.get("verdict")
    if verdict != "pass" and not force:
        raise SystemExit("refusing to record {0}: gate verdict is {1} (blocking: {2})".format(
            spec.get("candidate_id"), verdict, gate.get("blocking")))
    ledger = load(path)
    change = (spec.get("changes") or [{}])[0]
    entry = {
        "version": next_version(ledger),
        "candidate_id": spec.get("candidate_id"),
        "recorded_at": __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc).isoformat(timespec="seconds"),
        "git_sha": git_sha,
        "status": "active",
        "change": {"type": change.get("type"), "key": change.get("key"), "value": change.get("value")},
        "gate": {"verdict": verdict, "blocking": gate.get("blocking", []),
                 "needs_human_number": gate.get("needs_human_number", [])},
        "rollback": spec.get("rollback") or "revert the change above; single code path, no branch to delete",
        "note": note,
        **({"forced": True} if force and verdict != "pass" else {}),
    }
    # A version is live only while every earlier one is closed: the ledger should
    # never read as if two contradictory defaults were active at once.
    for older in active(ledger):
        older["status"] = "superseded"
    ledger["entries"].append(entry)
    save(path, ledger)
    return entry


def rollback(path: str, version: str) -> dict:
    ledger = load(path)
    found = next((item for item in ledger["entries"] if item["version"] == version), None)
    if not found:
        raise SystemExit("no such version: {0}".format(version))
    if found["status"] == "rolled_back":
        raise SystemExit("{0} was already rolled back".format(version))
    found["status"] = "rolled_back"
    found["rolled_back_at"] = __import__("datetime").datetime.now(
        __import__("datetime").timezone.utc).isoformat(timespec="seconds")
    save(path, ledger)
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="evolution versions")
    parser.add_argument("--ledger", default=None)
    sub = parser.add_subparsers(dest="command", required=True)

    rec = sub.add_parser("record", help="record a promoted candidate as the live version")
    rec.add_argument("--spec", required=True)
    rec.add_argument("--gate", required=True, help="gate.py output json")
    rec.add_argument("--note", required=True)
    rec.add_argument("--git-sha", default=None)
    rec.add_argument("--force", action="store_true", help="record despite a non-pass gate; marks the entry")

    sub.add_parser("list", help="list versions")
    sub.add_parser("current", help="print the live version")

    back = sub.add_parser("rollback", help="mark a version rolled back and print the revert")
    back.add_argument("--version", required=True)

    check = sub.add_parser("check", help="compare the live version's git SHA with HEAD")
    check.add_argument("--cwd", default=None)

    args = parser.parse_args(argv)
    path = ledger_path(args.ledger)

    if args.command == "record":
        spec = json.loads(open(args.spec, encoding="utf-8").read())
        gate = json.loads(open(args.gate, encoding="utf-8").read())
        entry = record(path, spec, gate, git_sha=args.git_sha or head_sha(), note=args.note, force=args.force)
        print(json.dumps({"version": entry["version"], "candidate": entry["candidate_id"],
                          "git_sha": entry["git_sha"], "status": entry["status"]}))
        return 0

    if args.command == "list":
        ledger = load(path)
        print(json.dumps([{key: item[key] for key in ("version", "candidate_id", "status", "git_sha", "recorded_at")}
                          for item in ledger["entries"]], ensure_ascii=False))
        return 0

    if args.command == "current":
        entry = current(load(path))
        print(json.dumps(entry, ensure_ascii=False) if entry else "null")
        return 0 if entry else 1

    if args.command == "rollback":
        entry = rollback(path, args.version)
        print(json.dumps({"version": entry["version"], "status": entry["status"],
                          "revert": entry["rollback"],
                          "reminder": "apply the revert by hand, rebuild, run ops/canary_check.py, then smoke a ticket"},
                         ensure_ascii=False))
        return 0

    entry = current(load(path))
    if not entry:
        print(json.dumps({"error": "no active version"}))
        return 1
    head = head_sha(args.cwd)
    match = applied(entry.get("git_sha"), args.cwd)
    print(json.dumps({"version": entry["version"], "recorded_sha": entry.get("git_sha"),
                      "head_sha": head, "applied": match}))
    return 0 if match else 1


if __name__ == "__main__":
    raise SystemExit(main())
