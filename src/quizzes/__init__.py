# ==========================================================
# Quiz (MCQ) generation feature — backend only.
#
# Pure Python. Reuses the existing RAG building blocks
# (retrieval agent, grounding-style validation, LLM factory)
# without touching the stable chat pipeline.
#
#   src/quizzes/models.py       data model + status constants
#   src/quizzes/retrieval.py    quiz context retrieval
#   src/quizzes/generation.py   subject-agnostic MCQ generation
#   src/quizzes/validation.py   structural + grounding + dedup checks
#   src/quizzes/lifecycle.py    create/start/submit + authoritative scoring
# ==========================================================
