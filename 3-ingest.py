#!/usr/bin/env python3
"""Lecture Synthesis Engine — ingestion script (DRAFT).

Friday objective: feed a raw Plaud transcript .txt file into the Gemini API using the
adversarial auditor system prompt, and write the Markmap .md file out.

Usage:
    python ingest.py lecture-03.txt
    python ingest.py lecture-03.txt --prompt adversarial-auditor-prompt-v1.1.md --out output/

Setup:
    pip install google-generativeai
    export GEMINI_API_KEY=...        # your existing key; never hardcode it
    export GEMINI_MODEL=...          # optional; defaults below

Pipeline: transcript .txt -> Gemini (v1.1 auditor prompt) -> Markmap .md
"""

import argparse
import os
import re
import sys

try:
    import google.generativeai as genai
except ImportError:
    sys.exit("Missing dependency: run `pip install google-generativeai` first.")

MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")  # draft default; change as needed
PROMPT_FILE_DEFAULT = "adversarial-auditor-prompt-v1.1.md"

# Run-mode adapter: this script has no SDK tools yet (Strands integration comes later).
# When the prompt says to invoke the halt tool, the model instead emits the question in
# <HALT> tags and stops. The Strands agent will later convert these into real tool calls.
RUN_MODE_ADAPTER = (
    "RUN MODE: no function-calling tools are available in this run. Wherever the system "
    "prompt instructs you to invoke [STRANDS_SDK_TOOL_NAME], instead output the halt "
    "question inside <HALT>...</HALT> tags and end your response immediately."
)


def load_system_prompt(path: str) -> str:
    """Load the auditor prompt, using only the content after the '---' separator
    (the header above it is documentation about the prompt, not for the model)."""
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    if "\n---\n" in text:
        text = text.split("\n---\n", 1)[1]
    return text.strip()


def strip_scratchpad(text: str) -> str:
    """Defense in depth: remove any <audit_scratchpad> content that leaks through."""
    cleaned = re.sub(r"<audit_scratchpad>.*?</audit_scratchpad>", "", text, flags=re.DOTALL)
    return re.sub(r"\n{3,}", "\n\n", cleaned).strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="Plaud transcript -> Markmap study notes")
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
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        sys.exit("Set GEMINI_API_KEY in your environment first.")

    with open(args.transcript, "r", encoding="utf-8") as f:
        transcript = f.read().strip()
    if not transcript:
        sys.exit("Transcript is empty; nothing to synthesize.")

    system_prompt = load_system_prompt(args.prompt)
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name=MODEL, system_instruction=system_prompt)

    print(f"Synthesizing {args.transcript} with {MODEL} ...", flush=True)
    response = model.generate_content(
        RUN_MODE_ADAPTER + "\n\nTRANSCRIPT:\n" + transcript
    )
    output = strip_scratchpad(response.text or "")
    if not output:
        sys.exit("Model returned empty output; nothing written.")

    os.makedirs(args.out, exist_ok=True)
    stem = os.path.splitext(os.path.basename(args.transcript))[0]
    out_path = os.path.join(args.out, stem + ".md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(output + "\n")

    halt_match = re.search(r"<HALT>(.*?)</HALT>", output, flags=re.DOTALL)
    if halt_match:
        print("\n" + "=" * 60)
        print("INTERCEPT FIRED — the auditor halted on a critical conflict:")
        print("=" * 60)
        print(halt_match.group(1).strip())
        print("=" * 60)
        print("Answer the question, fix the transcript if needed, and re-run.")
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()

