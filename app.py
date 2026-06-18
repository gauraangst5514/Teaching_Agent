"""
Teacher Assistant - FastAPI Application
Main entry point for the AI-powered teacher assistant.
"""

import os
import sys
import json
import uuid
import shutil
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Optional

# Ensure the teacher_assistant package directory is on the path so that
# intra-package imports like ``from config import ta_config`` resolve
# correctly regardless of where the process was started.
_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from fastapi import FastAPI, UploadFile, File, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from config import ta_config
from database import (
    init_db,
    create_submission,
    update_submission,
    get_submission,
    get_all_submissions,
    create_feedback,
    get_feedback_for_submission,
    get_dashboard_stats,
    add_chat_message,
    get_chat_history,
)
from agents.feedback_agent import FeedbackAgent

# ---------------------------------------------------------------------------
# App Setup
# ---------------------------------------------------------------------------

app = FastAPI(
    title="AI Teacher Assistant",
    description="Multimodal AI-powered teacher assistant for grading, feedback, and concept explanation.",
    version="1.0.0",
)

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = Path(ta_config.UPLOAD_DIR)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Mount static files
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
# Serve uploaded files so images can be displayed
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# ---------------------------------------------------------------------------
# Startup / Shutdown
# ---------------------------------------------------------------------------

@app.on_event("startup")
async def startup():
    """Initialize database on startup."""
    await init_db()
    print("✅ Database initialized")
    print(f"✅ Upload directory: {UPLOAD_DIR}")
    print(f"✅ vLLM endpoint: {ta_config.VLLM_BASE_URL}")


# ---------------------------------------------------------------------------
# Helper: save uploaded file
# ---------------------------------------------------------------------------

def _save_upload(file: UploadFile) -> str:
    """Save an uploaded file and return its relative path."""
    ext = Path(file.filename).suffix.lower() if file.filename else ".bin"
    unique_name = f"{uuid.uuid4().hex}{ext}"
    dest = UPLOAD_DIR / unique_name
    with open(dest, "wb") as buf:
        shutil.copyfileobj(file.file, buf)
    return unique_name  # relative to UPLOAD_DIR


# ---------------------------------------------------------------------------
# Routes — Student Portal
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def student_portal(request: Request):
    """Render the student portal page."""
    submissions = await get_all_submissions()
    # Show only the 10 most recent
    recent = submissions[:10] if submissions else []
    return templates.TemplateResponse(
        request=request,
        name="student.html",
        context={"request": request, "recent_submissions": recent},
    )


@app.post("/submit")
async def submit(
    request: Request,
    student_name: str = Form(...),
    submission_type: str = Form(...),
    question_text: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
):
    """Handle a new student submission (file upload and/or question)."""

    file_path = None
    original_text = question_text

    # Save file if provided
    if file and file.filename:
        file_path = _save_upload(file)

    # Create submission record
    submission_id = await create_submission(
        student_name=student_name,
        submission_type=submission_type,
        file_path=file_path,
        original_text=original_text,
    )

    # Process synchronously to ensure Modal container stays alive
    await _process_submission(submission_id, file_path, original_text, submission_type)

    return RedirectResponse(url=f"/submission/{submission_id}", status_code=303)


async def _process_submission(
    submission_id: int,
    file_path: Optional[str],
    text_input: Optional[str],
    submission_type: str,
):
    """Background task: run the full agent pipeline on a submission."""
    try:
        await update_submission(submission_id, status="processing")

        agent = FeedbackAgent()

        full_file_path = str(UPLOAD_DIR / file_path) if file_path else None

        if submission_type == "question" and text_input:
            result = await agent.process_question(text_input)
        else:
            result = await agent.process_submission(
                filepath=full_file_path,
                text_input=text_input,
                submission_type=submission_type,
            )

        # Save extracted text back to submission
        extracted = result.get("extracted_text", "")
        await update_submission(
            submission_id,
            status="completed",
            extracted_text=extracted,
        )

        # Save feedback
        await create_feedback(
            submission_id=submission_id,
            correctness_score=result.get("correctness_score", 0),
            mistakes_json=result.get("mistakes_json", "[]"),
            explanation=result.get("explanation", ""),
            suggestions=result.get("suggestions", ""),
            overall_feedback=result.get("overall_feedback", ""),
            agent_log=result.get("agent_log", ""),
        )

        print(f"✅ Submission {submission_id} processed successfully (score: {result.get('correctness_score', 'N/A')})")

    except Exception as e:
        print(f"❌ Error processing submission {submission_id}: {e}")
        import traceback
        traceback.print_exc()
        await update_submission(submission_id, status="failed")


# ---------------------------------------------------------------------------
# Routes — Submission Detail
# ---------------------------------------------------------------------------

@app.get("/submission/{submission_id}", response_class=HTMLResponse)
async def submission_detail(request: Request, submission_id: int):
    """Render the submission detail page with AI feedback."""
    submission = await get_submission(submission_id)
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    # get_feedback_for_submission returns a list; take the most recent one
    feedback_list = await get_feedback_for_submission(submission_id)
    feedback = feedback_list[0] if feedback_list else None

    # Parse mistakes JSON for template
    if feedback and feedback.get("mistakes_json"):
        try:
            feedback["mistakes"] = json.loads(feedback["mistakes_json"])
        except json.JSONDecodeError:
            feedback["mistakes"] = []
    elif feedback:
        feedback["mistakes"] = []

    return templates.TemplateResponse(
        request=request,
        name="submission.html",
        context={
            "request": request,
            "submission": submission,
            "feedback": feedback,
        },
    )

from fastapi.responses import Response
import markdown
import pdfkit

@app.get("/submission/{submission_id}/download")
async def download_report(submission_id: int):
    """Download the AI feedback report as a PDF file."""
    submission = await get_submission(submission_id)
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    feedback_list = await get_feedback_for_submission(submission_id)
    feedback = feedback_list[0] if feedback_list else None
    
    if not feedback:
        raise HTTPException(status_code=404, detail="Feedback not ready")

    student_name = submission['student_name'] if isinstance(submission, dict) else submission.student_name
    sub_type = submission['submission_type'] if isinstance(submission, dict) else submission.submission_type

    lines = []
    lines.append(f"# AI Feedback Report - Submission #{submission_id}")
    lines.append(f"**Student:** {student_name}")
    lines.append(f"**Type:** {sub_type}")
    lines.append("")
    
    if feedback.get("correctness_score") is not None:
        lines.append(f"## Score: {feedback['correctness_score']}/100\n")

    if feedback.get("overall_feedback"):
        lines.append("## Overall Feedback")
        lines.append(feedback["overall_feedback"] + "\n")

    if feedback.get("explanation"):
        lines.append("## Detailed Explanation")
        lines.append(feedback["explanation"] + "\n")

    if feedback.get("suggestions"):
        lines.append("## Suggestions")
        lines.append(feedback["suggestions"] + "\n")
        
    md_content = "\n".join(lines)
    html_content = markdown.markdown(md_content)
    
    # Add a simple stylesheet so the PDF looks nice
    full_html = f"""
    <html>
    <head>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; color: #333; max-width: 800px; margin: 0 auto; padding: 20px; }}
        h1 {{ border-bottom: 1px solid #eee; padding-bottom: 10px; color: #111; }}
        h2 {{ margin-top: 30px; color: #222; }}
        code {{ background: #f4f4f4; padding: 2px 4px; border-radius: 3px; font-family: monospace; }}
        pre {{ background: #f4f4f4; padding: 15px; border-radius: 5px; overflow-x: auto; }}
    </style>
    </head>
    <body>
    {html_content}
    </body>
    </html>
    """
    
    try:
        pdf_bytes = pdfkit.from_string(full_html, False)
        headers = {
            "Content-Disposition": f"attachment; filename=report_{submission_id}.pdf"
        }
        return Response(content=pdf_bytes, media_type="application/pdf", headers=headers)
    except Exception as e:
        print(f"Error generating PDF: {e}")
        # Fallback to plain text if wkhtmltopdf fails
        headers = {
            "Content-Disposition": f"attachment; filename=report_{submission_id}.md"
        }
        from fastapi.responses import PlainTextResponse
        return PlainTextResponse(content=md_content, headers=headers)


# ---------------------------------------------------------------------------
# Routes — Quick Question (AJAX)
# ---------------------------------------------------------------------------

@app.post("/ask")
async def ask_question(request: Request):
    """Handle a quick text question via AJAX."""
    body = await request.json()
    question = body.get("question", "").strip()

    if not question:
        return JSONResponse({"answer": "Please provide a question."}, status_code=400)

    try:
        agent = FeedbackAgent()
        result = await agent.process_question(question)
        answer = result.get("overall_feedback", result.get("explanation", "I could not generate an answer."))
        return JSONResponse({"answer": answer})
    except Exception as e:
        print(f"❌ Error answering question: {e}")
        return JSONResponse({"answer": f"Sorry, an error occurred: {str(e)}"}, status_code=500)


# ---------------------------------------------------------------------------
# Routes — Teacher Dashboard
# ---------------------------------------------------------------------------

@app.get("/dashboard", response_class=HTMLResponse)
async def teacher_dashboard(request: Request):
    """Render the teacher dashboard."""
    submissions = await get_all_submissions()
    stats = await get_dashboard_stats()

    # Enrich submissions with feedback scores
    enriched = []
    for sub in submissions:
        feedback_list = await get_feedback_for_submission(sub["id"])
        sub_copy = dict(sub)
        fb = feedback_list[0] if feedback_list else None
        sub_copy["score"] = fb["correctness_score"] if fb else None
        enriched.append(sub_copy)

    # Map stats keys to what the template expects
    status_counts = stats.get("status_counts", {})
    template_stats = {
        "total_submissions": stats.get("total_submissions", 0),
        "avg_score": stats.get("average_correctness_score", 0),
        "completed_count": status_counts.get("completed", 0),
        "pending_count": status_counts.get("pending", 0) + status_counts.get("processing", 0),
    }

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "request": request,
            "submissions": enriched,
            "stats": template_stats,
        },
    )


# ---------------------------------------------------------------------------
# API — Submission Status (for polling)
# ---------------------------------------------------------------------------

@app.get("/api/submission/{submission_id}/status")
async def submission_status(submission_id: int):
    """Return the current status of a submission (for polling)."""
    submission = await get_submission(submission_id)
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    feedback_list = await get_feedback_for_submission(submission_id)
    feedback = feedback_list[0] if feedback_list else None

    return JSONResponse({
        "status": submission["status"],
        "has_feedback": feedback is not None,
        "score": feedback["correctness_score"] if feedback else None,
    })


# ---------------------------------------------------------------------------
# API — Contextual Chat
# ---------------------------------------------------------------------------

@app.get("/api/submission/{submission_id}/chat")
async def get_submission_chat(submission_id: int):
    """Retrieve the chat history for a given submission."""
    # Verify submission exists
    submission = await get_submission(submission_id)
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
        
    history = await get_chat_history(submission_id)
    return JSONResponse({"history": history})

@app.post("/api/submission/{submission_id}/chat")
async def post_submission_chat(request: Request, submission_id: int):
    """Post a new message to the contextual chat."""
    body = await request.json()
    question = body.get("question", "").strip()

    if not question:
        return JSONResponse({"error": "Please provide a question."}, status_code=400)

    # Verify submission and get context
    submission = await get_submission(submission_id)
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    feedback_list = await get_feedback_for_submission(submission_id)
    feedback = feedback_list[0] if feedback_list else None

    document_context = submission.get("extracted_text", "")
    feedback_context = ""
    if feedback:
        feedback_context = f"Score: {feedback.get('correctness_score')}\n"
        feedback_context += f"Overall Feedback: {feedback.get('overall_feedback')}\n"
        feedback_context += f"Mistakes: {feedback.get('mistakes_json')}\n"
        feedback_context += f"Explanation: {feedback.get('explanation')}\n"

    # Save user message
    await add_chat_message(submission_id, "user", question)

    # Fetch updated history
    chat_history = await get_chat_history(submission_id)

    try:
        agent = FeedbackAgent()
        answer = await agent.process_contextual_chat(
            question=question,
            chat_history=chat_history[:-1], # pass history excluding the new user message (since we add it manually in the agent)
            document_context=document_context,
            feedback_context=feedback_context
        )
        
        # Save agent reply
        await add_chat_message(submission_id, "assistant", answer)
        
        return JSONResponse({"answer": answer})
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"❌ Error in contextual chat: {e}")
        return JSONResponse({"error": f"Sorry, an error occurred: {str(e)}"}, status_code=500)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8080, reload=True)
