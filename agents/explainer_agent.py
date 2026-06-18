"""
Explainer Agent — generates clear, teacher-quality explanations for mistakes.

Given a list of mistakes and the original student work, this agent produces
detailed concept explanations, worked examples, and learning tips.
"""

import logging
from typing import Any

from agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are an expert, patient, and encouraging maths teacher.  Your goal is
to help students understand their mistakes and learn the underlying
concepts.

RULES:
1. For each mistake, explain:
   a. WHAT went wrong — describe the error in simple language.
   b. WHY it's wrong — explain the mathematical rule or concept violated.
   c. HOW to fix it — show the correct approach step by step.
   d. A SIMILAR example — provide a new, similar problem with solution
      so the student can practise.
2. Use simple, clear language appropriate for a student.
3. Be encouraging — acknowledge what the student did well.
4. Organise your explanation with clear headings.
5. If there are no mistakes, congratulate the student and suggest
   extension problems to deepen understanding.
"""


class ExplainerAgent:
    """Agent that generates pedagogical explanations for student mistakes.

    This is a no-tools agent — relies on the LLM's teaching ability.
    """

    def __init__(self) -> None:
        self.agent = BaseAgent(
            system_prompt=_SYSTEM_PROMPT,
            tools=None,
            tool_registry=None,
        )

    async def process(
        self, mistakes: list[dict[str, Any]], original_work: str
    ) -> str:
        """Generate explanations for each mistake.

        Parameters
        ----------
        mistakes:
            List of mistake dicts (from :class:`CorrectnessAgent`).
        original_work:
            The student's cleaned work text for reference.

        Returns
        -------
        str
            Detailed, teacher-quality explanations.
        """
        if not mistakes:
            prompt = (
                "The student's work is fully correct.  Here is their work:\n\n"
                f"{original_work}\n\n"
                "Please congratulate them and suggest extension problems or "
                "deeper concepts they could explore next."
            )
        else:
            mistakes_text = "\n".join(
                f"  {i+1}. Problem '{m.get('problem', '?')}': "
                f"Student wrote '{m.get('student_answer', '?')}' but correct is "
                f"'{m.get('correct_answer', '?')}'. "
                f"Error type: {m.get('error_type', 'unknown')}. "
                f"Description: {m.get('description', '')}"
                for i, m in enumerate(mistakes)
            )
            prompt = (
                "A student submitted the following work:\n\n"
                f"{original_work}\n\n"
                "The following mistakes were identified:\n"
                f"{mistakes_text}\n\n"
                "Please provide detailed, encouraging explanations for each "
                "mistake, following your teaching guidelines."
            )

        logger.info(
            "ExplainerAgent processing %d mistake(s)", len(mistakes)
        )
        return await self.agent.run(prompt)

    def get_log(self) -> str:
        """Return the agent's log."""
        return self.agent.get_agent_log()
