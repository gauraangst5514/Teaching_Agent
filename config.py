"""
Configuration module for the Teacher Assistant app.

Loads settings from the parent project's .env file or environment variables.
Provides vLLM connection details, database URL, and upload directory paths.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from the parent directory (project root) first, then local .env
_parent_env = Path(__file__).resolve().parent.parent / ".env"
_local_env = Path(__file__).resolve().parent / ".env"

if _parent_env.exists():
    load_dotenv(_parent_env)
if _local_env.exists():
    load_dotenv(_local_env, override=True)


class TAConfig:
    """Teacher Assistant application configuration."""

    # vLLM / Alpie model settings
    VLLM_BASE_URL: str = os.getenv(
        "VLLM_BASE_URL", "http://20.245.200.125:8000/v1"
    )
    VLLM_API_KEY: str = os.getenv("VLLM_API_KEY", "EMPTY")
    VLLM_MODEL: str = os.getenv(
        "VLLM_MODEL",
        "/home/azureuser/.cache/huggingface/hub/models--169Pi--Alpie_learn_sft_merged",
    )

    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///teacher_assistant.db")
    DB_PATH: str = os.getenv(
        "DB_PATH",
        str(Path(__file__).resolve().parent / "teacher_assistant.db"),
    )

    # File uploads
    UPLOAD_DIR: str = os.getenv(
        "UPLOAD_DIR",
        str(Path(__file__).resolve().parent / "uploads"),
    )

    # Agent settings
    MAX_AGENT_ITERATIONS: int = int(os.getenv("MAX_AGENT_ITERATIONS", "15"))
    MAX_TOOL_RESULT_LENGTH: int = int(os.getenv("MAX_TOOL_RESULT_LENGTH", "100000"))

    @classmethod
    def validate(cls) -> None:
        """Validate that required configuration values are present."""
        if not cls.VLLM_BASE_URL:
            raise ValueError("VLLM_BASE_URL is missing. Please set it in .env")
        if not cls.VLLM_MODEL:
            raise ValueError("VLLM_MODEL is missing. Please set it in .env")

    @classmethod
    def ensure_directories(cls) -> None:
        """Create required directories if they don't exist."""
        os.makedirs(cls.UPLOAD_DIR, exist_ok=True)


ta_config = TAConfig()
ta_config.ensure_directories()
