"""CampusPilot AI — intelligent student opportunity assistant.

Strands Decider 2B classifies the user's intent (tool-selection pattern) before every turn.
Amazon Bedrock (Amazon Nova Pro by default) powers the generative conversation.

    from agent.agent import HackathonAgent
    out = HackathonAgent().chat("Find internships for a 2nd-year CSE student.")
    out["reply"], out["decisions"]
"""

from __future__ import annotations

import time
from typing import Any

from strands import Agent
from strands.event_loop._retry import ModelRetryStrategy
from strands.types.exceptions import ModelThrottledException

from decider_kit import Decider
from decider_kit.llm import agent_model, default_model_id, strip_thinking

from .decision import AMBIGUITY_THRESHOLD, OpportunityToolSelector, _CLARIFY_MESSAGES
from .tools import TOOLS

NAME = "CampusPilot AI — Student Opportunity Assistant"

SYSTEM_PROMPT = """You are CampusPilot AI, a helpful assistant for college students in India.

You help students discover internships, scholarships, free learning resources, and build personalised
career plans. You have access to four tools:
- search_opportunities: find internships and scholarships
- find_learning_resources: find courses and tutorials
- build_career_plan: generate a weekly study/career roadmap
- compare_opportunities: compare two or more opportunity records side by side

IMPORTANT RULES:
1. Always use a tool when one is relevant — do not invent data.
2. Every tool response includes a data_source field. Remind the user that all results are
   sample data and must be verified directly with the organisation.
3. When you receive tool results, present them clearly: list each opportunity with its title,
   organisation, key requirements, and deadline. For learning resources, mention whether they
   are free.
4. Never fabricate internship companies, scholarship eligibility, application links, or deadlines.
5. Be concise and student-friendly. If the user's request is ambiguous, ask one focused
   clarifying question.
6. When building a career plan, tailor it to any year-of-study or timeline the student mentions.
"""


class HackathonAgent:
    """One Strands agent session with the tool-selection decision pattern wired in."""

    def __init__(
        self,
        decider: Decider | None = None,
        model_id: str | None = None,
    ) -> None:
        self.decider = decider or Decider()
        self.model_id = model_id or default_model_id()
        # One selector per agent instance; its log accumulates across turns.
        self.selector = OpportunityToolSelector(self.decider)
        # Per-session Agent instances (Strands Agent keeps message history internally).
        self._agents: dict[str, Agent] = {}

    # ---- public interface expected by the kit --------------------------------

    def chat(
        self,
        message: str,
        session_id: str = "default",
        images: list[Any] | None = None,
    ) -> dict[str, Any]:
        """Handle one user turn. Returns reply, decisions list, latency, and model info."""
        before = len(self.selector.log)
        t0 = time.perf_counter()

        # 1. Run the decision BEFORE the LLM turn.
        history = self._history_text(session_id)
        decision_entry = self.selector.select(message, history)

        # 2. If the decider is very uncertain, ask for clarification instead of guessing.
        if decision_entry["verdict"] == "clarify":
            reply = decision_entry.get("clarify_message", _CLARIFY_MESSAGES["none"])
            return {
                "reply": reply,
                "decisions": self.selector.log[before:],
                "model_id": self.model_id,
                "latency_ms": round((time.perf_counter() - t0) * 1000),
                "agent": NAME,
            }

        # 3. Narrow tools based on the decision.
        if decision_entry["narrowed"]:
            from .tools import (compare_opportunities, build_career_plan,
                                find_learning_resources, search_opportunities)
            _name_map = {
                "search_opportunities": search_opportunities,
                "find_learning_resources": find_learning_resources,
                "build_career_plan": build_career_plan,
                "compare_opportunities": compare_opportunities,
            }
            chosen = decision_entry["tool"]
            tools_to_use = [_name_map[chosen]] if chosen in _name_map else TOOLS
        else:
            tools_to_use = TOOLS

        # 4. Get or create a Strands Agent for this session with the right tools.
        agent = self._get_or_create_agent(session_id, tools_to_use)

        # 5. Run the LLM turn (ModelRetryStrategy handles transient rate-limit retries
        #    automatically; we catch here only if all retries are exhausted).
        try:
            result = agent(message)
            reply = strip_thinking(str(result))
        except ModelThrottledException:
            reply = (
                "⚠️ The language model is temporarily busy (rate limit). "
                "Please wait 30 seconds and try again. "
                "The UGMDU free tier has per-minute limits during the hackathon."
            )

        return {
            "reply": reply,
            "decisions": self.selector.log[before:],
            "model_id": self.model_id,
            "latency_ms": round((time.perf_counter() - t0) * 1000),
            "agent": NAME,
        }

    # ---- helpers -------------------------------------------------------------

    def _get_or_create_agent(self, session_id: str, tools: list[Any]) -> Agent:
        """Return the cached agent for this session, or create a new one.

        When tools change (because the selection differs turn-to-turn) we create a fresh
        Agent for this turn but reuse the existing one's message history so context is
        preserved. Strands Agents store history internally; we read it back via .messages.
        """
        existing = self._agents.get(session_id)
        if existing is not None:
            # strands-agents 1.61+ stores tools in agent.tool_registry.registry (dict keyed by
            # tool name). There is no .tools attribute.
            try:
                existing_names = set(existing.tool_registry.registry.keys())
            except AttributeError:
                existing_names = set(existing.tool_names) if hasattr(existing, "tool_names") else set()
            new_names = {getattr(t, "tool_name", getattr(t, "__name__", str(t))) for t in tools}
            if existing_names == new_names:
                return existing

        # Create a new agent; inherit history from the previous one if it exists.
        # ModelRetryStrategy: retries on rate-limit (4s→8s→16s→32s→64s, max 6 attempts).
        agent = Agent(
            model=agent_model(self.model_id),
            system_prompt=SYSTEM_PROMPT,
            tools=tools,
            callback_handler=None,
            retry_strategy=ModelRetryStrategy(
                initial_delay=4,   # wait 4 s before first retry
                max_delay=60,      # cap at 60 s (UGMDU limits reset within a minute)
                max_attempts=4,    # 3 retries — keeps total wait under 30 s
            ),
        )
        if existing is not None and hasattr(existing, "messages") and existing.messages:
            # Copy conversation history so the LLM has context from previous turns.
            try:
                agent.messages = list(existing.messages)
            except Exception:  # noqa: BLE001 — history copy is best-effort
                pass

        self._agents[session_id] = agent
        return agent

    def _history_text(self, session_id: str) -> str:
        """Last few turns as plain text, for the decider's state input."""
        agent = self._agents.get(session_id)
        if agent is None or not hasattr(agent, "messages"):
            return ""
        lines = []
        for msg in (agent.messages or [])[-6:]:  # last 3 turns (user + assistant each)
            role = msg.get("role", "")
            content = msg.get("content", "")
            if isinstance(content, list):
                text = " ".join(
                    c.get("text", "") for c in content if isinstance(c, dict) and "text" in c
                )
            else:
                text = str(content)
            if text.strip():
                lines.append(f"{role}: {text[:300]}")
        return "\n".join(lines)


if __name__ == "__main__":
    import json
    import sys

    a = HackathonAgent()
    prompts = sys.argv[1:] or [
        "Find internships for a 2nd-year CSE student.",
        "Recommend free Java and DSA learning resources.",
        "Create a 12-week placement preparation plan.",
        "Compare INT001 and INT002.",
    ]
    for msg in prompts:
        print(f"\n>>> {msg}")
        out = a.chat(msg)
        print(json.dumps({"reply": out["reply"][:300], "decisions": out["decisions"]}, indent=2))
