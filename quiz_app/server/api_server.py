"""FastAPI server that exposes student endpoints."""

from __future__ import annotations

from threading import Thread

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import uvicorn

from quiz_app.constants.network_constants import DEFAULT_HOST, DEFAULT_PORT
from quiz_app.core.quiz_manager import QuizManager

_STUDENT_PAGE_HTML = """<!doctype html>
<html lang=\"en\">
  <head>
    <meta charset=\"utf-8\" />
    <title>QuizQt Student</title>
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <style>
      :root { font-family: system-ui, sans-serif; background: #101625; color: #f5f7ff; }
      body { margin: 0; padding: 1.5rem; display: flex; flex-direction: column; gap: 1rem; }
      .card { background: #1c2438; border-radius: 0.75rem; padding: 1.5rem; box-shadow: 0 0.5rem 1.5rem rgba(0, 0, 0, 0.3); }
      button { background: #12a594; border: none; padding: 0.75rem 1.25rem; color: #fff; font-size: 1rem; border-radius: 0.5rem; cursor: pointer; }
      button:hover { background: #0c7c6f; }
      input { width: 100%; padding: 0.75rem; font-size: 1rem; border-radius: 0.5rem; border: 1px solid #3a4258; margin-bottom: 0.75rem; }
      #status { min-height: 1.25rem; }
    </style>
  </head>
  <body>
    <section class=\"card\">
      <h1>QuizQt Student Page</h1>
      <p id=\"question-text\">Waiting for the teacher to start a question…</p>
    </section>
    <section class=\"card\">
      <form id=\"answer-form\">
        <label for=\"answer-input\">Your answer</label>
        <input id=\"answer-input\" name=\"answer\" autocomplete=\"off\" />
        <button type=\"submit\">Submit answer</button>
      </form>
      <p id=\"status\"></p>
    </section>
    <script>
      const questionTextEl = document.getElementById('question-text');
      const statusEl = document.getElementById('status');
      const formEl = document.getElementById('answer-form');
      const answerInput = document.getElementById('answer-input');

      async function refreshQuestion() {
        try {
          const response = await fetch('/question');
          const payload = await response.json();
          if (payload.active) {
            questionTextEl.textContent = payload.question_text ?? 'Question is active.';
          } else {
            questionTextEl.textContent = 'Waiting for the teacher to start a question…';
          }
        } catch (error) {
          questionTextEl.textContent = 'Unable to reach the quiz server.';
        }
      }

      formEl.addEventListener('submit', async (event) => {
        event.preventDefault();
        const answerText = answerInput.value.trim();
        if (!answerText) {
          statusEl.textContent = 'Please type an answer first.';
          return;
        }
        try {
          const response = await fetch('/answer', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ answer_text: answerText })
          });
          if (response.ok) {
            statusEl.textContent = 'Answer sent!';
            answerInput.value = '';
          } else {
            const body = await response.json();
            statusEl.textContent = body.detail ?? 'Unable to send answer.';
          }
        } catch (error) {
          statusEl.textContent = 'Unable to send answer.';
        }
      });

      refreshQuestion();
      setInterval(refreshQuestion, 2000);
    </script>
  </body>
</html>
"""


class AnswerPayload(BaseModel):
    """Payload schema for submitted answers."""

    answer_text: str


def _get_quiz_manager_dependency(quiz_manager: QuizManager):
    def dependency() -> QuizManager:
        return quiz_manager

    return dependency


def create_api_app(quiz_manager: QuizManager) -> FastAPI:
    """Create a FastAPI application wired to the provided quiz manager."""
    app = FastAPI(title="QuizQt API", version="0.1.0")
    quiz_manager_dep = _get_quiz_manager_dependency(quiz_manager)

    @app.get("/", response_class=HTMLResponse)
    def serve_student_page() -> str:
        return _STUDENT_PAGE_HTML

    @app.get("/question")
    def get_question(manager: QuizManager = Depends(quiz_manager_dep)) -> dict[str, object]:
        question = manager.get_current_question()
        if question is None:
            return {"active": False, "question_text": None}
        return {"active": question.is_active, "question_text": question.question_text}

    @app.post("/answer", status_code=201)
    def submit_answer(
        payload: AnswerPayload,
        manager: QuizManager = Depends(quiz_manager_dep),
    ) -> dict[str, object]:
        try:
            submission = manager.add_answer(payload.answer_text)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

        return {
            "question_id": submission.question_id,
            "submitted_at": submission.submitted_at.isoformat(),
        }

    return app


def start_api_server(
    quiz_manager: QuizManager,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
) -> Thread:
    """Start the FastAPI server in a background daemon thread."""
    app = create_api_app(quiz_manager)
    config = uvicorn.Config(app=app, host=host, port=port, log_level="info")
    server = uvicorn.Server(config)

    def run_server() -> None:
        server.run()

    thread = Thread(target=run_server, name="QuizApiServer", daemon=True)
    thread.start()
    return thread
