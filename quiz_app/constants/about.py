"""Static metadata describing QuizQt."""

APP_NAME = "QuizQt"
APP_VERSION = "0.1"
APP_AUTHOR = "Magnus Simonsen"
APP_AI = "GPT-5.1-Codex / Claude Sonnet"
APP_LICENSE = "MIT License"
APP_REPOSITORY_URL = "https://github.com/magnussimonsen/QuizQt"
APP_ABOUT_TEXT = (
    "QuizQt is an open-source classroom quiz facilitator built with Qt and FastAPI. "
    "Use it to add questions with LaTeX support, run live sessions, and let students join from the web."
)

HELP_TEXT = (
    "You can create or edit quizzes directly in the GUI, adding LaTeX-enabled questions one by one. "
    "Alternatively, author a .txt file (useful with AI tools) using the import format:\n\n"
    "Q: What is $30^o$ in radians?\n"
    "A: \\frac{\\pi}{2}\nB: \\frac{\\pi}{6}\nC: \\frac{\\pi}{2}\nD: \\frac{\\pi}{3}\n"
    "CORRECT: B\nTIMELIMIT: 15\n\n"
    "Q: What is $45^o$ in radians?\n"
    "A: \\frac{\\pi}{3}\nB: \\frac{\\pi}{6}\nC: \\frac{\\pi}{4}\nD: \\frac{3\\pi}{4}\n"
    "CORRECT: C\nTIMELIMIT: 15"
)
