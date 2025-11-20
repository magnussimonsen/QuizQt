"""FastAPI server that exposes student endpoints."""

from __future__ import annotations

from threading import Thread

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import uvicorn

from quiz_app.constants.network_constants import DEFAULT_HOST, DEFAULT_PORT
from quiz_app.core.markdown_math_renderer import renderer
from quiz_app.core.quiz_manager import QuizManager

_STUDENT_PAGE_HTML = """<!doctype html>
<html lang=\"en\">
  <head>
    <meta charset=\"utf-8\" />
    <title>QuizQt Student</title>
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <style>
      :root { font-family: 'Inter', system-ui, sans-serif; background: #0b1120; color: #f5f7ff; }
      body { margin: 0; padding: 1.5rem; display: flex; flex-direction: column; gap: 1rem; }
      .card { background: #111a30; border-radius: 0.75rem; padding: 1.5rem; box-shadow: 0 0.5rem 1.5rem rgba(0, 0, 0, 0.4); }
      #question-container { min-height: 6rem; font-size: 1.1rem; line-height: 1.6; }
      .options-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 0.75rem; }
      .option-button { border: none; border-radius: 0.75rem; padding: 1rem; font-size: 1rem; background: #1f9aa5; color: #fff; cursor: pointer; transition: transform 120ms ease, background 120ms ease; }
      .option-button:hover { transform: translateY(-2px); background: #16808a; }
      .option-button:disabled { opacity: 0.5; cursor: not-allowed; }
      #status { min-height: 1.25rem; }
    </style>
    <script>
      window.MathJax = { tex: { inlineMath: [['$','$']], displayMath: [['$$','$$']] }, svg: { fontCache: 'global' } };
    </script>
    <script defer src=\"https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js\"></script>
  </head>
  <body>
    <section class=\"card\">
      <h1>QuizQt Student Page</h1>
      <div id=\"question-container\">Waiting for the teacher to start a question…</div>
    </section>
    <section class=\"card\">
      <div id=\"options-container\" class=\"options-grid\"></div>
      <p id=\"status\"></p>
    </section>
    <script>
      const questionContainer = document.getElementById('question-container');
      const optionsContainer = document.getElementById('options-container');
      const statusEl = document.getElementById('status');

      function buildOptionButton(optionText, index) {
        const button = document.createElement('button');
        button.className = 'option-button';
        button.textContent = `${String.fromCharCode(65 + index)}. ${optionText}`;
        button.addEventListener('click', () => submitAnswer(index));
        return button;
      }

      function renderOptions(options, active) {
        optionsContainer.innerHTML = '';
        options.forEach((option, index) => {
          const button = buildOptionButton(option, index);
          button.disabled = !active;
          optionsContainer.appendChild(button);
        });
      }

      async function refreshQuestion() {
        try {
          const response = await fetch('/question');
          const payload = await response.json();
          if (payload.active && payload.question_html) {
            questionContainer.innerHTML = payload.question_html;
            const options = Array.isArray(payload.options) ? payload.options : [];
            renderOptions(options, true);
            statusEl.textContent = '';
            if (window.MathJax?.typesetPromise) {
              await MathJax.typesetPromise([questionContainer]);
            }
          } else {
            questionContainer.textContent = 'Waiting for the teacher to start a question…';
            renderOptions([], false);
          }
        } catch (error) {
          questionContainer.textContent = 'Unable to reach the quiz server.';
          renderOptions([], false);
        }
      }

      async function submitAnswer(optionIndex) {
        try {
          const response = await fetch('/answer', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ selected_option_index: optionIndex })
          });
          if (response.ok) {
            statusEl.textContent = 'Answer sent!';
          } else {
            const body = await response.json();
            statusEl.textContent = body.detail ?? 'Unable to send answer.';
          }
        } catch (error) {
          statusEl.textContent = 'Unable to send answer.';
        }
      }

      refreshQuestion();
      setInterval(refreshQuestion, 2000);
    </script>
  </body>
</html>
"""


class AnswerPayload(BaseModel):
  """Payload schema for submitted answers."""

  selected_option_index: int


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
        active = manager.is_question_active()
        if question is None:
            return {"active": False, "question_html": None, "options": []}
        fragment = renderer.render_fragment(question.question_text)
        return {
            "active": active,
            "question_id": question.id,
            "question_html": fragment,
            "options": question.options,
        }

    @app.post("/answer", status_code=201)
    def submit_answer(
        payload: AnswerPayload,
        manager: QuizManager = Depends(quiz_manager_dep),
    ) -> dict[str, object]:
        try:
          submission = manager.record_selected_option(payload.selected_option_index)
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
