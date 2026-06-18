"""
Modal GPU Deployment Script for Teacher Assistant

Deploy with:
    cd teacher_assistant && modal deploy modal_deploy.py

Serve locally for testing:
    cd teacher_assistant && modal serve modal_deploy.py
"""

import modal

# ---------------------------------------------------------------------------
# Container Image
# ---------------------------------------------------------------------------

image = (
    modal.Image.debian_slim(python_version="3.11")
    # System packages for Tesseract OCR and PDF rendering
    .apt_install(
        "tesseract-ocr",
        "tesseract-ocr-eng",
        "poppler-utils",
        "libgl1-mesa-glx",
        "libglib2.0-0",
        "wkhtmltopdf",
    )
    # Python dependencies
    .pip_install(
        "fastapi>=0.110.0",
        "uvicorn>=0.28.0",
        "python-multipart>=0.0.9",
        "jinja2>=3.1.3",
        "openai>=1.50.0",
        "pydantic>=2.9.0",
        "python-dotenv>=1.0.1",
        "pytesseract>=0.3.10",
        "pdf2image>=1.16.3",
        "Pillow>=10.2.0",
        "sympy>=1.12",
        "aiosqlite>=0.19.0",
        "aiofiles>=23.2.1",
        "youtube-transcript-api>=0.6.2",
        "pdfkit>=1.0.0",
        "markdown>=3.6.0",
    )
    .add_local_dir(
        ".",
        remote_path="/app",
        ignore=["__pycache__", ".pyc", "uploads", ".git", "modal_deploy.py"]
    )
)

# ---------------------------------------------------------------------------
# Modal App
# ---------------------------------------------------------------------------

app = modal.App(
    name="teacher-assistant",
    image=image,
)

# Volume for persistent storage (uploads + database)
volume = modal.Volume.from_name("teacher-assistant-data", create_if_missing=True)

# ---------------------------------------------------------------------------
# Web Endpoint
# ---------------------------------------------------------------------------

@app.function(
    gpu="T4",  # T4 is sufficient since inference happens on external vLLM server
    volumes={"/data": volume},
    timeout=600,
    secrets=[
        modal.Secret.from_dict({
            "VLLM_BASE_URL": "http://20.245.200.125:8000/v1",
            "VLLM_API_KEY": "EMPTY",
            "VLLM_MODEL": "/home/azureuser/.cache/huggingface/hub/models--169Pi--Alpie_learn_sft_merged",
            "UPLOAD_DIR": "/data/uploads",
            "DB_PATH": "/data/teacher_assistant.db",
        })
    ],
)
@modal.asgi_app()
def web():
    """Serve the Teacher Assistant FastAPI app."""
    import sys
    import os

    # Add the app directory to path so intra-package imports work
    sys.path.insert(0, "/app")

    # Ensure upload directory exists on the volume
    os.makedirs("/data/uploads", exist_ok=True)

    # Override config paths for Modal environment
    os.environ["UPLOAD_DIR"] = "/data/uploads"
    os.environ["DB_PATH"] = "/data/teacher_assistant.db"

    # Import and return the FastAPI app
    from app import app as fastapi_app

    return fastapi_app


# ---------------------------------------------------------------------------
# Optional: Standalone model inference endpoint for testing
# ---------------------------------------------------------------------------

@app.function(
    timeout=120,
    secrets=[
        modal.Secret.from_dict({
            "VLLM_BASE_URL": "http://20.245.200.125:8000/v1",
            "VLLM_API_KEY": "EMPTY",
            "VLLM_MODEL": "/home/azureuser/.cache/huggingface/hub/models--169Pi--Alpie_learn_sft_merged",
        })
    ],
)
def inference(prompt: str) -> str:
    """Direct inference endpoint for testing the vLLM connection."""
    import os
    from openai import OpenAI

    client = OpenAI(
        base_url=os.environ["VLLM_BASE_URL"],
        api_key=os.environ["VLLM_API_KEY"],
    )

    response = client.chat.completions.create(
        model=os.environ["VLLM_MODEL"],
        messages=[
            {"role": "system", "content": "You are an expert teacher assistant."},
            {"role": "user", "content": prompt},
        ],
        max_tokens=1024,
    )

    return response.choices[0].message.content
