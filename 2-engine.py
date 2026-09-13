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
