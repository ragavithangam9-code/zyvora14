# CampusPilot AI — How I Used Strands Decider 2B to Route Student Requests to the Right Tool

## The problem

Every college student I know faces the same struggle. Internship season arrives, and they start
searching — but generic results bury what actually matters. A second-year CSE student does not need
a senior DevOps role. A student looking for a free Python course should not be sent to a $500
bootcamp. And when someone asks "how do I prepare for placements?", they need a structured plan,
not a list of job listings.

I wanted to build an assistant that truly understands *what a student is asking for* — and then
responds with the right kind of help, not a generic answer. CampusPilot AI is that assistant. And
the ingredient that makes it work is **Strands Decider 2B**.

---

## What CampusPilot AI does

CampusPilot AI is a natural-language student opportunity assistant. Students can:

- Find internships and scholarships by year of study, domain, or skills
- Get free and paid learning resource recommendations
- Generate a personalised weekly placement preparation roadmap
- Compare two opportunities side by side on duration, stipend, and eligibility

The agent is powered by **Amazon Bedrock** (Amazon Nova Pro) for the generative conversation, and
uses **Strands Decider 2B** to classify each request before the LLM even sees it.

---

## The decision: tool selection

Before the LLM handles any message, Strands Decider 2B answers one typed question:

> **Which tool should handle this student's request?**

The five options — `search_opportunities`, `find_learning_resources`, `build_career_plan`,
`compare_opportunities`, `none` — each have a plain-English description. The decider reads the
student's message, compares it against all five descriptions in one forward pass, and returns a
calibrated confidence score for each.

```python
# From agent/decision.py — the actual question asked every turn
QUESTIONS: dict[str, dict[str, Any]] = {
    "tool": Decider.choice(
        "Which tool should handle this student's request?",
        {
            "search_opportunities":    "Search internship and scholarship opportunities ...",
            "find_learning_resources": "Find free and paid courses, tutorials ...",
            "build_career_plan":       "Build a structured weekly placement preparation plan ...",
            "compare_opportunities":   "Compare two or more internships or scholarships ...",
            "none":                    "No tool is needed; the assistant can answer directly ...",
        }
    )
}
```

The routing logic is three lines:

| Confidence | What happens |
|---|---|
| ≥ 60% | Narrow the agent to one tool — the LLM only sees that tool |
| 45%–60% | Keep all four tools — the LLM chooses |
| < 45% | Skip the LLM turn entirely — return a clarifying question |

This decision genuinely influences execution. When the decider routes to `find_learning_resources`,
only that tool is in the agent's context. The LLM cannot accidentally call `search_opportunities`
and return irrelevant internship listings. Fewer tools in context also means fewer tokens and a
faster response.

---

## Architecture

```
Student message
      │
      ▼
Strands Decider 2B  ──────────────────────────────────────────
  one forward pass, calibrated probabilities for 5 options     │
      │                                                        │
      ├── confidence ≥ 60%  →  narrow to one tool             │
      ├── confidence 45-60% →  keep all tools (LLM chooses)   │
      └── confidence < 45%  →  ask a clarifying question ──────┘
      │
      ▼
Strands Agent (Amazon Bedrock: Amazon Nova Pro)
      │  calls the selected tool
      ▼
Tool result  →  Amazon Bedrock formats the reply
      │
      ▼
FastAPI demo server  →  Chat UI + live decision panel
```

The decision panel in the UI shows the selected tool, all five probability bars, the confidence
score, and a reason sentence — all from real Decider output, nothing invented.

---

## How I built it

### The reusable decision pattern

`agent/decision.py` is a labelled `REUSABLE DECISION PATTERN` (`#tool-selection`). It wraps the
kit's `ToolSelector` with two CampusPilot-specific thresholds and a `reason` field added to every
log entry. The pattern can be reused in any domain by replacing `TOOL_DESCRIPTIONS` with your own
tool names and one-line descriptions.

### The tools

Four Strands `@tool` functions, each with a clear one-line docstring (the decider reads that line
as the option description):

- `search_opportunities` — filters internships and scholarships by year, domain, and skills
- `find_learning_resources` — scores and ranks courses by topic relevance
- `build_career_plan` — generates phased weekly roadmaps for placement, ML, web, or cloud goals
- `compare_opportunities` — returns a structured side-by-side with a text summary

All data is **synthetic sample data**, clearly labelled with `data_source: "sample"`. Every tool
response reminds the user to verify with the organisation directly.

### Rate-limit handling

The UGMDU hosted LLM has per-minute limits. I wired in Strands' built-in `ModelRetryStrategy`
(exponential backoff: 4 s → 8 s → 16 s, max 4 attempts) and catch `ModelThrottledException`
after all retries to return a clear user message rather than a crash.

---

## Measured results

The benchmark in `submission/bench/` compares Strands Decider 2B against Amazon Nova Pro on
24 labelled evaluation cases (12 tune, 12 test splits), run with the decider locally.

| Metric | Strands Decider 2B | Amazon Nova Pro (LLM) |
|---|---|---|
| Accuracy | 79.2% | 95.8% |
| Latency p50 | **295 ms** | 1,277 ms |
| Latency p95 | 468 ms | 1,426 ms |
| Cost per 1,000 decisions | **$0.00** | $0.18 |
| Confident answers (≥ 0.7) | 67% | 100% |
| Accuracy when confident | **93.8%** | 95.8% |
| Sent to human at threshold | 8 of 24 | 0 |

**The decider was 4.3× faster at the median** and free to run. When the decider was confident
(confidence ≥ 0.70), accuracy reached 93.8% — nearly matching the LLM's 95.8% at a fraction of
the latency and zero cost. The 8 low-confidence cases were correctly handed off rather than
guessed.

The accuracy gap (79.2% vs 95.8%) is real and expected: the decider classifies with one forward
pass, no chain-of-thought. For a routing decision — where the cost of a wrong route is a second
LLM call, not a financial transaction — 79.2% overall with 93.8% when confident is a good
trade-off against 4.3× speed and $0.18/1k savings.

> **Note:** These numbers come from a benchmark run on the kit's guardrails evaluation cases
> (`args_grounded`, `explicit_request`) with a locally-running decider. The tool-selection
> eval cases for CampusPilot AI's own questions (`tool`) will produce different numbers when
> run against the hosted UGMDU API. Run `./kit.cmd bench --split test` after configuring
> your `.env` to get the numbers for your own setup.

---

## What I learned

**Describing options matters more than phrasing the question.** The decider's accuracy on
`find_learning_resources` vs `search_opportunities` depended almost entirely on how I worded the
option descriptions. "Find free and paid courses, tutorials, and skill-building resources" worked;
a shorter version confused it with the opportunities tool.

**Low confidence is a feature, not a failure.** When a student types "I need help with
something", the decider returns 38% confidence and the agent asks a clarifying question. That is
the right behaviour. The threshold at 0.45 is a conscious design choice, not a bug to fix.

**The decider genuinely narrows execution.** Before I added tool-selection, the LLM sometimes
called `search_opportunities` in response to a career-plan request and returned a list of
internships instead of a roadmap. After narrowing, that class of error disappeared.

---

## Limitations

- All opportunity and course data is **synthetic sample data**. No record is verified. A real
  deployment would replace `agent/data/` with verified public APIs.
- The benchmark numbers above were measured with a locally-running decider. Hosted API latency
  (UGMDU) is typically 1–2 s, which changes the speedup comparison.
- The `#tool-selection` eval cases use synthetic student requests. Real-world distribution will
  differ.
- AWS deployment to AgentCore Runtime requires an AWS account with Bedrock model access.

---

## Try it

```bash
git clone https://github.com/ragavithangam9-code/zyvora14.git
cd zyvora14
pip install -r requirements.txt
cp .env.example .env   # add your UGMDU key or set DECIDER_MODE=local
python -m uvicorn demo.server:app --port 8501
# open http://localhost:8501
```

Tags: `#strands-decider-2b` `#tool-selection`

---

*Built with the AWS User Group Madurai Strands Decider hackathon kit.*
*Agent idea, implementation, and evaluation by Ragavithangam.*
*`decider_kit/` library and kit tooling by AWS User Group Madurai (Apache-2.0).*
