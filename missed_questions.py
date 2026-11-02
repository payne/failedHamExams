#!/usr/bin/env python3
"""Build one markdown file of missed questions from saved HamStudy.org practice exams.

Usage:
    python3 missed_questions.py [exam ...] [-o output.md]

Each exam can be a page saved from the "Review questions" screen as either
"Webpage, Single File" (.mhtml) or "Webpage, Complete" (.html).
With no exams given, every .mhtml and .html file in this folder is used,
oldest first. Missed questions are merged by question ID, so a question
missed on more than one exam appears once and lists every wrong answer.
Uses only the Python standard library.
"""
import argparse
import email
from email import policy
from html.parser import HTMLParser
from pathlib import Path


def load_html(path):
    """Return the main HTML page from a saved .html or .mhtml file."""
    path = Path(path)
    if path.suffix.lower() != ".mhtml":
        return path.read_text(encoding="utf-8", errors="replace")
    with open(path, "rb") as f:
        msg = email.message_from_binary_file(f, policy=policy.default)
    for part in msg.walk():
        if part.get_content_type() == "text/html":
            return part.get_payload(decode=True).decode("utf-8", errors="replace")
    raise ValueError(f"No HTML page found in {path}")


class ExamParser(HTMLParser):
    """Collects each question's number, text, image, answers and which were correct/selected."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.questions = []
        self.current = None
        self.capture = None  # "number", "question", "answer_label", "answer_text"
        self.depth = 0  # div depth inside the element being captured
        self.answer = None
        self.in_image = False  # inside a question's div.image (its figure)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        classes = (a.get("class") or "").split()

        if tag == "div" and "flashcard_container" in classes:
            qid = a.get("id", "").removeprefix("cont_")
            self.current = {"id": qid, "number": "", "text": "", "image": None, "answers": []}
            self.questions.append(self.current)
            self.in_image = False
            return
        if self.current is None:
            return

        if tag == "div" and "image" in classes:
            self.in_image = True
        elif tag == "div" and "flashcard" in classes:
            self.in_image = False
        elif tag == "img" and self.in_image and self.current["image"] is None:
            self.current["image"] = a.get("src")
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


def read_exam(path):
    """Parse one saved exam. Returns its pool name, questions and missed questions."""
    html = load_html(path)
    parser = ExamParser()
    parser.feed(html)
    questions = [q for q in parser.questions if q["answers"]]

    # Pool name from links like "hamstudy.org/practice/E4_2024#...".
    pool = ""
    marker = "hamstudy.org/practice/"
    if marker in html:
        pool = html.split(marker, 1)[1].split('"', 1)[0].split("#", 1)[0]

    missed = []
    for q in questions:
        # A "Webpage, Complete" save points figures at a local folder; link to HamStudy instead.
        if q["image"] and not q["image"].startswith("http") and pool:
            name = q["image"].replace("\\", "/").rsplit("/", 1)[-1]
            q["image"] = f"https://hamstudy.org/api/pools/{pool}/images/{name}"
        correct = next((a for a in q["answers"] if a["correct"]), None)
        chosen = next((a for a in q["answers"] if a["selected"]), None)
        if correct is not None and chosen is not correct:
            missed.append((q, correct, chosen))
    return {"path": Path(path), "pool": pool, "questions": questions, "missed": missed}


def build_markdown(exams):
    # Merge missed questions across exams by question ID.
    merged = {}
    for n, exam in enumerate(exams, 1):
        for q, correct, chosen in exam["missed"]:
            entry = merged.setdefault(q["id"], {"q": q, "correct": correct, "misses": []})
            entry["misses"].append((n, clean(q["number"]), chosen))

    # Questions missed most often first, then in question-pool order.
    ordered = sorted(merged.values(), key=lambda e: (-len(e["misses"]), e["q"]["id"]))
    repeats = sum(1 for e in ordered if len(e["misses"]) > 1)

    pools = sorted({e["pool"] for e in exams if e["pool"]})
    title = f"HamStudy {', '.join(pools)} Practice Exams" if pools else "HamStudy Practice Exams"
    lines = [f"# Missed Questions — {title}", "", "| Exam | File | Score | Missed |", "|---|---|---|---|"]
    for n, exam in enumerate(exams, 1):
        total, missed = len(exam["questions"]), len(exam["missed"])
        lines.append(f"| {n} | `{exam['path'].name}` | {total - missed}/{total} | {missed} |")
    lines += [
        "",
        f"**{len(ordered)}** different questions missed; "
        f"**{repeats}** missed on more than one exam (marked 🔁, listed first).",
        "",
    ]

    for e in ordered:
        q, misses = e["q"], e["misses"]
        repeat = f" 🔁 missed {len(misses)}×" if len(misses) > 1 else ""
        lines += ["---", "", f"## {q['id']}{repeat}", "", clean(q["text"]), ""]
        if q["image"]:
            lines += [f"![Figure]({q['image']})", ""]
        lines.append(f"- ✅ **Correct answer:** {fmt(e['correct'])}")
        for n, number, chosen in misses:
            lines.append(
                f"- ❌ **Exam {n}, question {number} — you chose:** "
                f"{fmt(chosen) if chosen else '_(no answer)_'}"
            )
        lines.append("")
    return "\n".join(lines)


def main():
    here = Path(__file__).resolve().parent
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("exams", nargs="*", type=Path, help="saved exam pages, in the order taken")
    ap.add_argument("-o", "--output", type=Path, default=here / "missed_questions.md")
    args = ap.parse_args()

    sources = args.exams or sorted(
        [p for p in here.iterdir() if p.suffix.lower() in (".mhtml", ".html")],
        key=lambda p: p.stat().st_mtime,
    )
    if not sources:
        ap.error("no .mhtml or .html exam files found; pass the paths as arguments")

    exams = [read_exam(p) for p in sources]
    exams = [e for e in exams if e["questions"]]  # skip pages with no questions (e.g. a results screen)
    if not exams:
        ap.error("none of the files contain exam questions")

    args.output.write_text(build_markdown(exams), encoding="utf-8")
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
