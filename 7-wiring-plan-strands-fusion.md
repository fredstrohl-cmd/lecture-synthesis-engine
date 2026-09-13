# Wiring plan: fuse the Strands halt into the engine (tonight)

Goal: replace ingest.py's fake halt (the `<HALT>` text adapter) with the real one -
the auditor calls an actual SDK tool, the run pauses for your answer, then Pass 2
finishes with your resolution recorded inline. One file to paste, one cage test to run.
Everything below was re-verified tonight against strands-agents 1.55.1.

Time estimate: 30-45 minutes. Do the steps in order. Stop after Step 5 if you're
fried - a green cage test means the fuse is done.

## What changes conceptually (read once, then just follow steps)

- Old: one raw Gemini call. The model "halts" by printing `<HALT>` tags. Text does
  not pause anything - the RUN_MODE_ADAPTER comment in ingest.py says so itself.
- New: a Strands `Agent` with one tool, `ask_human`. When the auditor finds a
  critical contradiction it calls the tool, the tool prints the question and blocks
  on your keyboard input, your answer goes back into the agent as the tool result,
  and Pass 2 formats the notes with "Resolved per student: ..." inline. The pause is
  structural now - the agent's event loop is literally waiting inside the tool call.
- The v1.1 auditor prompt, the scratchpad quarantine, and the output format do not
  change. Thursday's cage results still stand; tonight only the wiring underneath
  changes.

## Step 1 - Install the SDK (one command)

PowerShell, in your project folder:

```
pip install strands-agents==1.55.1 google-genai
```

Watch out: the package is `google-genai`, NOT `google-generativeai`. The old
ingest.py used `google-generativeai`; the Strands Gemini provider imports
`from google import genai`, which only exists in the newer `google-genai` package.
Having both installed is fine.

## Step 2 - Set your key (PowerShell syntax)

```
$env:GEMINI_API_KEY = "paste-your-AI-Studio-key-here"
```

Optional - override the model if the default below misbehaves:

```
$env:GEMINI_MODEL = "gemini-3.6-flash"
```

(`gemini-3.6-flash` is the model ID Thursday's green cage run used. The old
`gemini-2.0-flash` default in ingest.py was one of the stale names.)

## Step 3 - Get the files in one folder

You need three files side by side:

- `engine.py` - the new file from Step 4 (replaces ingest.py; keep ingest.py around
  as the fallback, don't delete it)
- `adversarial-auditor-prompt-v1.1.md` - unchanged, from the Drive folder
- a test transcript - the sabotaged 08-24 Micro excerpt if you still have it,
  otherwise any Plaud export

You do NOT need to edit the prompt file. Step 4's code replaces the
`[STRANDS_SDK_TOOL_NAME]` placeholder with `ask_human` at load time.

## Step 4 - Create engine.py (paste this whole file)

```python
#!/usr/bin/env python3
"""Lecture Synthesis Engine - fused build (Strands agent + real halt tool).

The halt is now a real SDK tool call: when the auditor finds a critical
contradiction it calls ask_human, the run pauses for your answer, then Pass 2
finishes with the resolution recorded inline.

Usage:
    python engine.py lecture-03.txt
    python engine.py lecture-03.txt --prompt adversarial-auditor-prompt-v1.1.md --out output/

Setup (PowerShell):
    pip install strands-agents==1.55.1 google-genai
    $env:GEMINI_API_KEY = "your-key"
"""

import argparse
import os
import re
import sys

try:
    from strands import Agent, tool
    from strands.models.gemini import GeminiModel
except ImportError:
    sys.exit("Missing dependency: run `pip install strands-agents==1.55.1 google-genai` first.")

MODEL_ID = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")
PROMPT_FILE_DEFAULT = "adversarial-auditor-prompt-v1.1.md"


@tool
def ask_human(question: str, excerpts: str, option_a: str, option_b: str) -> str:
    """Halt the run and ask the student to resolve a critical academic contradiction.

    Call this ONLY when the transcript states the same academic fact two
    incompatible ways (a mechanism, a test result, an interpretation). Never call
    it for minor noise - typos, filler, one-off remarks. Ask ONE sharp question.
    """
    print("\n" + "=" * 60)
    print("HALT - the auditor needs you:")
    print("=" * 60)
    print(question)
    print("\nConflicting excerpts:\n" + excerpts)
    print(f"\nA) {option_a}\nB) {option_b}")
    answer = input("\nYour answer (A / B or free text): ").strip()
    return f"Student resolved the conflict: {answer}"


def load_system_prompt(path: str) -> str:
    """Load the auditor prompt (content after the '---' separator only) and bind
    the tool-name placeholder to the real tool above."""
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    if "\n---\n" in text:
        text = text.split("\n---\n", 1)[1]
    return text.strip().replace("[STRANDS_SDK_TOOL_NAME]", "ask_human")


def strip_scratchpad(text: str) -> str:
    """Defense in depth: remove any <audit_scratchpad> content that leaks through."""
    cleaned = re.sub(r"<audit_scratchpad>.*?</audit_scratchpad>", "", text, flags=re.DOTALL)
    return re.sub(r"\n{3,}", "\n\n", cleaned).strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="Plaud transcript -> Markmap study notes (Strands build)")
    parser.add_argument("transcript", help="Path to the raw Plaud transcript .txt file")
    parser.add_argument("--prompt", default=PROMPT_FILE_DEFAULT,
                        help="Path to the auditor system-prompt .md file")
    parser.add_argument("--out", default="output",
                        help="Directory for the Markmap .md output")
    args = parser.parse_args()

    if not os.path.isfile(args.transcript):
        sys.exit(f"Transcript not found: {args.transcript}")
    if not os.path.isfile(args.prompt):
        sys.exit(f"Prompt file not found: {args.prompt}")
    if not os.environ.get("GEMINI_API_KEY"):
        sys.exit("Set GEMINI_API_KEY first:  $env:GEMINI_API_KEY = '...'")

    with open(args.transcript, "r", encoding="utf-8") as f:
        transcript = f.read().strip()
    if not transcript:
        sys.exit("Transcript is empty; nothing to synthesize.")

    model = GeminiModel(
        client_args={"api_key": os.environ["GEMINI_API_KEY"]},
        model_id=MODEL_ID,
    )
    agent = Agent(
        model=model,
        system_prompt=load_system_prompt(args.prompt),
        tools=[ask_human],
    )

    print(f"Synthesizing {args.transcript} with {MODEL_ID} via Strands ...", flush=True)
    result = agent("TRANSCRIPT:\n" + transcript)
    output = strip_scratchpad(str(result))
    if not output:
        sys.exit("Agent returned empty output; nothing written.")

    os.makedirs(args.out, exist_ok=True)
    stem = os.path.splitext(os.path.basename(args.transcript))[0]
    out_path = os.path.join(args.out, stem + ".md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(output + "\n")
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
```

## Step 5 - Cage test (the only acceptance check that matters)

Run the sabotaged transcript first:

```
python engine.py sabotaged-lecture.txt
```

The fuse holds if ALL of these happen:

1. The run stops mid-way and prints the `HALT - the auditor needs you:` banner,
   with both planted lines quoted back and A/B options.
2. The cursor sits there waiting. The script is genuinely paused - this is the
   whole point of tonight.
3. You type your answer (e.g. `A`), hit Enter, and the run CONTINUES on its own.
4. It writes `output/sabotaged-lecture.md`, and the notes contain a line like
   `Resolved per student: A` where the contradiction was.
5. No `<audit_scratchpad>` text anywhere in the output file.

Then the clean transcript:

```
python engine.py clean-lecture.txt
```

Expect either clean notes with a verify-later section, or a halt on the real
contradiction it caught Thursday (your professor's genuine Gram stain flip) - both
are passes. A silent wrong answer is the only failure.

## Step 6 - If something breaks (check in this order)

- `ImportError: cannot import name 'genai' from 'google'` -> you installed
  `google-generativeai` instead of `google-genai`. Run
  `pip install google-genai`.
- `Set GEMINI_API_KEY first` -> you set the env var in a different PowerShell
  window. Env vars don't carry between windows; re-run the `$env:` line in the
  same window.
- HTTP 503 / "high demand" from the Gemini API -> the model is overloaded, not
  your code. Wait a minute and re-run, or set `$env:GEMINI_MODEL` to another
  current flash model ID from AI Studio. (Thursday's runs hit this too; retrying
  worked.)
- The model formats notes without ever calling ask_human on the sabotaged file ->
  the cage failed. Don't debug prompt wording at 1am. Note it, go to bed, that's a
  Saturday problem with fresh eyes.
- Anything else: fall back to `python ingest.py ...` (the old file still works for
  producing notes) and leave the fuse for Saturday.

## Done-for-the-night line

Green cage test = the intercept is fused into the core loop. That's the build
milestone the README describes. Saturday's list (NOT tonight): update README's
repository layout to mention engine.py, re-shoot the demo outputs with the fused
build, and only then look at the stretch below.

## Stretch (Saturday, skip tonight): phone-halt instead of keyboard-halt

Thursday's viability spike proved the interrupt/resume path for shipping the halt
to your phone instead of blocking on stdin, on the same SDK version:

```python
from strands.vended_interventions.hitl import HumanInTheLoop
agent = Agent(model=model, system_prompt=prompt, tools=[ask_human],
              interventions=[HumanInTheLoop()])
result = agent("TRANSCRIPT:\n" + transcript)
if result.stop_reason == "interrupt":
    intr = result.interrupts[0]   # .id and .reason (the human-readable question)
    # ...send intr.reason to phone, wait for the reply, then:
    result = agent([{"interruptResponse": {"interruptId": intr.id, "response": answer}}])
```

`HumanInTheLoop(ask=my_callback)` is the lower-plumbing variant - your callback
sends the notification and returns the reply inline. `FileSessionManager` (already
in the installed package) keeps state alive between the ping and the reply. Docs:
https://strandsagents.com/docs/user-guide/concepts/agents/interventions/human-in-the-loop/

---

Verified tonight (2026-09-11) on strands-agents 1.55.1 / Python 3.10: install set,
GeminiModel constructor signature, and the full fused loop (model calls ask_human,
banner prints, run blocks on input, answer returns as the tool result, Pass 2
completes, str(result) yields the notes) using a scripted model through the real
SDK event loop. Not verified here: the live Gemini call itself (needs Jose's key,
runs on his machine) - that's what Step 5 checks.

