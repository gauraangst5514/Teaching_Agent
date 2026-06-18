"""
Correctness Agent — checks mathematical / logical correctness of student work.

Uses both the LLM reasoning and SymPy math tools to verify equations,
solve problems independently, and compare against the student's answers.
Returns a structured JSON assessment.
"""

import json
import logging
from typing import Any

from agents.base_agent import BaseAgent
from tools.math_tools import get_math_tools, MATH_TOOLS

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are an expert mathematics and logic teacher.  Your job is to check the
correctness of a student's work.

WORKFLOW:
1. Read through the student's work carefully.
2. For each equation or step, use the available math tools to verify
   correctness (verify_equation), solve independently (solve_equation),
   or simplify (simplify_expression).
3. Compare the student's answers with the correct answers.
4. Identify ALL mistakes — even small sign errors or algebraic slips.
5. For each mistake, note:
   - which step/problem it occurs in,
   - what the student wrote,
   - what the correct result should be,
   - the type of error (arithmetic, algebraic, conceptual, etc.).

After your analysis, provide your assessment as a JSON object with this
exact structure (and nothing else):

{
  "correct": <true if all work is correct, false otherwise>,
  "score": <integer 0-100>,
  "mistakes": [
    {
      "problem": "<problem number or identifier>",
      "student_answer": "<what the student wrote>",
      "correct_answer": "<the correct answer>",
      "error_type": "<arithmetic|algebraic|conceptual|sign|other>",
      "description": "<brief description of the mistake>"
    }
  ],
  "steps_analysis": [
    {
      "step": "<step identifier>",
      "is_correct": <true|false>,
      "note": "<brief note>"
    }
  ]
}
"""

_RESULT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "correct": {"type": "boolean"},
        "score": {"type": "integer", "minimum": 0, "maximum": 100},
        "mistakes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "problem": {"type": "string"},
                    "student_answer": {"type": "string"},
                    "correct_answer": {"type": "string"},
                    "error_type": {"type": "string"},
                    "description": {"type": "string"},
                },
            },
        },
        "steps_analysis": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "step": {"type": "string"},
                    "is_correct": {"type": "boolean"},
                    "note": {"type": "string"},
                },
            },
        },
    },
    "required": ["correct", "score", "mistakes", "steps_analysis"],
}


class CorrectnessAgent:
    """Agent that checks mathematical/logical correctness using math tools.

    Attributes
    ----------
    agent : BaseAgent
        The underlying LLM agent wired with math tools.
    """

    def __init__(self) -> None:
        self.agent = BaseAgent(
            system_prompt=_SYSTEM_PROMPT,
            tools=get_math_tools(),
            tool_registry=MATH_TOOLS,
        )

    async def process(
        self, student_work: str, question_context: str = ""
    ) -> dict[str, Any]:
        """Analyse *student_work* for correctness.

        Parameters
        ----------
        student_work:
            The cleaned, structured text of the student's submission.
        question_context:
            Optional original question/problem statement for reference.

        Returns
        -------
        dict
            Structured assessment with keys ``correct``, ``score``,
            ``mistakes``, ``steps_analysis``.
        """
        context_block = ""
        if question_context:
            context_block = (
                "\n--- ORIGINAL QUESTION / CONTEXT ---\n"
                f"{question_context}\n"
                "--- END CONTEXT ---\n"
            )

        prompt = (
            "Please check the following student work for correctness.  "
            "Use the math tools to verify equations and solve problems independently.\n"
            f"{context_block}"
            "\n--- STUDENT WORK ---\n"
            f"{student_work}\n"
            "--- END STUDENT WORK ---\n\n"
            "After your analysis, provide the final assessment as JSON."
        )

        logger.info("CorrectnessAgent processing %d chars of student work", len(student_work))
        raw_response = await self.agent.run(prompt)

        # Attempt to parse the JSON from the response
        parsed = BaseAgent._parse_json(raw_response)
        if "error" in parsed:
            # Fallback: ask again for structured output
            logger.warning("First correctness parse failed, retrying structured.")
            parsed = await self.agent.get_structured_response(
                f"Based on this analysis:\n{raw_response}\n\nProvide the assessment JSON.",
                _RESULT_SCHEMA,
            )

        # Ensure required keys exist with defaults
        if parsed.get("correct") is None:
            # If missing 'correct' but no mistakes are reported, assume correct
            parsed["correct"] = len(parsed.get("mistakes") or []) == 0
            
        if parsed.get("score") is None:
            parsed["score"] = 100 if parsed["correct"] else 0
            
        # If score is literally 0 but it's marked correct with no mistakes, fix it to 100
        if parsed["score"] == 0 and parsed["correct"] and len(parsed.get("mistakes") or []) == 0:
            parsed["score"] = 100
            
        if parsed.get("mistakes") is None:
            parsed["mistakes"] = []
        if parsed.get("steps_analysis") is None:
            parsed["steps_analysis"] = []
            
        return parsed

    def get_log(self) -> str:
        """Return the agent's tool-call log."""
        return self.agent.get_agent_log()
