"""
Base agent class for the Teacher Assistant system.

Mirrors the agentic tool-calling loop from the project's ``agents/llm.py``
but uses async/await for FastAPI compatibility and accepts pluggable tool
definitions & registries.
"""

import json
import asyncio
import logging
from typing import Any, Callable, Optional

from openai import OpenAI

from config import ta_config

logger = logging.getLogger(__name__)


class BaseAgent:
    """LLM-backed agent with an agentic tool-calling loop.

    Parameters
    ----------
    system_prompt:
        The system message that shapes the agent's personality/role.
    tools:
        Optional list of OpenAI-format tool definitions.  When ``None`` or
        empty the agent runs in plain chat mode (no tool calling).
    tool_registry:
        Dict mapping tool function names to callables.  Used to dispatch
        tool calls returned by the model.
    max_iterations:
        Safety cap on the number of LLM round-trips in a single ``run()``
        invocation.
    """

    def __init__(
        self,
        system_prompt: str,
        tools: Optional[list[dict[str, Any]]] = None,
        tool_registry: Optional[dict[str, Callable[..., str]]] = None,
        max_iterations: int = 15,
    ) -> None:
        self.client = OpenAI(
            base_url=ta_config.VLLM_BASE_URL,
            api_key=ta_config.VLLM_API_KEY,
        )
        self.model: str = ta_config.VLLM_MODEL
        self.system_prompt = system_prompt
        self.tools = tools or []
        self.tool_registry = tool_registry or {}
        self.max_iterations = max_iterations

        # Per-run conversation (reset on each ``run`` call)
        self._messages: list[dict[str, Any]] = []
        self._agent_log: list[str] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run(self, user_input: str | list[dict[str, Any]]) -> str:
        """Execute the full agentic loop and return the final text response.

        1. Send the user message.
        2. If the model requests tool calls, execute them and feed results
           back into the conversation.
        3. Repeat until the model produces a plain text reply or the
           iteration cap is reached.
        """
        # Reset conversation for this run
        self._messages = [{"role": "system", "content": self.system_prompt}]
        self._agent_log = []
        self._messages.append({"role": "user", "content": user_input})

        iterations = 0
        while iterations < self.max_iterations:
            iterations += 1

            # Build kwargs — only pass tools when we actually have them
            create_kwargs: dict[str, Any] = {
                "model": self.model,
                "messages": self._messages,
            }
            if self.tools:
                create_kwargs["tools"] = self.tools
                create_kwargs["tool_choice"] = "auto"

            # Run synchronous OpenAI call in a thread so we don't block the
            # asyncio event loop
            response = await asyncio.to_thread(
                self.client.chat.completions.create, **create_kwargs
            )

            message = response.choices[0].message
            self._messages.append(message)

            # If no tool calls, we're done
            if not message.tool_calls:
                final = message.content or ""
                self._agent_log.append(f"[iter {iterations}] Final response received.")
                return final

            # Execute each tool call
            for tool_call in message.tool_calls:
                func_name: str = tool_call.function.name
                args_str: str = tool_call.function.arguments
                log_entry = f"[iter {iterations}] Tool call: {func_name}({args_str})"
                logger.info(log_entry)
                self._agent_log.append(log_entry)

                result = self._execute_tool(func_name, args_str)

                # Truncate to avoid context-window explosion
                if len(result) > ta_config.MAX_TOOL_RESULT_LENGTH:
                    result = result[: ta_config.MAX_TOOL_RESULT_LENGTH] + "... [TRUNCATED]"

                self._messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": func_name,
                        "content": result,
                    }
                )

        self._agent_log.append("[WARN] Reached max iterations without final response.")
        return "The agent reached its maximum iteration limit without producing a final answer."

    async def get_structured_response(
        self, prompt: str, schema: dict[str, Any]
    ) -> dict[str, Any]:
        """Ask the model for a JSON response matching *schema*.

        Uses a temporary message list so the main conversation is not
        polluted.  Parses the first JSON object found in the reply.
        """
        messages = [
            {"role": "system", "content": self.system_prompt},
            {
                "role": "user",
                "content": (
                    prompt
                    + "\n\nRespond with ONLY valid JSON matching this schema: "
                    + json.dumps(schema)
                ),
            },
        ]

        response = await asyncio.to_thread(
            self.client.chat.completions.create,
            model=self.model,
            messages=messages,
        )

        content: str = response.choices[0].message.content or ""
        return self._parse_json(content)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def get_agent_log(self) -> str:
        """Return the accumulated log for the most recent ``run()`` call."""
        return "\n".join(self._agent_log)

    def _execute_tool(self, func_name: str, args_str: str) -> str:
        """Look up *func_name* in the tool registry and execute it."""
        if func_name not in self.tool_registry:
            return f"Tool '{func_name}' not found in registry."
        try:
            args = json.loads(args_str)
            func = self.tool_registry[func_name]
            return str(func(**args))
        except json.JSONDecodeError as e:
            return f"Error parsing arguments for '{func_name}': {e}"
        except Exception as e:
            return f"Error executing '{func_name}': {e}"

    @staticmethod
    def _parse_json(content: str) -> dict[str, Any]:
        """Extract and parse the first JSON object from *content*."""
        try:
            start = content.find("{")
            end = content.rfind("}")
            if start != -1 and end != -1:
                return json.loads(content[start : end + 1])
            raise ValueError("No JSON object found in response.")
        except Exception as e:
            logger.warning("JSON parsing failed: %s\nRaw: %s", e, content)
            return {"error": f"Failed to parse JSON: {e}", "raw_content": content}
