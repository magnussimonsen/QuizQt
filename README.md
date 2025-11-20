# QuizQt

Prototype Qt6 + FastAPI classroom quiz system with Markdown/LaTeX rendering,
multiple-choice questions, and a built-in student web page.

## Running locally

```bash
python -m venv .venv
.venv\Scripts\activate  # or source .venv/bin/activate on Linux
pip install -r requirements.txt
python app_main.py
```

The teacher UI launches and automatically starts the embedded FastAPI server
for students at `http://<teacher-ip>:8000/`.

## Quiz import format

Use the **Import new quiz** button to load a `.txt` file containing blocks such
as:

```
Q: What is $2 + 2$?
A: 3
B: 4
C: 5
D: 22
CORRECT: B

---
Q: Evaluate $\int_0^1 x^2 dx$
A: 1/2
B: 1/3
C: 1/4
D: 1/5
CORRECT: B
```

- `Q:` supports Markdown with inline (`$...$`) and block (`$$...$$`) LaTeX.
- Exactly four options (A–D) are required per question.
- `CORRECT:` is optional for now; leave it out if answers are ungraded.
