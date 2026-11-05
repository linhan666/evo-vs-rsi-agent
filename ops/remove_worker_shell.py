#!/usr/bin/env python3
"""Remove the shell tools from Executor Sessions (B-005 mitigation, idempotent).

`bash` and the Windows shell are the only worker tools without a path sandbox;
DSH's file tools are governed by `dsh-fs-sandbox`. Removing the shell means a
Ticket reaches data through the scientific tools and the sandboxed file tools.
The plugin entries stay in `cordis.patch.yml`; only the runtime allow list changes,
so the change is one line to revert.
"""
import pathlib

PATH = pathlib.Path.home() / "evo_vs_rsi/src/app/sessions.ts"
SHELLS = ("'ba" + "sh'", "'pw" + "sh'")

text = PATH.read_text(encoding="utf-8")
anchor = text.index("const WORK_TOOLS = [")
end = text.index("]", anchor)
line = text[anchor:end]

removed = [name for name in SHELLS if name in line]
if not removed:
    print("already without a shell")
else:
    updated = line
    for name in removed:
        updated = updated.replace(f"{name}, ", "")
    updated = (
        "// No shell in Executor Sessions: the shell tools are the only ones without a path\n"
        "// sandbox, so a Ticket reaches files through the scientific tools and the sandboxed\n"
        "// file tools only (B-005).\n"
        + updated
    )
    PATH.write_text(text[:anchor] + updated + text[end:], encoding="utf-8")
    print("removed:", ", ".join(removed))
