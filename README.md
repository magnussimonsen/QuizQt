# QuizQt

Fast teacher console (Qt6) + student web page (FastAPI) for multiple-choice quizzes with Markdown/LaTeX support.

## Screenshots
![Teacher dashboard](screenshots/QuizQt-2025-11-20-1.png)
![Student page](screenshots/QuizQt-2025-11-20-2.png)
![Live scoreboard](screenshots/QuizQt-2025-11-20-3.png)

## Quick start
```bash
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
python app_main.py
```
The Qt app launches and hosts the student page at `http://<teacher-ip>:8000/`.

## Building (Linux)
PyInstaller packaging on Linux: from the repo root run

```bash
bash build/build_quizqt.sh
```

The helper script installs PyInstaller into the active virtual environment if needed and produces the bundle in `build/dist/QuizQt/`. Launch the resulting `build/dist/QuizQt/QuizQt` binary to run the packaged desktop app.

## Building (Windows)
Use PowerShell (pwsh or Windows PowerShell) from the repo root:

```powershell
pwsh quiz_app/build_quizqt.ps1
```

Prefer Cmd instead? Run:

```cmd
quiz_app\build_quizqt.bat
```

Both scripts look for `.venv\\Scripts\\python.exe` first (falling back to `py`/`python` on your PATH), install PyInstaller if it is missing, and write the packaged app to `quiz_app/dist/QuizQt/QuizQt.exe`.

## Quiz text format
Each question block in `quiz_questions.txt` looks like:
```
Q: Question text with $\LaTeX$
A: Option A
B: Option B
C: Option C
D: Option D
CORRECT: B
```
- `Q:` supports Markdown + inline or block LaTeX.
- Provide exactly four options A–D.
- `CORRECT:` is optional; omit it for ungraded questions.
