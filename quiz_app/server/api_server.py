"""FastAPI server that exposes student endpoints."""

from __future__ import annotations

from threading import Thread

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import uvicorn

from quiz_app.constants.network_constants import DEFAULT_HOST, DEFAULT_PORT
from quiz_app.core.markdown_math_renderer import renderer
from quiz_app.core.name_assigner import NameAssigner
from quiz_app.core.quiz_manager import QuizManager

_ALIAS_COOKIE = "quizqt_display_name"
_NAME_POOL_GENERATION = -1


def _encode_alias_cookie(alias: str, generation: int) -> str:
  return f"{generation}|{alias}"


def _decode_alias_cookie(value: str | None) -> tuple[int | None, str | None]:
  if not value:
    return None, None
  if "|" in value:
    generation_str, alias = value.split("|", 1)
    try:
      return int(generation_str), alias
    except ValueError:
      return None, None
  return None, value


def _ensure_alias(
  request: Request,
  response: Response,
  manager: QuizManager,
  assigner: NameAssigner,
) -> str:
  global _NAME_POOL_GENERATION
  generation = manager.get_alias_generation()
  if generation != _NAME_POOL_GENERATION:
    assigner.reset_cycle()
    _NAME_POOL_GENERATION = generation
  cookie_generation, alias = _decode_alias_cookie(request.cookies.get(_ALIAS_COOKIE))
  if alias:
    if cookie_generation is None and generation == 0:
      return alias
    if cookie_generation == generation:
      return alias
  alias = assigner.next_name()
  response.set_cookie(
    key=_ALIAS_COOKIE,
    value=_encode_alias_cookie(alias, generation),
    max_age=60 * 60 * 24 * 30,
    samesite="lax",
    httponly=True,
  )
  return alias

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
      .student-name { margin-top: 0.25rem; color: #94a3b8; font-size: 0.95rem; }
    </style>
    <script>
      window.MathJax = { tex: { inlineMath: [['$','$']], displayMath: [['$$','$$']] }, svg: { fontCache: 'global' } };
    </script>
    <script defer src=\"https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js\"></script>
  </head>
  <body>
    <section class=\"card\">
      <h1>QuizQt Student Page</h1>
      <p id=\"student-name\" class=\"student-name\"></p>
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
      const studentNameEl = document.getElementById('student-name');
      
      let currentQuestionId = null;
      let hasAnswered = false;
      let myAnswer = null;
      let displayName = null;

      async function loadIdentity() {
        try {
          const response = await fetch('/identity');
          const payload = await response.json();
          displayName = payload.display_name || null;
          if (displayName) {
            studentNameEl.textContent = `You are ${displayName}`;
          } else {
            studentNameEl.textContent = '';
          }
        } catch (error) {
          console.error('Error fetching identity:', error);
          studentNameEl.textContent = '';
        }
      }

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
          button.disabled = !active || hasAnswered;
          optionsContainer.appendChild(button);
        });
      }

      async function typesetMath() {
        // Simple approach: wait for MathJax and typeset, with retries
        const targets = [questionContainer, optionsContainer];
        await new Promise(resolve => setTimeout(resolve, 100));
        for (let i = 0; i < 15; i++) {
          if (window.MathJax && window.MathJax.typesetPromise) {
            try {
              await window.MathJax.typesetPromise(targets);
              console.log('MathJax typeset successful on attempt', i + 1);
              return;
            } catch (err) {
              console.warn('MathJax typeset attempt', i + 1, 'error:', err);
            }
          }
          await new Promise(resolve => setTimeout(resolve, 150));
        }
        console.warn('MathJax typesetting failed after all retries');
      }

      async function refreshQuestion() {
        try {
          const response = await fetch('/question');
          const payload = await response.json();
          console.log('Question payload:', payload);
          if (payload.active) {
            // Only update if question has changed
            if (payload.question_id !== currentQuestionId) {
              console.log('New question detected, updating display');
              currentQuestionId = payload.question_id;
              hasAnswered = false; // Reset answer flag for new question
              myAnswer = null; // Reset stored answer
              // Display question HTML (or placeholder if empty)
              questionContainer.innerHTML = payload.question_html || '<p><em>(No question text)</em></p>';
              const options = Array.isArray(payload.options) ? payload.options : [];
              renderOptions(options, true);
              statusEl.textContent = '';
              statusEl.style.color = '#f5f7ff';
              // Typeset math with retry logic
              typesetMath();
            }
          } else {
            // Question is not active - teacher has stopped it or shown answer
            if (payload.correct_option_index !== null && myAnswer !== null && hasAnswered) {
              // Show correct/wrong feedback
              if (myAnswer === payload.correct_option_index) {
                statusEl.textContent = '✓ Correct!';
                statusEl.style.color = '#4ade80';
              } else {
                statusEl.textContent = '✗ Sorry, wrong answer. Correct answer: ' + String.fromCharCode(65 + payload.correct_option_index);
                statusEl.style.color = '#f87171';
              }
            }
            if (currentQuestionId !== null && payload.question_id === null) {
              console.log('Question not active or no question');
              currentQuestionId = null;
              hasAnswered = false;
              myAnswer = null;
              questionContainer.textContent = 'Waiting for the teacher to start a question…';
              renderOptions([], false);
            }
          }
        } catch (error) {
          console.error('Error fetching question:', error);
          questionContainer.textContent = 'Unable to reach the quiz server.';
          renderOptions([], false);
        }
      }

      async function submitAnswer(optionIndex) {
        if (hasAnswered) {
          statusEl.textContent = 'You have already answered this question!';
          return;
        }
        
        try {
          const response = await fetch('/answer', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ selected_option_index: optionIndex })
          });
          if (response.ok) {
            hasAnswered = true;
            myAnswer = optionIndex; // Store answer for later feedback
            // Disable all buttons
            const buttons = optionsContainer.querySelectorAll('.option-button');
            buttons.forEach(btn => btn.disabled = true);
            // Just show answer sent - feedback comes when teacher shows answer
            statusEl.textContent = 'Answer sent!';
            statusEl.style.color = '#f5f7ff';
          } else {
            const body = await response.json();
            statusEl.textContent = body.detail ?? 'Unable to send answer.';
            statusEl.style.color = '#f5f7ff';
          }
        } catch (error) {
          statusEl.textContent = 'Unable to send answer.';
          statusEl.style.color = '#f5f7ff';
        }
      }

      // Start polling immediately - MathJax will be available when needed
      console.log('QuizQt Student Page loaded, starting refresh cycle...');
      loadIdentity();
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
    name_assigner = NameAssigner.from_default_file()

    @app.get("/", response_class=HTMLResponse)
    def serve_student_page() -> str:
        return _STUDENT_PAGE_HTML

    @app.get("/identity")
    def get_identity(
        request: Request,
        response: Response,
        manager: QuizManager = Depends(quiz_manager_dep),
    ) -> dict[str, str]:
        alias = _ensure_alias(request, response, manager, name_assigner)
        return {"display_name": alias}

    @app.get("/question")
    def get_question(manager: QuizManager = Depends(quiz_manager_dep)) -> dict[str, object]:
        question = manager.get_current_question()
        active = manager.is_question_active()
        if question is None:
            return {"active": False, "question_html": None, "options": [], "correct_option_index": None}
        fragment = renderer.render_fragment(question.question_text)
        # Only send correct answer when question is not active (teacher has shown answer)
        correct_index = None if active else question.correct_option_index
        return {
            "active": active,
            "question_id": question.id,
            "question_html": fragment,
            "options": question.options,
            "correct_option_index": correct_index,
        }

    @app.post("/answer", status_code=201)
    def submit_answer(
      payload: AnswerPayload,
      request: Request,
      response: Response,
      manager: QuizManager = Depends(quiz_manager_dep),
    ) -> dict[str, object]:
        alias = _ensure_alias(request, response, manager, name_assigner)
        try:
            submission = manager.record_selected_option(
                payload.selected_option_index,
                display_name=alias,
            )
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
