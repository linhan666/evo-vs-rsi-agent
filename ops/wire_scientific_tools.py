#!/usr/bin/env python3
"""Wire the scientific tools into the worker tool set (idempotent).

`src/app/tools/executor.ts` exists only in the checkout, so this patch runs there.
Anchors are asserted: a changed upstream shape fails loudly instead of editing
the wrong place.
"""
import pathlib

ROOT = pathlib.Path.home() / "evo_vs_rsi"
path = ROOT / "src/app/tools/executor.ts"
source = path.read_text(encoding="utf-8")
changed = False

IMPORT_ANCHOR = "import { AcknowledgementSchema, readTool, tool, type Tool } from './tool.ts'"
IMPORT_LINE = "\nimport { scientificTools } from '../../research/tools.ts'"
if "scientificTools" not in source:
    assert IMPORT_ANCHOR in source, "tool.ts import anchor missing"
    source = source.replace(IMPORT_ANCHOR, IMPORT_ANCHOR + IMPORT_LINE, 1)
    changed = True

RETURN_ANCHOR = ("export function executorTools(host: ExecutorToolsHost, ticket: Ticket): Tool[] {\n"
                 "  const ticketId = ticket.id\n"
                 "  return [")
if "...scientificTools(ticket)" not in source:
    assert RETURN_ANCHOR in source, "executorTools return anchor missing"
    source = source.replace(RETURN_ANCHOR, RETURN_ANCHOR + "\n    ...scientificTools(ticket),", 1)
    changed = True

if changed:
    path.write_text(source, encoding="utf-8")
print("changed" if changed else "already wired")
