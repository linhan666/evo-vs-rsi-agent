#!/usr/bin/env python3
"""Register the local Source in the four places step 10 of docs/008-cookbook.md names.

Idempotent: re-running changes nothing. Every anchor is asserted, so a changed
upstream shape fails loudly instead of silently editing the wrong line.
"""
import pathlib

ROOT = pathlib.Path.home() / "evo_vs_rsi"
changed = []


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def write(path, text):
    (ROOT / path).write_text(text, encoding="utf-8")
    changed.append(path)


# 1. Build entry.
p = "tsdown.config.ts"
s = read(p)
if "local-watch" not in s:
    old = "'feishu-watch': 'src/sources/feishu.ts' }"
    assert old in s, "tsdown anchor missing"
    write(p, s.replace(old, "'feishu-watch': 'src/sources/feishu.ts', 'local-watch': 'src/sources/local.ts' }"))

# 2. Package export.
p = "package.json"
s = read(p)
if "./local-watch" not in s:
    old = '    "./feishu-watch": "./lib/feishu-watch.js",\n'
    assert old in s, "package.json anchor missing"
    write(p, s.replace(old, old + '    "./local-watch": "./lib/local-watch.js",\n'))

# 3. Bundle insert.
p = "cordis.patch.yml"
s = read(p)
if "dsh-superagent-local" not in s:
    old = (
        "    - id: dsh-superagent-feishu\n"
        "      name: dsh-superagent/feishu-watch\n"
        "      disabled: true\n"
    )
    assert old in s, "cordis.patch.yml anchor missing"
    new = old + (
        "    # Local task-file Source: enabled, but inert until a profile sets an inbox directory.\n"
        "    - id: dsh-superagent-local\n"
        "      name: dsh-superagent/local-watch\n"
        "      disabled: false\n"
    )
    write(p, s.replace(old, new))

# 4. Architecture module and test tables (tests/docs.spec.ts enforces both).
p = "docs/007-architecture.md"
s = read(p)
if "src/sources/local.ts" not in s:
    anchor = [line for line in s.split("\n") if line.startswith("| `src/sources/feishu-image.ts`")]
    assert anchor, "module table anchor missing"
    row = ("| `src/sources/local.ts` | The local task-file kind and plugin entry, exported as `./local-watch`: "
           "one JSON file per request, an inbox directory as the receiving scope, and one reply file per message |")
    s = s.replace(anchor[0], anchor[0] + "\n" + row, 1)
    old_sentence = ("`src/sources/github.ts` and `src/sources/feishu.ts` are also the entries of the two Source plugins, "
                    "built by `tsdown.config.ts` and exported in `package.json` as `./github-watch` and `./feishu-watch`. "
                    "The bundle's `cordis.patch.yml` inserts the three plugins, with Feishu disabled.")
    new_sentence = ("`src/sources/github.ts`, `src/sources/feishu.ts` and `src/sources/local.ts` are also the entries of "
                    "the three Source plugins, built by `tsdown.config.ts` and exported in `package.json` as "
                    "`./github-watch`, `./feishu-watch` and `./local-watch`. The bundle's `cordis.patch.yml` inserts the "
                    "four plugins, with Feishu disabled and the local Source enabled but inert until a profile sets an "
                    "inbox directory.")
    assert old_sentence in s, "architecture prose anchor missing"
    s = s.replace(old_sentence, new_sentence, 1)
    write(p, s)

p = "docs/007-architecture.md"
s = read(p)
if "tests/local.spec.ts" not in s:
    anchor = [line for line in s.split("\n") if line.startswith("| `tests/sources.spec.ts`")]
    assert anchor, "test table anchor missing"
    row = ("| `tests/local.spec.ts` | The local task-file Source: translation into Trigger, Thread, Actor and Channel; "
           "one stored Trigger per file with archiving; malformed files left in place; scope; idempotent replies; "
           "setup and switch health |")
    write(p, s.replace(anchor[0], anchor[0] + "\n" + row, 1))

print("changed:", changed or "nothing (already registered)")
