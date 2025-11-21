"""FastAPI server that exposes student endpoints."""

from __future__ import annotations

from datetime import timezone
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
      .hidden { display: none; }
      .primary-button { border: none; border-radius: 0.75rem; padding: 0.85rem 1.5rem; font-size: 1rem; background: #1f9aa5; color: #fff; cursor: pointer; transition: transform 120ms ease, background 120ms ease; }
      .primary-button:hover { transform: translateY(-2px); background: #16808a; }
      .primary-button:disabled { opacity: 0.6; cursor: not-allowed; }
      #question-container { min-height: 6rem; font-size: 1.1rem; line-height: 1.6; }
      .options-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 0.75rem; }
      .option-button { border: none; border-radius: 0.75rem; padding: 1rem; font-size: 1rem; background: #1f9aa5; color: #fff; cursor: pointer; transition: transform 120ms ease, background 120ms ease; }
      .option-button:hover { transform: translateY(-2px); background: #16808a; }
      .option-button:disabled { opacity: 0.5; cursor: not-allowed; }
      #status { min-height: 1.25rem; }
      .student-name { margin-top: 0.25rem; color: #94a3b8; font-size: 0.95rem; }
      .join-status { margin-top: 0.5rem; font-size: 0.95rem; color: #94a3b8; }
      #timer-wrapper { display: flex; flex-direction: column; gap: 0.35rem; margin-bottom: 1rem; }
      #timer-wrapper.hidden { display: none; }
      #timer-label { font-size: 0.95rem; color: #facc15; }
      .timer-track { width: 100%; height: 0.6rem; background: rgba(250, 204, 21, 0.25); border-radius: 999px; overflow: hidden; }
      #timer-fill { width: 100%; height: 100%; background: #facc15; transform-origin: left center; transform: scaleX(0); transition: transform 120ms linear; }
    </style>
    <script>
      window.MathJax = { tex: { inlineMath: [['$','$']], displayMath: [['$$','$$']] }, svg: { fontCache: 'global' } };
    </script>
    <script defer src=\"https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js\"></script>
  </head>
  <body>
    <section class=\"card\" id=\"join-card\">
      <h1>QuizQt Lobby</h1>
      <p>Press the button when you are connected and ready.</p>
      <button id=\"join-button\" class=\"primary-button\">Join Quiz</button>
      <p id=\"join-status\" class=\"join-status\"></p>
    </section>
    <section class="card hidden" id="waiting-card">
      <h2>Waiting Room</h2>
      <p id="waiting-message">Waiting for the teacher to start the next question…</p>
      <p id="student-name" class="student-name"></p>
    </section>
    <section class="card hidden" id="quiz-card">
      <div id="question-container">Waiting for the teacher to start the next question…</div>
      <div id="timer-wrapper" class="hidden">
        <span id="timer-label"></span>
        <div class="timer-track">
          <div id="timer-fill"></div>
        </div>
      </div>
      <div id="options-container" class="options-grid"></div>
      <p id="status"></p>
    </section>
    <script>
      const questionContainer = document.getElementById('question-container');
      const optionsContainer = document.getElementById('options-container');
      const statusEl = document.getElementById('status');
      const studentNameEl = document.getElementById('student-name');
      const joinCard = document.getElementById('join-card');
      const waitingCard = document.getElementById('waiting-card');
      const quizCard = document.getElementById('quiz-card');
      const joinButton = document.getElementById('join-button');
      const joinStatus = document.getElementById('join-status');
      const waitingMessage = document.getElementById('waiting-message');
      const timerWrapper = document.getElementById('timer-wrapper');
      const timerLabel = document.getElementById('timer-label');
      const timerFill = document.getElementById('timer-fill');

      let currentQuestionId = null;
      let hasAnswered = false;
      let myAnswer = null;
      let displayName = null;
      let hasJoinedLobby = false;
      let lobbyGeneration = null;
      let joinedLobbyGeneration = null;
      let aliasGeneration = null;
      let pollHandle = null;
      let timerInterval = null;
      let timerDeadlineMs = null;
      let timerTotalMs = null;
      let timeExpiredForQuestion = false;

      function setVisibility(element, isVisible) {
        if (!element) return;
        if (isVisible) {
          element.classList.remove('hidden');
        } else {
          element.classList.add('hidden');
        }
      }

      function stopTimer(hide = true) {
        if (timerInterval) {
          clearInterval(timerInterval);
          timerInterval = null;
        }
        timerDeadlineMs = null;
        timerTotalMs = null;
        if (hide) {
          setVisibility(timerWrapper, false);
        }
        timerLabel.textContent = '';
        timerFill.style.transform = 'scaleX(0)';
      }

      function updateTimerDisplay() {
        if (!timerDeadlineMs || !timerTotalMs || !timerWrapper) {
          return;
        }
        const remainingMs = Math.max(0, timerDeadlineMs - Date.now());
        const fraction = timerTotalMs <= 0 ? 0 : Math.min(1, remainingMs / timerTotalMs);
        timerFill.style.transform = `scaleX(${fraction})`;
        if (remainingMs > 0) {
          const secondsLeft = Math.max(0, Math.ceil(remainingMs / 1000));
          timerLabel.textContent = `${secondsLeft}s remaining`;
        } else {
          timerLabel.textContent = 'Time limit reached';
          timerFill.style.transform = 'scaleX(0)';
          handleTimeExpired();
          stopTimer(false);
        }
      }

      function startTimer(deadlineMs, totalSeconds) {
        timerTotalMs = Math.max(1, totalSeconds * 1000);
        timerDeadlineMs = deadlineMs;
        setVisibility(timerWrapper, true);
        updateTimerDisplay();
        if (timerInterval) {
          clearInterval(timerInterval);
        }
        timerInterval = setInterval(updateTimerDisplay, 100);
      }

      function handleTimeExpired() {
        if (timeExpiredForQuestion) {
          return;
        }
        timeExpiredForQuestion = true;
        const buttons = optionsContainer.querySelectorAll('.option-button');
        buttons.forEach(btn => (btn.disabled = true));
        if (!hasAnswered) {
          statusEl.textContent = '⏱ Time is up – you can no longer submit an answer.';
          statusEl.style.color = '#facc15';
        }
      }

      async function loadIdentity() {
        try {
          const response = await fetch('/identity');
          const payload = await response.json();
          displayName = payload.display_name || null;
          if (typeof payload.alias_generation === 'number') {
            aliasGeneration = payload.alias_generation;
          }
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

      async function joinLobby() {
        joinButton.disabled = true;
        joinStatus.textContent = 'Contacting server…';
        try {
          const response = await fetch('/join', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({})
          });
          const body = await response.json().catch(() => ({}));
          if (!response.ok) {
            joinStatus.textContent = body.detail || 'Unable to join yet. Try again soon.';
            joinButton.disabled = false;
            return;
          }
          hasJoinedLobby = true;
          joinedLobbyGeneration = body.lobby_generation ?? lobbyGeneration;
          if (joinedLobbyGeneration != null) {
            lobbyGeneration = joinedLobbyGeneration;
          }
          await loadIdentity();
          joinStatus.textContent = '';
          setVisibility(joinCard, false);
          setVisibility(waitingCard, true);
          waitingMessage.textContent = 'Waiting for the teacher to start the next question…';
        } catch (error) {
          console.error('Error joining lobby:', error);
          joinStatus.textContent = 'Unable to reach the server. Check your connection and try again.';
          joinButton.disabled = false;
        }
      }

      joinButton.addEventListener('click', joinLobby);

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
          button.disabled = !active || hasAnswered || timeExpiredForQuestion;
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

          if (typeof payload.lobby_generation !== 'undefined') {
            lobbyGeneration = payload.lobby_generation;
          }
          if (typeof payload.alias_generation === 'number') {
            const incomingAliasGeneration = payload.alias_generation;
            if (aliasGeneration === null) {
              aliasGeneration = incomingAliasGeneration;
            } else if (aliasGeneration !== incomingAliasGeneration) {
              aliasGeneration = incomingAliasGeneration;
              await loadIdentity();
            }
          }
          const lobbyOpen = Boolean(payload.lobby_open);
          const joinedCurrentLobby = hasJoinedLobby && joinedLobbyGeneration === lobbyGeneration && lobbyGeneration !== null;

          if (lobbyOpen && !joinedCurrentLobby) {
            hasJoinedLobby = false;
            joinedLobbyGeneration = null;
            joinStatus.textContent = 'New quiz starting. Tap Join to participate.';
            joinButton.disabled = false;
            setVisibility(joinCard, true);
            setVisibility(waitingCard, false);
            setVisibility(quizCard, false);
            stopTimer();
            timeExpiredForQuestion = false;
            return;
          }

          if (!joinedCurrentLobby) {
            setVisibility(joinCard, false);
            setVisibility(quizCard, false);
            setVisibility(waitingCard, true);
            waitingMessage.textContent = lobbyOpen
              ? 'Waiting for the teacher to start the next question…'
              : 'Waiting for the teacher to open the lobby…';
            questionContainer.textContent = 'Waiting for the teacher to start the next question…';
            renderOptions([], false);
            statusEl.textContent = '';
            stopTimer();
            timeExpiredForQuestion = false;
            return;
          }

          if (payload.active) {
            setVisibility(waitingCard, false);
            setVisibility(quizCard, true);
            // Only update if question has changed
            if (payload.question_id !== currentQuestionId) {
              console.log('New question detected, updating display');
              currentQuestionId = payload.question_id;
              hasAnswered = false; // Reset answer flag for new question
              myAnswer = null; // Reset stored answer
              timeExpiredForQuestion = false;
              stopTimer();
              // Display question HTML (or placeholder if empty)
              questionContainer.innerHTML = payload.question_html || '<p><em>(No question text)</em></p>';
              const options = Array.isArray(payload.options) ? payload.options : [];
              renderOptions(options, true);
              statusEl.textContent = '';
              statusEl.style.color = '#f5f7ff';
              // Typeset math with retry logic
              typesetMath();
            }
            const timerEligible = (
              typeof payload.time_limit_seconds === 'number' &&
              payload.time_limit_seconds > 0 &&
              payload.question_started_at
            );
            if (timerEligible) {
              const startedMs = Date.parse(payload.question_started_at);
              if (!Number.isNaN(startedMs)) {
                startTimer(startedMs + payload.time_limit_seconds * 1000, payload.time_limit_seconds);
              } else {
                stopTimer();
              }
            } else {
              stopTimer();
              if (timeExpiredForQuestion) {
                timeExpiredForQuestion = false;
                renderOptions(Array.isArray(payload.options) ? payload.options : [], true);
              }
            }
          } else {
            setVisibility(waitingCard, true);
            waitingMessage.textContent = 'Waiting for the teacher to start the next question…';
            stopTimer();

            if (payload.question_id === null) {
              setVisibility(quizCard, false);
              if (currentQuestionId !== null) {
                console.log('Question not active or no question');
                currentQuestionId = null;
                hasAnswered = false;
                myAnswer = null;
                timeExpiredForQuestion = false;
              }
              questionContainer.textContent = 'Waiting for the teacher to start the next question…';
              renderOptions([], false);
              if (!hasAnswered) {
                statusEl.textContent = '';
              }
            } else {
              setVisibility(quizCard, true);
              const options = Array.isArray(payload.options) ? payload.options : [];
              renderOptions(options, false);
            }

            if (payload.correct_option_index !== null && myAnswer !== null && hasAnswered) {
              if (myAnswer === payload.correct_option_index) {
                statusEl.textContent = '✓ Correct!';
                statusEl.style.color = '#4ade80';
              } else {
                statusEl.textContent = '✗ Sorry, wrong answer. Correct answer: ' + String.fromCharCode(65 + payload.correct_option_index);
                statusEl.style.color = '#f87171';
              }
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
        if (timeExpiredForQuestion) {
          statusEl.textContent = '⏱ Time is up – you can no longer submit an answer.';
          statusEl.style.color = '#facc15';
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
            if (body.detail && body.detail.toLowerCase().includes('time limit')) {
              handleTimeExpired();
            }
          }
        } catch (error) {
          statusEl.textContent = 'Unable to send answer.';
          statusEl.style.color = '#f5f7ff';
        }
      }

      console.log('QuizQt Student Page loaded. Waiting for the lobby join.');
      loadIdentity();
      refreshQuestion();
      pollHandle = setInterval(refreshQuestion, 2000);
    </script>
  </body>
</html>
"""


class AnswerPayload(BaseModel):
    """Payload schema for submitted answers."""

    selected_option_index: int


class JoinPayload(BaseModel):
    """Payload schema for the lobby join flow."""

    display_name: str | None = None


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
    ) -> dict[str, object]:
        alias = _ensure_alias(request, response, manager, name_assigner)
        return {
            "display_name": alias,
            "alias_generation": manager.get_alias_generation(),
        }

    @app.get("/question")
    def get_question(manager: QuizManager = Depends(quiz_manager_dep)) -> dict[str, object]:
        question = manager.get_current_question()
        active = manager.is_question_active()
        lobby_open = manager.lobby_is_open()
        lobby_generation = manager.get_lobby_generation()
        quiz_started = manager.has_quiz_session_started()
        alias_generation = manager.get_alias_generation()
        display_options = manager.get_current_display_options()
        start_time = manager.get_current_question_start_time()
        start_iso = None
        if start_time is not None:
          if start_time.tzinfo is None:
            start_iso = start_time.replace(tzinfo=timezone.utc).isoformat()
          else:
            start_iso = start_time.astimezone(timezone.utc).isoformat()
        if question is None:
            return {
                "active": False,
                "question_id": None,
                "question_html": None,
            "options": display_options,
                "correct_option_index": None,
                "lobby_open": lobby_open,
                "lobby_generation": lobby_generation,
                "quiz_started": quiz_started,
                "alias_generation": alias_generation,
            "time_limit_seconds": None,
            "question_started_at": start_iso,
            }
        fragment = renderer.render_fragment(question.question_text)
        # Only send correct answer when question is not active (teacher has shown answer)
        correct_index = None if active else manager.get_current_display_correct_index()
        return {
            "active": active,
            "question_id": question.id,
            "question_html": fragment,
          "options": display_options,
            "correct_option_index": correct_index,
            "lobby_open": lobby_open,
            "lobby_generation": lobby_generation,
            "quiz_started": quiz_started,
            "alias_generation": alias_generation,
          "time_limit_seconds": question.time_limit_seconds,
          "question_started_at": start_iso,
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

    @app.post("/join", status_code=201)
    def join_lobby(
        payload: JoinPayload,
        request: Request,
        response: Response,
        manager: QuizManager = Depends(quiz_manager_dep),
    ) -> dict[str, object]:
        alias = _ensure_alias(request, response, manager, name_assigner)
        chosen_name = alias
        if payload.display_name:
            stripped = payload.display_name.strip()
            if stripped:
                chosen_name = stripped
        try:
            joined = manager.register_lobby_student(chosen_name)
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {
            "student_id": joined.student_id,
            "display_name": joined.display_name,
            "joined_at": joined.joined_at.isoformat(),
          "lobby_generation": manager.get_lobby_generation(),
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
