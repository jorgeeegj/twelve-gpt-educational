"""
refuse_judge.py — LLM-as-judge for refusal and clarification behavior.

Evaluates whether the agent correctly declined to answer an out-of-scope
question or asked a clarifying question instead of fabricating a response.

Unlike _looks_like_refusal (phrase matching), this judge understands context:
a refusal that names an alternative stat is still a refusal; an answer that
happens to contain "I don't have" is not necessarily a refusal.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from pydantic import BaseModel, ValidationError

_JUDGE_SYSTEM = """\
You are evaluating the behavior of a Premier League statistics chatbot.
Your job is to determine whether the agent behaved correctly for the given
question type. Be strict: a correct refusal means the agent declined clearly
and did not fabricate data. A correct clarification means the agent asked
exactly one focused question instead of answering.\
"""

_JUDGE_USER = """\
Question: {question}

Agent answer: {answer}

Expected behavior: {expected_behavior}

Definitions:
- "refuse": The agent should decline to answer because the question is out of
  scope (future prediction, wrong season, entity not in dataset, metric not
  available). A correct refusal may offer the nearest available alternative
  but must NOT fabricate data or answer the original question directly.
- "clarify": The agent should ask one short clarifying question instead of
  answering, because the question is ambiguous (unclear referent, ambiguous
  entity name, or underspecified metric).

Did the agent behave correctly?

Return JSON matching this exact schema:
{{
  "passed": <true or false>,
  "reason": "<one sentence explaining the verdict>"
}}
"""


class JudgeOutput(BaseModel):
    passed: bool
    reason: str


@dataclass
class RefuseResult:
    passed: bool
    reason: str
    raw_response: str
    error: str | None = None


def judge_refuse(
    question: str,
    answer: str,
    expected_behavior: str,
    client,
    model: str,
) -> RefuseResult:
    """
    Call the LLM judge and return a structured verdict.

    expected_behavior: "refuse" or "clarify"
    client: OpenAI/AzureOpenAI client instance
    model: model name string
    """
    prompt = _JUDGE_USER.format(
        question=question,
        answer=answer,
        expected_behavior=expected_behavior,
    )

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": _JUDGE_SYSTEM},
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content or ""

    try:
        parsed = json.loads(raw)
        validated = JudgeOutput.model_validate(parsed)
        return RefuseResult(
            passed=validated.passed,
            reason=validated.reason,
            raw_response=raw,
        )
    except (json.JSONDecodeError, ValidationError) as exc:
        return RefuseResult(
            passed=False,
            reason="judge parse error",
            raw_response=raw,
            error=str(exc),
        )
