# CampusPilot AI — Student Opportunity Assistant

## Use case

College students struggle to find relevant internships, scholarships, skill-building resources,
and placement preparation guidance. Generic search engines surface irrelevant or unverified
results. CampusPilot AI understands natural-language requests, routes each request to the right
tool using **Strands Decider 2B**, and returns useful recommendations backed by clearly labelled
sample data.

## Decision pattern

**#tool-selection** — before the LLM handles a request, Strands Decider 2B classifies the user's
intent and narrows the agent to only the relevant tool. This reduces incorrect tool calls, lowers
token usage, and surfaces the decision transparently in the UI.

Five tools, one choice question:

| Tool option | What it handles |
|---|---|
| `search_opportunities` | Internship and scholarship discovery |
| `find_learning_resources` | Courses, skills, and free/paid learning material |
| `build_career_plan` | Placement roadmaps and weekly study schedules |
| `compare_opportunities` | Side-by-side comparison of two or more records |
| `none` | Direct conversational reply (greetings, clarifications, unsupported requests) |

When confidence is below 0.60, all tools are kept and the LLM decides — nothing is lost.

## Data

`agent/data/opportunities.json` and `agent/data/resources.json` are clearly labelled synthetic
datasets. Every record includes a `data_source: "sample"` field. The agent always reminds users
to verify opportunities directly.

## Deployment

Amazon Bedrock AgentCore Runtime (see `deploy/` and `agent/features.yaml`).
LLM: Amazon Bedrock (Amazon Nova Pro by default; `BEDROCK_MODEL_ID` in `.env`).
Decider: AWS User Group Madurai hosted API, or local (`DECIDER_MODE` in `.env`).
