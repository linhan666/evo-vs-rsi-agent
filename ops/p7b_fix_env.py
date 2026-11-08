#!/usr/bin/env python3
"""Make env.sh safe under `set -u`.

The cost-instrumentation block appended earlier used `$NODE_OPTIONS` bare inside a
`case` and an `export`. With `set -u` in the caller (the orchestration script),
an unset NODE_OPTIONS aborts the whole shell — which is what killed the
orchestrator on its first attempt, not the `tmux kill-server` line.

Idempotent.
"""
from pathlib import Path

ENV = Path(__file__).resolve().parent.parent / "env.sh"

def main() -> int:
    text = ENV.read_text(encoding="utf-8")
    before = text
    text = text.replace('case ":$NODE_OPTIONS:" in', 'case ":${NODE_OPTIONS:-}:" in')
    text = text.replace('export NODE_OPTIONS="$NODE_OPTIONS --require',
                        'export NODE_OPTIONS="${NODE_OPTIONS:-} --require')
    if text == before:
        print("env.sh: already safe under set -u")
        return 0
    ENV.write_text(text, encoding="utf-8")
    print("env.sh: NODE_OPTIONS references guarded")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
