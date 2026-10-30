#!/usr/bin/env python3
"""Build a markdown file of missed questions from a saved HamStudy.org practice test.

Usage:
    python3 missed_questions.py [input.mhtml] [output.md]

Defaults to the first .mhtml file in this folder and writes missed_questions.md.
Uses only the Python standard library.
"""
import email
import sys
from email import policy
from html.parser import HTMLParser
from pathlib import Path


def load_html(mhtml_path):
    """Return the main HTML page stored inside an .mhtml file."""
    with open(mhtml_path, "rb") as f:
        msg = email.message_from_binary_file(f, policy=policy.default)
    for part in msg.walk():
        if part.get_content_type() == "text/html":
            return part.get_payload(decode=True).decode("utf-8", errors="replace")
    raise ValueError(f"No HTML page found in {mhtml_path}")


class ExamParser(HTMLParser):
    """Collects each question's number, text, image, answers and which were correct/selected."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.questions = []
        self.current = None
        self.capture = None  # "number", "question", "answer_label", "answer_text"
        self.depth = 0  # div depth inside the element being captured
        self.answer = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        classes = (a.get("class") or "").split()

        if tag == "div" and "flashcard_container" in classes:
            qid = a.get("id", "").removeprefix("cont_")
            self.current = {"id": qid, "number": "", "text": "", "image": None, "answers": []}
            self.questions.append(self.current)
            return
        if self.current is None:
            return

        if tag == "img" and self.current["image"] is None and "/images/" in a.get("src", ""):
            self.current["image"] = a["src"]
        elif tag == "h2" and not self.current["number"]:
            self.capture = "number"
        elif tag == "div" and "question" in classes:
            self.capture, self.depth = "question", 0
        elif tag == "li" and "answer" in classes:
            self.answer = {
                "letter": "",
                "text": "",
                "correct": "correct" in classes,
                "selected": "selected" in classes,
            }
            self.current["answers"].append(self.answer)
        elif tag == "label" and self.answer is not None and not self.answer["letter"]:
            self.capture = "answer_label"
        elif tag == "div" and self.answer is not None and self.capture is None:
            self.capture, self.depth = "answer_text", 0
        elif tag == "div" and self.capture in ("question", "answer_text"):
            self.depth += 1
        elif tag in ("p", "br") and self.capture == "question":
            self.current["text"] += " "

    def handle_endtag(self, tag):
        if self.capture in ("number", "answer_label") and tag in ("h2", "label"):
            self.capture = None
        elif tag == "div" and self.capture in ("question", "answer_text"):
            if self.depth == 0:
                self.capture = None
            else:
                self.depth -= 1
        elif tag == "li":
            self.answer = None
        elif tag == "ul" and self.current is not None:
            self.answer = None

    def handle_data(self, data):
        if self.capture == "number":
            self.current["number"] += data
        elif self.capture == "question":
            self.current["text"] += data
        elif self.capture == "answer_label":
            self.answer["letter"] += data
        elif self.capture == "answer_text":
            self.answer["text"] += data


def clean(text):
    return " ".join(text.split())


def fmt(answer):
    return f"**{clean(answer['letter']).rstrip('.')}.** {clean(answer['text'])}"


def build_markdown(title, questions):
    missed = []
    for q in questions:
        correct = next((a for a in q["answers"] if a["correct"]), None)
        chosen = next((a for a in q["answers"] if a["selected"]), None)
        if correct is not None and chosen is not correct:
            missed.append((q, correct, chosen))

    answered = sum(1 for q in questions if any(a["selected"] for a in q["answers"]))
    lines = [
        f"# Missed Questions — {title}",
        "",
        f"Missed **{len(missed)}** of {len(questions)} questions "
        f"(score {len(questions) - len(missed)}/{len(questions)}, {answered} answered).",
        "",
    ]
    for q, correct, chosen in missed:
        lines += [
            "---",
            "",
            f"## {clean(q['number'])} — {q['id']}",
            "",
            clean(q["text"]),
            "",
        ]
        if q["image"]:
            lines += [f"![Figure]({q['image']})", ""]
        lines += [
            f"- ✅ **Correct answer:** {fmt(correct)}",
            f"- ❌ **You chose:** {fmt(chosen) if chosen else '_(no answer)_'}",
            "",
        ]
    return "\n".join(lines)


def main():
    here = Path(__file__).resolve().parent
    if len(sys.argv) > 1:
        src = Path(sys.argv[1])
    else:
        found = sorted(here.glob("*.mhtml"))
        if not found:
            sys.exit("No .mhtml file found; pass the path as an argument.")
        src = found[0]
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else here / "missed_questions.md"

    html = load_html(src)
    parser = ExamParser()
    parser.feed(html)
    questions = [q for q in parser.questions if q["answers"]]

    # Pool name from the <base href=".../practice/E4_2024">, e.g. "E4_2024".
    pool = ""
    marker = 'hamstudy.org/practice/'
    if marker in html:
        pool = html.split(marker, 1)[1].split('"', 1)[0].split("#", 1)[0]
    title = f"HamStudy {pool} Practice Exam" if pool else "HamStudy Practice Exam"

    out.write_text(build_markdown(title, questions), encoding="utf-8")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
