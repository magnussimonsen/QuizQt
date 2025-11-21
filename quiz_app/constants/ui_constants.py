"""Qt UI constants used across widgets."""

WINDOW_TITLE: str = "QuizQt Teacher Console"
PLACEHOLDER_QUESTION: str = "Enter your question text (supports Markdown + LaTeX)."
STUDENT_URL_PLACEHOLDER: str = "http://<teacher-ip>:8000/"
ANSWER_REFRESH_INTERVAL_MS: int = 1000

MODE_BUTTON_MAKE: str = "Make New Quiz"
MODE_BUTTON_IMPORT: str = "Import Quiz"
MODE_BUTTON_SAVE_FILE: str = "Save Quiz to File"
MODE_BUTTON_EDIT: str = "Edit Quiz"
MODE_BUTTON_START: str = "Start Quiz"
MODE_BUTTON_STOP: str = "End Quiz"

MODE1_INSERT_BUTTON: str = "Add New Question"
MODE1_SAVE_BUTTON: str = "Save Question"
MODE1_DELETE_BUTTON: str = "Delete Question"
MODE1_PREV_BUTTON: str = "Show Previous Question"
MODE1_NEXT_BUTTON: str = "Show Next Question"
MODE4_ACTION_BUTTON: str = "Start Quiz"
MODE4_DESCRIPTION: str = "Waiting room for students before the quiz begins."
MODE4_EMPTY_STATE: str = "No students have joined yet."
MODE4_READY_COUNT_TEMPLATE: str = "{count} student(s) ready"

IMPORT_BUTTON_TEXT: str = "Select quiz file"
IMPORT_DIALOG_TITLE: str = "Select quiz file"
IMPORT_FILE_FILTER: str = "Quiz files (*.txt);;All files (*.*)"
EXPORT_DIALOG_TITLE: str = "Save quiz to file"
EXPORT_FILE_FILTER: str = "Quiz files (*.txt);;All files (*.*)"

MODE3_SHOW_CORRECT: str = "Show Correct Answer"
MODE3_NEXT_QUESTION: str = "Next Question"

NO_QUIZ_LOADED_MESSAGE: str = "Please import or create a quiz first."
QUIZ_COMPLETE_MESSAGE: str = "You have reached the end of the quiz."
QUIZ_SAVED_MESSAGE: str = "Quiz saved and ready to run."
