"""
Handwriting Agent — interprets and structures raw OCR output from
handwritten student work.

This agent does NOT use external tools; it relies purely on the LLM to
clean up noisy OCR text, identify mathematical equations vs prose, and
produce a well-structured representation.
"""

import logging
from typing import Any

from agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are a highly capable Vision-Language Model serving as an expert Teacher Assistant.
Your task is to look at the provided image (or document) containing a student's handwritten work, read it, and produce a clean, structured text representation.

RULES:
1. Carefully read all handwriting, mathematical equations, and text in the image.
2. Identify mathematical equations and format them clearly. Use standard notation: x^2 for exponents, sqrt() for roots, fractions as a/b.
3. Separate distinct problems/questions with clear numbering.
4. Identify text blocks (prose explanations) vs mathematical work.
5. Mark anything truly unreadable as [ILLEGIBLE].
6. Do NOT invent content — only transcribe and structure what is there.
7. Preserve the student's original logic and steps.

OUTPUT FORMAT:
Return the structured text with clear section headers like:
  ## Problem 1
  **Student's work:**
  <cleaned steps>

  ## Problem 2
  ...
"""


class HandwritingAgent:
    """Agent specialised in extracting and structuring text directly from images.

    This uses the multimodal capabilities of the VLM to bypass local OCR.
    """

    def __init__(self) -> None:
        self.agent = BaseAgent(
            system_prompt=_SYSTEM_PROMPT,
            tools=None,
            tool_registry=None,
        )

    async def process(self, multimodal_input: str | list[dict[str, Any]]) -> str:
        """Extract and structure text directly from the *multimodal_input*.

        Parameters
        ----------
        multimodal_input:
            The multimodal payload, e.g. base64 image dict.

        Returns
        -------
        str
            A cleaned, structured interpretation of the handwritten work.
        """
        logger.info("HandwritingAgent processing multimodal input.")
        return await self.agent.run(multimodal_input)

    def get_log(self) -> str:
        """Return the agent's log."""
        return self.agent.get_agent_log()
