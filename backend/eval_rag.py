from app.api.deps import TEMP_USER_ID
from app.db.session import SessionLocal
from app.services.rag import answer_question

TESTS = [
    {"q": "What is tokenization?", "found": True},
    {"q": "What is a morpheme?", "found": True},
    {"q": "What are the two types of morphemes?", "found": True, "page": 16, "text": "affix"},
    {"q": "What is lemmatization?", "found": True, "page": 22, "text": "lemma"},
    {"q": "Explain CYK parsing", "found": True, "page": 38},
    {"q": "What is a transformer model?", "found": True},
    {"q": "How to remove white space or chars in python?", "found": True},
    {"q": "How do I strip whitespace from a string in Python?", "found": True},
    {"q": "write a program to count No. of digits", "found": True},
    {"q": "in CodingProblems.pdf how many programs are there?", "found": True, "text": "22"},
    {"q": "What is backpropagation?", "found": False},
    {"q": "Explain gradient descent", "found": False},
    {"q": "What is a convolutional neural network?", "found": False},
    {"q": "What is reinforcement learning?", "found": False},
    {"q": "Explain decision trees", "found": False},
    {"q": "Who invented the NLTK library?", "found": False},
    {"q": "How do I cook biryani?", "found": False},
    {"q": "What is the capital of France?", "found": False},
]

failures = 0
with SessionLocal() as db:
    for t in TESTS:
        a = answer_question(db, TEMP_USER_ID, t["q"])
        problems = []

        if a.found != t["found"]:
            problems.append(f"found={a.found}, wanted {t['found']}")
        if t.get("page") and a.found:
            pages = [c.page for c in a.citations]
            if t["page"] not in pages:
                problems.append(f"page {t['page']} not cited (cited {pages})")
        if t.get("text") and t["text"] not in a.answer.lower():
            problems.append(f"answer does not contain '{t['text']}'")

        failures += bool(problems)
        status = "OK   " if not problems else "WRONG"
        print(
            f"{status} | {a.mode:<14} | top={a.top_score:.3f} | "
            f"{a.reason:<17} | {t['q']}"
        )
        for p in problems:
            print(f"        -> {p}")

print(f"\nwrong: {failures} of {len(TESTS)}")