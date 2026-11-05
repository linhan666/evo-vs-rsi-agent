#!/usr/bin/env python3
"""Refuse to start the runtime when `lib/` is older than the TypeScript sources.

Defect (science_005): source changed, `pnpm build` was not run, and the service
silently loaded the previous tool surface. The runtime reads `lib/`, so freshness
is a launch precondition, not a nicety. Exit 1 = stale or missing build.
"""
import pathlib
import sys

ROOT = pathlib.Path.home() / "evo_vs_rsi"
lib = ROOT / "lib/index.js"
src = ROOT / "src"

if not lib.exists():
    print(f"STALE: {lib} is missing; run `pnpm build` before starting the service")
    sys.exit(1)

lib_mtime = lib.stat().st_mtime
newest = max((p.stat().st_mtime for p in src.rglob("*.ts")), default=0)
newest_file = max(src.rglob("*.ts"), key=lambda p: p.stat().st_mtime)

if newest > lib_mtime:
    print(f"STALE: {newest_file.relative_to(ROOT)} is newer than {lib.relative_to(ROOT)}; run `pnpm build` first")
    sys.exit(1)

print("lib is fresh; safe to start the service")
