"""REUSABLE DECISION PATTERN: tool selection for a student opportunity assistant  (#tool-selection)

What it does
    Before the LLM handles a request, Strands Decider 2B classifies the user's intent and narrows
    the agent to only the relevant tool. Fewer tools in context means fewer wrong tool calls, lower
    token usage, and a faster, cheaper LLM turn.

    When the decider's confidence is below CONFIDENCE_THRESHOLD (default 0.60), all tools are kept
    and the LLM chooses — nothing is lost. If a question is flagged as ambiguous (AMBIGUITY_THRESHOLD
    default 0.45), the agent asks a clarifying question instead of guessing.

Typed questions and options
    `tool` (choice): one option per tool (description from the tool's own docstring) plus `none`.

    | Option                  | Handles                                              |
    |-------------------------|------------------------------------------------------|
    | search_opportunities    | internship / scholarship discovery                   |
    | find_learning_resources | courses, skills, free or paid learning material      |
    | build_career_plan       | placement roadmaps and weekly study schedules        |
    | compare_opportunities   | side-by-side comparison of two or more records       |
    | none                    | greetings, clarifications, unsupported requests      |

Wiring
    `OpportunityToolSelector` wraps a Strands `Agent`. In `agent.py`:

        selector = OpportunityToolSelector(decider)
        # Each chat turn:
        agent = selector.agent_for(user_message, model=agent_model(), system_prompt=SYSTEM_PROMPT)
        result = agent(user_message)

    `selector.log` accumulates one entry per turn for the decision panel in the demo UI.

How to reuse it
    Copy this file for any domain. Replace TOOL_DESCRIPTIONS with your own tool names and
    one-line descriptions. Adjust CONFIDENCE_THRESHOLD and AMBIGUITY_THRESHOLD to taste.
    The `QUESTIONS` dict is exactly what `./kit bench` and the test suite expect.
"""

from __future__ import annotations

from typing import Any

from decider_kit import Decider
from decider_kit.patterns.tool_selection import ToolSelector

PATTERN_TAG = "#tool-selection"

# Confidence below this → keep all tools (LLM chooses freely).
CONFIDENCE_THRESHOLD = 0.60

# Confidence below this → ask a clarifying question.
AMBIGUITY_THRESHOLD = 0.45

# Tool descriptions used both for the choice question and the fallback clarification message.
TOOL_DESCRIPTIONS: dict[str, str] = {
    "search_opportunities": (
        "Search internship and scholarship opportunities by domain, year of study, or skill keywords"
    ),
    "find_learning_resources": (
        "Find free and paid courses, tutorials, and skill-building resources by topic or technology"
    ),
    "build_career_plan": (
        "Build a structured weekly placement preparation plan or career roadmap based on a student's goal"
    ),
    "compare_opportunities": (
        "Compare two or more internships or scholarships side by side by eligibility, skills, duration, and value"
    ),
    "none": (
        "No tool is needed; the assistant can answer directly (greetings, clarifications, unsupported requests)"
    ),
}

# QUESTIONS is the single typed question asked per turn.
# The benchmark, tests, and eval cases all reference this dict.
QUESTIONS: dict[str, dict[str, Any]] = {
    "tool": Decider.choice(
        "Which tool should handle this student's request?",
        TOOL_DESCRIPTIONS,
    )
}

# Clarification responses when intent is genuinely ambiguous.
_CLARIFY_MESSAGES = {
    "search_opportunities": "Are you looking for internship listings, scholarship listings, or both?",
    "find_learning_resources": "Which technology or subject would you like resources for?",
    "build_career_plan": "What is your target — placement prep, a specific tech domain, or an internship?",
    "compare_opportunities": "Which opportunities would you like me to compare? Please share their IDs or names.",
    "none": (
        "I can help you find internships, scholarships, learning resources, or build a career plan. "
        "What would you like to do?"
    ),
}


class OpportunityToolSelector:
    """Wraps a `ToolSelector` with CampusPilot-specific thresholds and logging.

    Usage::

        selector = OpportunityToolSelector(Decider())
        # per turn:
        agent = selector.agent_for(
            request, model=agent_model(), system_prompt=SYSTEM_PROMPT,
            callback_handler=None
        )
        result = agent(request)
        # decision log for the UI:
        latest = selector.log[-1]
    """

    def __init__(self, decider: Decider, threshold: float = CONFIDENCE_THRESHOLD):
        from .tools import TOOLS

        self._inner = ToolSelector(decider, TOOLS, threshold=threshold, context="for a college student")
        self.log: list[dict[str, Any]] = []

    # ---- public ---------------------------------------------------------------

    def select(self, request: str, history: str = "") -> dict[str, Any]:
        """Run the decision; return a log entry with tool, confidence, narrowed flag, probabilities, and reason."""
        sel = self._inner.select(request, history)
        conf = round(sel.confidence, 3)

        # Build a short human-readable reason from the actual decider output.
        # This is derived from confidence thresholds and the chosen tool — never invented.
        if sel.confidence < AMBIGUITY_THRESHOLD:
            reason = (
                f"Confidence {conf:.0%} is below the ambiguity threshold ({AMBIGUITY_THRESHOLD:.0%}). "
                "Intent is unclear — asking for clarification."
            )
        elif not sel.narrowed:
            reason = (
                f"Confidence {conf:.0%} is below the routing threshold ({CONFIDENCE_THRESHOLD:.0%}). "
                "Keeping all tools; the LLM will choose."
            )
        else:
            desc = TOOL_DESCRIPTIONS.get(sel.tool, sel.tool)
            reason = (
                f"Confidence {conf:.0%} ≥ {CONFIDENCE_THRESHOLD:.0%}. "
                f"Routing to '{sel.tool}': {desc}."
            )

        entry: dict[str, Any] = {
            "pattern": PATTERN_TAG,
            "stage": "tool_selection",
            "tool": sel.tool,
            "confidence": conf,
            "narrowed": sel.narrowed,
            "probabilities": sel.decision.probabilities,
            "decider_ms": round(self._inner.decider.last_latency_ms or 0),
            "reason": reason,
        }
        if sel.confidence < AMBIGUITY_THRESHOLD:
            entry["verdict"] = "clarify"
            entry["clarify_message"] = _CLARIFY_MESSAGES.get(sel.tool, _CLARIFY_MESSAGES["none"])
        elif not sel.narrowed:
            entry["verdict"] = "keep_all"
        else:
            entry["verdict"] = "narrowed"
        self.log.append(entry)
        return entry

    def tools_for(self, request: str, history: str = "") -> list[Any]:
        """Return the narrowed tool list (or all tools if unsure)."""
        self.select(request, history)
        last = self.log[-1]
        if last["verdict"] == "clarify":
            return []  # signal to agent.py to return a clarifying message
        return self._inner.tools_for(request, history) if last["narrowed"] else list(self._inner.tools)

    def agent_for(self, request: str, *, model: Any, system_prompt: str = "",
                  history: str = "", **agent_kwargs: Any) -> Any:
        """Return a Strands Agent narrowed to the right tool for this request."""
        from strands import Agent

        entry = self.select(request, history)
        if entry["verdict"] == "clarify":
            return None  # agent.py handles this
        tools = self._inner.tools_for(request, history) if entry["narrowed"] else list(self._inner.tools)
        return Agent(model=model, system_prompt=system_prompt, tools=tools, **agent_kwargs)
