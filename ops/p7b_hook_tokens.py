#!/usr/bin/env python3
"""Record reasoning_tokens in the LLM usage ledger.

Why: the harness never sets `reasoningEffort` (both role models default to null),
so every call runs at the provider's default thinking budget. Measured on the same
prompt/model: omitting the parameter yields 76 reasoning tokens, `high` 180, `none`
0 with no reasoning_content at all. Without this field the ledger cannot tell
"the agent thought harder" from "the agent wrote more", which makes any future
thinking-effort arm impossible to quantify.

Additive and idempotent; the running service already has the old module in memory,
so this takes effect on the next service restart.
"""
from pathlib import Path

HOOK = Path(__file__).resolve().parent.parent / "ops" / "usage_hook.cjs"


def main() -> int:
    text = HOOK.read_text(encoding="utf-8")
    if "reasoning_tokens" in text:
        print("usage_hook: reasoning_tokens already recorded")
        return 0

    before = text
    text = text.replace(
        "const merged = { model: null, prompt_tokens: 0, completion_tokens: 0, cached_tokens: 0 }",
        "const merged = { model: null, prompt_tokens: 0, completion_tokens: 0, cached_tokens: 0, reasoning_tokens: 0 }")
    text = text.replace(
        "    if (completion !== undefined) merged.completion_tokens = completion",
        "    if (completion !== undefined) merged.completion_tokens = completion\n"
        "    // Thinking budget actually spent. Without it the ledger cannot separate\n"
        "    // \"reasoned longer\" from \"wrote more\", and an effort-vs-quality arm is\n"
        "    // unmeasurable (see HANDOFF section on reasoning effort).\n"
        "    const reasoning = usage.completion_tokens_details && usage.completion_tokens_details.reasoning_tokens\n"
        "    if (typeof reasoning === 'number') merged.reasoning_tokens = reasoning")
    if text == before:
        print("usage_hook: ANCHOR NOT FOUND")
        return 1
    HOOK.write_text(text, encoding="utf-8")
    print("usage_hook: reasoning_tokens captured")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
