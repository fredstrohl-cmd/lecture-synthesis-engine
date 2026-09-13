# Architecture - Lecture Synthesis Engine (DRAFT)

Mermaid source below. Render with mermaid.live, the GitHub markdown preview, or the
Mermaid CLI for the repo's PNG/SVG asset.

```mermaid
flowchart LR
    subgraph Input
        A[Plaud voice recorder<br/>lecture audio] -->|export| B[transcript .txt]
    end

    subgraph Agent["Lecture Synthesis Engine (Strands Agents SDK)"]
        B --> C[ingest.py<br/>CLI entry]
        C --> D[Strands agent<br/>adversarial auditor system prompt]
        D --> E{Pass 1: AUDIT<br/>inside audit_scratchpad tags}
        E -->|no critical conflict| G[Pass 2: FORMAT<br/>Markmap markdown]
        E -->|critical conflict| H[ask_human tool<br/>halt and wait]
        H -->|conflict + verbatim excerpts + A/B options| I((Student))
        I -->|resolution| J[apply + record inline<br/>Resolved per student: ...]
        J --> G
    end

    subgraph Output
        G --> K[study notes .md<br/>hierarchical nodes + verify-later section]
        K --> L[Markmap renderer<br/>interactive mind map]
    end
```

## Deployment notes

- **Model:** development runs use the Gemini API (`GEMINI_API_KEY` from the
  environment, never hardcoded). Through Strands the model is interchangeable; the
  deployment target is Claude on Amazon Bedrock.
- **Human-in-the-loop:** the halt is a real SDK tool call (`ask_human`). In the CLI
  build it blocks on stdin; the same tool boundary maps to a notification + reply
  loop if deployed (Bedrock AgentCore + an email/SMS surface is the stretch goal).
- **Scheduling:** today it runs on demand per transcript. A watcher (cron locally,
  or EventBridge on AWS) that ingests each new Plaud export as it lands is the
  background-cadence version.
- **Scratchpad quarantine:** audit reasoning lives in `<audit_scratchpad>` tags and
  is stripped from output both by prompt rule and by a regex pass in code (defense
  in depth).

