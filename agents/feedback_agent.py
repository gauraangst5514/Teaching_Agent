"""
Feedback Agent — the **orchestrator** that chains all specialised agents
to produce comprehensive feedback on student submissions.

Pipeline:
    File submission:  OCR → Handwriting → Correctness → Explainer → Feedback
    Text submission:           (skip OCR) → Correctness → Explainer → Feedback
    Question:                  Direct LLM answer
"""

import json
import logging
import os
import base64
import mimetypes
import os
from typing import Any, Optional

from agents.base_agent import BaseAgent
from agents.handwriting_agent import HandwritingAgent
from agents.correctness_agent import CorrectnessAgent
from agents.explainer_agent import ExplainerAgent

logger = logging.getLogger(__name__)

_FEEDBACK_SYSTEM_PROMPT = """\
You are a Teacher Assistant that provides final, consolidated feedback
on student submissions.  You will receive:
- The student's cleaned work,
- A correctness assessment (score, mistakes),
- Detailed explanations for any mistakes,
- Suggestions for improvement.

Produce a FINAL FEEDBACK REPORT that is:
1. Encouraging and constructive.
2. Clearly structured with sections: Summary, Score, Strengths,
   Areas for Improvement, Detailed Explanations, Suggestions.
3. Written in student-friendly language.
"""

_QUESTION_SYSTEM_PROMPT = """\
You are a friendly, knowledgeable Teacher Assistant.  A student is asking
you a question.  Provide a clear, detailed, and encouraging answer.
If the question involves maths, show step-by-step working.
If you are unsure, say so honestly.
"""


class FeedbackAgent:
    """Orchestrator agent that chains OCR → Handwriting → Correctness →
    Explainer → Feedback to produce a comprehensive assessment.
    """

    def __init__(self) -> None:
        self.handwriting_agent = HandwritingAgent()
        self.correctness_agent = CorrectnessAgent()
        self.explainer_agent = ExplainerAgent()

        # For final feedback synthesis
        self._feedback_agent = BaseAgent(
            system_prompt=_FEEDBACK_SYSTEM_PROMPT,
            tools=None,
            tool_registry=None,
        )
        # For direct question answering
        self._question_agent = BaseAgent(
            system_prompt=_QUESTION_SYSTEM_PROMPT,
            tools=None,
            tool_registry=None,
        )

    # ------------------------------------------------------------------
    # Full pipeline
    # ------------------------------------------------------------------

    async def process_submission(
        self,
        filepath: Optional[str] = None,
        text_input: Optional[str] = None,
        submission_type: str = "notebook",
        question_context: str = "",
    ) -> dict[str, Any]:
        """Run the full feedback pipeline.

        Parameters
        ----------
        filepath:
            Path to an uploaded image or PDF.  Used for OCR-based
            submissions (notebooks, assignments).
        text_input:
            Direct text input.  Skips OCR stages.
        submission_type:
            One of ``notebook``, ``assignment``, ``solution``, ``question``.
        question_context:
            Optional original problem statement for correctness checking.

        Returns
        -------
        dict
            Complete feedback payload with all intermediate results.
        """
        logs: list[str] = []
        extracted_text: str = ""
        cleaned_text: str = ""

        # ----- YouTube URL Handling -----------------------------------------
        if submission_type == "youtube" and text_input:
            logger.info("Processing YouTube URL via Thumbnail Extraction: %s", text_input)
            logs.append(f"=== Processing YouTube Video ===\nURL: {text_input}")
            
            import re
            import io
            import base64
            import requests
            from PIL import Image

            def extract_video_id(url: str) -> str | None:
                patterns = [
                    r'(?:v=|/v/|youtu\.be/)([a-zA-Z0-9_-]{11})',
                    r'(?:embed/)([a-zA-Z0-9_-]{11})',
                    r'(?:shorts/)([a-zA-Z0-9_-]{11})',
                ]
                for pattern in patterns:
                    m = re.search(pattern, url)
                    if m:
                        return m.group(1)
                return None

            def extract_youtube_thumbnails(url: str) -> list[Image.Image]:
                vid = extract_video_id(url)
                if not vid:
                    return []
                thumb_urls = [
                    f"https://img.youtube.com/vi/{vid}/maxresdefault.jpg",
                    f"https://img.youtube.com/vi/{vid}/sddefault.jpg",
                    f"https://img.youtube.com/vi/{vid}/hqdefault.jpg",
                    f"https://img.youtube.com/vi/{vid}/mqdefault.jpg",
                    f"https://img.youtube.com/vi/{vid}/0.jpg",
                    f"https://img.youtube.com/vi/{vid}/1.jpg",
                    f"https://img.youtube.com/vi/{vid}/2.jpg",
                    f"https://img.youtube.com/vi/{vid}/3.jpg",
                ]
                frames = []
                seen_sizes = set()
                for t_url in thumb_urls:
                    try:
                        r = requests.get(t_url, timeout=10)
                        if r.status_code == 200 and len(r.content) > 1000:
                            img = Image.open(io.BytesIO(r.content)).convert("RGB")
                            if img.size[0] >= 200 and img.size not in seen_sizes:
                                frames.append(img)
                                seen_sizes.add(img.size)
                    except Exception:
                        continue
                return frames

            def image_to_base64_url(img: Image.Image, max_side: int | None = 1280) -> str:
                if img.mode not in ("RGB",):
                    img = img.convert("RGB")
                if max_side is not None:
                    w, h = img.size
                    if max(w, h) > max_side:
                        scale = max_side / max(w, h)
                        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=85)
                b64_str = base64.b64encode(buf.getvalue()).decode("utf-8")
                return f"data:image/jpeg;base64,{b64_str}"

            logs.append("Extracting thumbnails from YouTube CDN...")
            frames = extract_youtube_thumbnails(text_input)
            
            if not frames:
                return {
                    "error": "Could not extract thumbnails for the video.",
                    "extracted_text": text_input,
                    "cleaned_text": "",
                    "correctness": {"correct": False, "score": 0, "mistakes": [], "steps_analysis": []},
                    "correctness_score": 0,
                    "mistakes": [],
                    "mistakes_json": "[]",
                    "explanation": "",
                    "overall_feedback": "Could not extract thumbnails. Please ensure the URL is correct and the video is public.",
                    "suggestions": "Try another video or format.",
                    "agent_log": "\n".join(logs) + "\nFailed to get thumbnails.",
                }

            logs.append(f"Successfully fetched {len(frames)} thumbnails.")
            extracted_text = f"YouTube URL: {text_input}\nFrames extracted: {len(frames)}"
            cleaned_text = text_input
            
            # Generate detailed report
            logs.append("Requesting the model to analyze the YouTube URL via thumbnails...")
            report_prompt = (
                "You are an expert AI Teacher Assistant. A student has provided a YouTube video link for learning.\n\n"
                f"**Video URL:**\n{cleaned_text}\n\n"
                "Please analyze the content of this YouTube video based on the provided thumbnails. Provide a detailed, comprehensive report "
                "of the video's full explanation. Structure your report clearly with an Introduction, Key Concepts, "
                "Detailed Breakdown, and a Summary. Use encouraging, educational language to help the student "
                "understand the material deeply."
            )
            
            payload = []
            for frame in frames:
                payload.append({
                    "type": "image_url",
                    "image_url": {"url": image_to_base64_url(frame)}
                })
            payload.append({"type": "text", "text": report_prompt})

            overall_feedback = await self._feedback_agent.run(payload)
            logs.append(self._feedback_agent.get_agent_log())
            
            return {
                "extracted_text": extracted_text,
                "cleaned_text": cleaned_text,
                "correctness": {"correct": True, "score": 100, "mistakes": [], "steps_analysis": []},
                "correctness_score": 100,
                "mistakes": [],
                "mistakes_json": "[]",
                "explanation": "Detailed video report generated via thumbnail analysis.",
                "overall_feedback": overall_feedback,
                "suggestions": "Review the summary and try explaining the concepts in your own words to reinforce learning.",
                "agent_log": "\n".join(logs),
            }

        # ----- Stage 1: Text acquisition -----------------------------------
        if filepath and os.path.isfile(filepath):
            logger.info("Stage 1 & 2: Direct VLM extraction from %s", filepath)
            logs.append("=== Stage 1 & 2: Direct VLM Extraction ===")
            
            with open(filepath, "rb") as f:
                encoded_file = base64.b64encode(f.read()).decode("utf-8")
                
            mime_type, _ = mimetypes.guess_type(filepath)
            if not mime_type:
                mime_type = "image/jpeg"
                
            multimodal_payload = [
                {"type": "text", "text": "Extract all handwriting and math from this document."},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{mime_type};base64,{encoded_file}"
                    }
                }
            ]

            cleaned_text = await self.handwriting_agent.process(multimodal_payload)
            logs.append(f"Cleaned text ({len(cleaned_text)} chars)")
            logs.append(self.handwriting_agent.get_log())
            
            # Since we bypassed OCR agent, extracted_text is the same as cleaned
            extracted_text = cleaned_text

        elif text_input:
            logger.info("Stage 1-2: Using provided text input directly")
            logs.append("=== Stages 1-2: Direct text input (no OCR needed) ===")
            extracted_text = text_input
            cleaned_text = text_input
        else:
            return {
                "error": "No file or text input provided.",
                "extracted_text": "",
                "cleaned_text": "",
                "correctness": {},
                "explanation": "",
                "overall_feedback": "",
                "suggestions": "",
                "agent_log": "No input provided.",
            }

        # ----- Stage 3: Correctness checking --------------------------------
        logger.info("Stage 3: Correctness checking")
        logs.append("\n=== Stage 3: Correctness Analysis ===")

        correctness = await self.correctness_agent.process(
            student_work=cleaned_text,
            question_context=question_context,
        )
        logs.append(f"Correctness result: score={correctness.get('score', '?')}")
        logs.append(self.correctness_agent.get_log())

        mistakes: list[dict[str, Any]] = correctness.get("mistakes", [])

        # ----- Stage 4: Explanation generation ------------------------------
        logger.info("Stage 4: Generating explanations")
        logs.append("\n=== Stage 4: Explanation Generation ===")

        explanation = await self.explainer_agent.process(
            mistakes=mistakes,
            original_work=cleaned_text,
        )
        logs.append(f"Explanation ({len(explanation)} chars)")
        logs.append(self.explainer_agent.get_log())

        # ----- Stage 5: Final feedback synthesis ----------------------------
        logger.info("Stage 5: Synthesising final feedback")
        logs.append("\n=== Stage 5: Final Feedback Synthesis ===")

        synthesis_prompt = (
            "Here is the complete analysis of a student's submission.\n\n"
            f"**Submission type:** {submission_type}\n\n"
            "**Student's cleaned work:**\n"
            f"{cleaned_text}\n\n"
            "**Correctness assessment:**\n"
            f"Score: {correctness.get('score', 0)}/100\n"
            f"Correct: {correctness.get('correct', False)}\n"
            f"Mistakes: {json.dumps(mistakes, indent=2)}\n\n"
            "**Detailed explanations:**\n"
            f"{explanation}\n\n"
            "Please produce the final, consolidated feedback report."
        )
        overall_feedback = await self._feedback_agent.run(synthesis_prompt)
        logs.append(self._feedback_agent.get_agent_log())

        # Build suggestions from mistakes
        suggestions = self._build_suggestions(mistakes, correctness)

        return {
            "extracted_text": extracted_text,
            "cleaned_text": cleaned_text,
            "correctness": correctness,
            "correctness_score": correctness.get("score", 0),
            "mistakes": mistakes,
            "mistakes_json": json.dumps(mistakes),
            "explanation": explanation,
            "overall_feedback": overall_feedback,
            "suggestions": suggestions,
            "agent_log": "\n".join(logs),
        }

    # ------------------------------------------------------------------
    # Direct question answering
    # ------------------------------------------------------------------

    async def process_question(self, question: str) -> dict[str, Any]:
        """Answer a student's text question directly.

        Parameters
        ----------
        question:
            The student's question text.

        Returns
        -------
        dict
            Payload with the answer and metadata.
        """
        logger.info("Answering student question (%d chars)", len(question))
        answer = await self._question_agent.run(question)
        return {
            "extracted_text": question,
            "cleaned_text": question,
            "correctness": {"correct": True, "score": 100, "mistakes": [], "steps_analysis": []},
            "correctness_score": 100,
            "mistakes": [],
            "mistakes_json": "[]",
            "explanation": "",
            "overall_feedback": answer,
            "suggestions": "Keep asking questions — curiosity is the best way to learn!",
            "agent_log": self._question_agent.get_agent_log(),
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_suggestions(
        mistakes: list[dict[str, Any]],
        correctness: dict[str, Any],
    ) -> str:
        """Build a suggestions string based on the mistake analysis."""
        if not mistakes:
            return (
                "Excellent work! All problems appear to be correct. "
                "Consider challenging yourself with more advanced problems."
            )

        error_types: set[str] = {m.get("error_type", "unknown") for m in mistakes}
        suggestions_parts: list[str] = [
            f"You had {len(mistakes)} mistake(s) to review."
        ]

        if "arithmetic" in error_types:
            suggestions_parts.append(
                "• Practice basic arithmetic — double-check calculations."
            )
        if "algebraic" in error_types:
            suggestions_parts.append(
                "• Review algebra rules, especially sign handling and "
                "distribution."
            )
        if "conceptual" in error_types:
            suggestions_parts.append(
                "• Revisit the underlying concepts — understanding 'why' "
                "helps avoid repeated errors."
            )
        if "sign" in error_types:
            suggestions_parts.append(
                "• Pay extra attention to positive/negative signs in each "
                "step."
            )

        suggestions_parts.append(
            "• After reviewing explanations, try similar problems to "
            "reinforce your understanding."
        )

        return "\n".join(suggestions_parts)

    # ------------------------------------------------------------------
    # Contextual Chat
    # ------------------------------------------------------------------

    async def process_contextual_chat(
        self,
        question: str,
        chat_history: list[dict[str, str]],
        document_context: str,
        feedback_context: str,
    ) -> str:
        """Handle a follow-up question regarding a specific submission.

        Spins up a temporary agent loaded with the submission context and
        the conversation history, then returns the assistant's answer.
        """
        system_prompt = (
            "You are a Teacher Assistant helping a student understand their specific submission. "
            "Below is the context of their submission and the feedback they received.\n\n"
            f"--- STUDENT DOCUMENT ---\n{document_context}\n--- END DOCUMENT ---\n\n"
            f"--- AI FEEDBACK ---\n{feedback_context}\n--- END FEEDBACK ---\n\n"
            "Use this context to answer the student's questions accurately and patiently. "
            "Show step-by-step working if math is involved."
        )

        agent = BaseAgent(
            system_prompt=system_prompt,
            tools=None,
            tool_registry=None,
        )

        # Pre-load the conversation history into the agent
        agent._messages = [{"role": "system", "content": system_prompt}]
        for msg in chat_history:
            # chat_history format from DB: {"role": "user", "content": ...}
            agent._messages.append({"role": msg["role"], "content": msg["content"]})

        # The BaseAgent's run method expects a new user input and handles max_iterations.
        # But wait, run() resets self._messages! We need to bypass the reset or modify run().
        # Actually, let's just make the run call with the new question.
        # Wait! BaseAgent.run(user_input) resets the messages!
        # Let's fix BaseAgent.run to NOT reset if we pass a flag, or we can just
        # invoke the LLM directly here since we don't need tools.

        # Direct LLM invocation (no tools needed for chat)
        agent._messages.append({"role": "user", "content": question})
        import asyncio
        response = await asyncio.to_thread(
            agent.client.chat.completions.create,
            model=agent.model,
            messages=agent._messages,
        )
        return response.choices[0].message.content or ""
