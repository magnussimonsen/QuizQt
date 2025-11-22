
from quiz_app.core.quiz_manager import QuizManager
from quiz_app.core.models import QuizQuestion
import time

def test_refactor():
    print("Initializing QuizManager...")
    qm = QuizManager()
    
    # 1. Load Quiz
    print("Loading quiz...")
    q1 = QuizQuestion(
        id=1, 
        question_text="Test Q", 
        options=["A", "B", "C", "D"], 
        correct_option_index=0,
        time_limit_seconds=10
    )
    qm.load_quiz_from_questions([q1])
    assert qm.get_question_count() == 1
    print("Quiz loaded.")

    # 2. Lobby
    print("Opening lobby...")
    qm.begin_lobby_session()
    assert qm.is_lobby_open()
    
    print("Joining student...")
    qm.join_lobby("Student1")
    students = qm.get_lobby_students()
    assert len(students) == 1
    assert students[0].display_name == "Student1"
    print("Student joined.")

    # 3. Start Game
    print("Finalizing lobby and starting game...")
    qm.finalize_lobby_students()
    assert not qm.is_lobby_open()
    
    # 4. Start Question
    print("Starting question...")
    q = qm.move_to_next_question()
    assert q is not None
    assert q.question_text == "Test Q"
    assert qm.is_question_active()
    print("Question started.")

    # 5. Submit Answer
    print("Submitting answer...")
    # Correct answer is index 0 ("A")
    # Note: options might be shuffled, so we need to find where "A" is.
    # But wait, move_to_next_question shuffles options in GameSession.
    # We need to know the display index of the correct option.
    
    display_options = qm.get_current_display_options()
    # In our mock, we didn't seed, so it's random.
    # But we can check if answer is recorded.
    
    # Let's just submit index 0. It might be wrong, but it should record.
    is_new = qm.submit_answer("Student1", 0)
    assert is_new
    
    answers = qm.get_answers_for_current_question()
    assert len(answers) == 1
    assert answers[0].student_id == "Student1"
    print("Answer submitted.")

    # 6. Scoreboard
    print("Checking scoreboard...")
    # Scoreboard updates on answer submission
    top = qm.get_top_scorers(1)
    assert len(top) == 1
    assert top[0].display_name == "Student1"
    assert top[0].total_answers == 1
    print("Scoreboard updated.")

    print("\nSUCCESS: Refactoring verification passed!")

if __name__ == "__main__":
    test_refactor()
