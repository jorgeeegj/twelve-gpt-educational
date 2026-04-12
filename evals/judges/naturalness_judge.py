"""
naturalness_judge.py — LLM-as-judge for answer quality.

Evaluates two dimensions in a single LLM call to save cost:
  - Naturalness (1-5): does the answer sound like a human football analyst?
  - Completeness (yes/no): does the answer actually address the question?

Uses Pydantic for structured output validation — if the LLM returns a
malformed response, ValidationError is raised immediately rather than
silently producing bad scores. This is the "fail-fast" principle from
the course's structured outputs lesson.
"""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, Field, ValidationError

_JUDGE_SYSTEM = """\
You are evaluating the quality of answers from a Premier League statistics analyst chatbot.
Rate the answer on two dimensions and return a JSON object exactly matching the schema provided.
Be strict but fair — a good answer is fluent, uses natural football language, and directly
addresses the question with the correct context.\
"""

_JUDGE_USER = """\
Question: {question}

Answer: {answer}

Rate this answer on two dimensions:

1. NATURALNESS (integer 1-5):
   5 = Fluent analyst voice. Reads like a human football expert wrote it.
   4 = Clear and correct. Slightly dry but natural.
   3 = Correct information but robotic phrasing. Readable but awkward.
   2 = Barely natural. Sounds like machine output with some grammar.
   1 = Unreadable. JSON dumps, raw column names, broken sentences, or no answer at all.

2. COMPLETENESS (boolean):
   true  = The answer directly addresses what was asked.
   false = The answer dodges, is off-topic, or says it couldn't find data when
           the question should be answerable.

Return JSON matching this exact schema:
{{
  "naturalness_score": <integer 1-5>,
  "naturalness_rationale": "<one sentence explaining the score>",
  "is_complete": <true or false>,
  "completeness_rationale": "<one sentence explaining>"
}}\
"""


class JudgeOutput(BaseModel):
    naturalness_score: int = Field(ge=1, le=5)
    naturalness_rationale: str
    is_complete: bool
    completeness_rationale: str


@dataclass
class NaturalnessResult:
    naturalness_score: int
    naturalness_rationale: str
    is_complete: bool
    completeness_rationale: str
    raw_response: str
    error: str | None = None

    @property
    def passed_naturalness(self) -> bool:
        return self.naturalness_score >= 4

    @property
    def passed_completeness(self) -> bool:
        return self.is_complete


def judge_naturalness(
    question: str,
    answer: str,
    client,
    model: str,
) -> NaturalnessResult:
    """
    Call the LLM judge and return structured scores.

    client: OpenAI/AzureOpenAI client instance
    model: model name string
    """
    import json

    prompt = _JUDGE_USER.format(question=question, answer=answer)

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
        return NaturalnessResult(
            naturalness_score=validated.naturalness_score,
            naturalness_rationale=validated.naturalness_rationale,
            is_complete=validated.is_complete,
            completeness_rationale=validated.completeness_rationale,
            raw_response=raw,
        )
    except (json.JSONDecodeError, ValidationError) as exc:
        # Return a failed result rather than crashing the benchmark run
        return NaturalnessResult(
            naturalness_score=1,
            naturalness_rationale="judge parse error",
            is_complete=False,
            completeness_rationale="judge parse error",
            raw_response=raw,
            error=str(exc),
        )
