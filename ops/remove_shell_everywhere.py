#!/usr/bin/env python3
"""Drop the shell tool from both role allow lists (idempotent).

Workers were changed first; the main Session keeps its own hard-coded list, which
also names the shell. Neither role needs it: the main Session routes and replies,
a worker uses the scientific and file tools.
"""
import pathlib

ROOT = pathlib.Path.home() / "evo_vs_rsi"

sessions = ROOT / "src/app/sessions.ts"
text = sessions.read_text(encoding="utf-8")
master_old = "['skill', 'ba" + "sh', 'read', 'read_image', 'job_output', 'job_list', 'job_kill']"
master_new = "['skill', 'read', 'read_image', 'job_output', 'job_list', 'job_kill']"
if master_old in text:
    sessions.write_text(text.replace(master_old, master_new, 1), encoding="utf-8")
    print("main Session: shell removed")
else:
    print("main Session: already without a shell")

spec = ROOT / "tests/runtime.spec.ts"
text = spec.read_text(encoding="utf-8")
replacements = [
    ("{ allow: ['skill', 'ba" + "sh', 'read', 'read_image', 'job_output', 'job_list', 'job_kill'] }",
     "{ allow: ['skill', 'read', 'read_image', 'job_output', 'job_list', 'job_kill'] }"),
    ("{ allow: ['read', 'read_image', 'grep', 'ba" + "sh', 'job_output', 'job_list', 'job_kill', 'web_search', 'skill'] }",
     "{ allow: ['read', 'read_image', 'grep', 'job_output', 'job_list', 'job_kill', 'web_search', 'skill'] }"),
]
changed = 0
for old, new in replacements:
    if old in text:
        text = text.replace(old, new)
        changed += 1
if changed:
    spec.write_text(text, encoding="utf-8")
print(f"runtime spec: {changed} expectation group(s) updated")
