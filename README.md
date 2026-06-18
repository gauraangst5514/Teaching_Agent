# AI Teacher Assistant

A Multimodal AI-powered teacher assistant designed to automate grading, provide detailed student feedback, and explain complex concepts interactively. Built with FastAPI and powered by an LLM via vLLM endpoint.

## Features

- **Student Portal**: Students can submit their assignments, including multimodal inputs like images.
- **Automated Grading & Feedback**: Uses an ensemble of AI agents (e.g., correctness, handwriting, and explainer agents) to evaluate submissions and provide constructive feedback.
- **Interactive Explanations**: Includes a chat interface for students to ask follow-up questions or get complex concepts explained in simple terms.
- **Teacher Dashboard**: View overall submission statistics, recent submissions, and detailed feedback metrics.

## Tech Stack

- **Backend**: Python 3.9+, FastAPI
- **Frontend**: Jinja2 Templates, HTML/CSS/JS
- **Database**: SQLite (via aiosqlite)
- **AI Integration**: Connects to an OpenAI-compatible vLLM endpoint for local/remote LLM inference.

## Setup & Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/gauraangst5514/Teaching_Agent.git
   cd Teaching_Agent
   ```

2. Create a virtual environment and install dependencies:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. Setup environment variables:
   Copy the `.env.example` file to `.env` (if provided) or configure your `.env` directly:
   - `VLLM_BASE_URL`: Base URL to your vLLM endpoint (e.g. `http://localhost:8000/v1`)
   - `VLLM_API_KEY`: Usually `EMPTY` for a local vLLM, or your actual API key
   - `VLLM_MODEL`: The LLM model name being used

4. Initialize the database:
   *(The app handles database initialization automatically on startup)*

5. Run the server:
   ```bash
   uvicorn app:app --host 0.0.0.0 --port 8000 --reload
   ```

6. Open your browser:
   Navigate to `http://localhost:8000` to access the application.

## Project Structure

- `app.py`: Main FastAPI application, routes, and startup logic.
- `config.py`: Configuration and environment variable management.
- `database.py`: SQLite database models and CRUD operations.
- `agents/`: Contains specialized AI agents for feedback, explanation, correctness, and handwriting analysis.
- `tools/`: Utility tools (e.g., math tools) utilized by the agents.
- `templates/`: Jinja2 HTML templates for the UI.
- `static/`: Static CSS and JavaScript files.
