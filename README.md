# CampusPilot AI — Student Opportunity Assistant

An intelligent agent that helps college students discover internships, scholarships, learning
resources, and build personalised placement preparation plans — using **Strands Decider 2B** for
tool routing and **Amazon Bedrock** for the conversation.

> Built with the AWS User Group Madurai Strands Decider hackathon kit

---

## What it does

| Student request | What happens |
|---|---|
| "Find internships for a 2nd-year CSE student" | Strands Decider routes to `search_opportunities` |
| "Free Java and DSA courses" | Routed to `find_learning_resources` |
| "Build me a 12-week placement plan" | Routed to `build_career_plan` |
| "Compare INT001 and INT002" | Routed to `compare_opportunities` |
| "What can you help me with?" (ambiguous) | Decider returns low confidence → agent asks a clarifying question |

---

## Architecture

```
User message
      │
      ▼
 Strands Decider 2B          ← one forward pass, calibrated confidence
 (tool-selection pattern)
      │  confidence >= 0.60  →  narrow to one tool
      │  confidence  < 0.60  →  keep all four tools (LLM chooses)
      │  confidence  < 0.45  →  return clarifying question (no LLM turn wasted)
      ▼
 Strands Agent (Amazon Bedrock: Amazon Nova Pro)
      │  calls the selected tool
      ▼
 Tool result  →  Amazon Bedrock formats the final reply
      │
      ▼
 FastAPI demo server  →  Chat UI + decision panel
```

**Decision pattern:** `#tool-selection` (see `agent/decision.py` — labelled
`REUSABLE DECISION PATTERN`).

---

## Quick start (local)

### 1. Prerequisites

```
Python 3.11+
pip install -r requirements.txt
```

### 2. Configure `.env`

```bash
cp .env.example .env
```

Edit `.env` and set at minimum:

```
# Where Strands Decider 2B runs:
DECIDER_MODE=ugmdu                            # or: local
DECIDER_API_KEY=<your-ugmdu-key>              # from https://www.awsugmdu.in
DECIDER_URL=https://da25tnxy06gjk.cloudfront.net

# Where the LLM runs:
LLM_PROVIDER=bedrock                          # or: local, ugmdu
AWS_REGION=us-east-1
BEDROCK_MODEL_ID=us.amazon.nova-pro-v1:0
```

For a **completely local run** (no AWS cost, no cloud keys):

```
DECIDER_MODE=local
LLM_PROVIDER=local
LLM_MODEL_ID=qwen3.5:4b
```

Then start Ollama and the decider server first:
```bash
ollama pull qwen3.5:4b
./kit serve           # starts Strands Decider 2B locally
```

### 3. Start the demo

```bash
./kit demo            # Windows: .\kit.cmd demo
# Opens http://localhost:8501
```

### 4. Run the agent in the terminal

```bash
python -m agent.agent "Find internships for a 2nd-year CSE student."
```

---

## Run tests

```bash
./kit test            # Windows: .\kit.cmd test
# or directly:
pytest tests/ -v
```

---

## Benchmark (decider vs Bedrock LLM)

Tune on one split, report on the held-out test split:

```bash
./kit bench --split tune   # tune thresholds
./kit bench --split test   # numbers you report
```

Results are written to `submission/bench/results.md` and `results.json`.

---

## Deploy to AWS

```bash
./kit deploy          # packages the agent and deploys to AgentCore Runtime
./kit invoke "Find internships for a 2nd-year CSE student."
```

Requires an AWS account with Bedrock model access enabled.

---

## Project structure

```
agent/
  agent.py          HackathonAgent — Strands Agent + tool-selection wiring
  decision.py       REUSABLE DECISION PATTERN: #tool-selection
  tools.py          search_opportunities, find_learning_resources,
                    build_career_plan, compare_opportunities
  data/
    opportunities.json   internship + scholarship sample records
    resources.json       course + tutorial sample records
  eval_cases.jsonl  24 labelled evaluation cases (tune + test splits)
  features.yaml     AgentCore Memory / Gateway config (disabled for now)
  demo_script.yaml  demo video script

demo/
  server.py         FastAPI server (unchanged from kit)
  static/index.html polished student dashboard UI

decider_kit/        AWS UG Madurai kit library — not modified
tests/              kit test suite (agent_contract, patterns, tools, …)
```

---

## Data disclaimer

All records in `agent/data/` are **synthetic sample data** created for demonstration only.
Every record carries `"data_source": "sample"`. No record represents a verified live opportunity,
real company, or actual scholarship. Users must verify details directly with organisations.

---

## Submission tags

`#strands-decider-2b` `#tool-selection`

---

## Licence

Apache-2.0 — see `LICENSE`.

Attribution: **Built with the AWS User Group Madurai Strands Decider hackathon kit**.
Kit and `decider_kit/` library by AWS User Group Madurai. Not an official AWS project.
