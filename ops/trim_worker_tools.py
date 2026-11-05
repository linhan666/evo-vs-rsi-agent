#!/usr/bin/env python3
"""Cut the worker's generic file/web tool surface to the job tools (idempotent).

science_009 empirically showed the generic fs tools reach far beyond the ticket
directory (an outside write succeeded; the protected test CSV was readable), so
the worker keeps only the job tools — every real task in science_007/008 ran on
the scientific tools alone. The main Session keeps `skill` but loses `read`,
which only duplicates `orchestrator_read` for its resources.
"""
import pathlib

ROOT = pathlib.Path.home() / "evo_vs_rsi"
sessions = ROOT / "src/app/sessions.ts"
text = sessions.read_text(encoding="utf-8")

start = text.index("const WORK_TOOLS = [")
end = text.index("]", start)
trimmed = ("// Generic file/web tools removed after the science_009 boundary mapping: the fs sandbox\n"
           "// root is far wider than the ticket directory, and every real task ran on the scientific\n"
           "// tools alone. Restore only together with a real isolation boundary (B-005).\n"
           "const WORK_TOOLS = ['job_output', 'job_list', 'job_kill']")
sessions.write_text(text[:start] + trimmed + text[end + 1:], encoding="utf-8")
print("worker tools trimmed")

master_old = "['skill', 'read', 'read_image', 'job_output', 'job_list', 'job_kill']"
master_new = "['skill', 'job_output', 'job_list', 'job_kill']"
if master_old in sessions.read_text(encoding="utf-8"):
    t = sessions.read_text(encoding="utf-8")
    sessions.write_text(t.replace(master_old, master_new, 1), encoding="utf-8")
    print("main Session trimmed")

spec = ROOT / "tests/runtime.spec.ts"
text = spec.read_text(encoding="utf-8")
pairs = [
    ("{ allow: ['skill', 'read', 'read_image', 'job_output', 'job_list', 'job_kill'] }",
     "{ allow: ['skill', 'job_output', 'job_list', 'job_kill'] }"),
    ("{ allow: ['read', 'read_image', 'grep', 'job_output', 'job_list', 'job_kill', 'web_search', 'skill'] }",
     "{ allow: ['job_output', 'job_list', 'job_kill'] }"),
]
changed = 0
for old, new in pairs:
    count = text.count(old)
    if count:
        text = text.replace(old, new)
        changed += count
if changed:
    spec.write_text(text, encoding="utf-8")
print(f"runtime spec: {changed} expectation group(s) updated")
