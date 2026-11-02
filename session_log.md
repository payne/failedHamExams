# Session Log — Missed Ham Exam Questions

**Date:** 2026-10-29
**Folder:** `/home/mpayne/git/failedHamExams`

## Request

> Write a program, that from the file in this folder build a markdown file with each question I got wrong. The file should have the question, the correct answer and what I choose.

## What was in the folder

- `HamStudy.org_ Ham Radio Practice Test.mhtml`: a page from a HamStudy.org practice exam (pool `E4_2024`, Amateur Extra), saved from Chrome.
- `venv/`: a Python 3.11 virtual environment with no extra packages installed.

## How the saved page marks answers

The `.mhtml` file is a MIME archive. Its main HTML page is stored as quoted-printable text. In that HTML, each of the 50 questions is a `div.flashcard_container` that contains:

- `<h2>` with the question number (e.g. `9/50`)
- `div.question` with the question text
- `ul.answers` holding four `li.answer` items. Their classes show the result:
  - `answer correct selected perma_selected`: you chose it and it was right (30 questions)
  - `answer selected perma_selected`: you chose it and it was wrong (20 questions)
  - `answer correct`: the right answer on a question you missed (20 questions)
- An optional `div.image` holding a figure image (Figures E9-2 and E5-1)

## What was built

`missed_questions.py` uses only the Python standard library:

1. It reads the `.mhtml` file with the `email` module and pulls out the HTML page.
2. It parses the HTML with `html.parser`. For each question it collects the number, ID, text, figure image, and answers, plus which answer was correct and which one you selected.
3. It writes `missed_questions.md`. That file has a score summary, then one section for each missed question with the question, ✅ the correct answer, and ❌ the answer you chose. Questions with a diagram also get an image link.

### Usage

```
python3 missed_questions.py                         # first .mhtml in folder -> missed_questions.md
python3 missed_questions.py exam.mhtml output.md    # explicit input/output
```

### Result

The script ran without errors: **20 of 50 missed (score 30/50)**. This matches the count of wrong answers marked in the saved page. Both figure-based questions it missed include links to their images.

## Files

| File | Purpose |
|------|---------|
| `missed_questions.py` | The program |
| `missed_questions.md` | The generated list of missed questions |
| `session_log.md` | This file |

## Full source: `missed_questions.py`

```python
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
```

## Full output: missed questions

### Missed Questions — HamStudy E4_2024 Practice Exam

Missed **20** of 50 questions (score 30/50, 50 answered).

---

#### 9/50 — E6B08

Which of the following is a Schottky barrier diode?

- ✅ **Correct answer:** **A.** Metal-semiconductor junction
- ❌ **You chose:** **C.** PIN junction

---

#### 11/50 — E4D09

What is the purpose of the preselector in a communications receiver?

- ✅ **Correct answer:** **C.** To increase the rejection of signals outside the band being received
- ❌ **You chose:** **B.** To provide broadband attenuation before the first RF stage to prevent intermodulation

---

#### 13/50 — E6C04

Which of the following is an advantage of BiCMOS logic?

- ✅ **Correct answer:** **C.** It has the high input impedance of CMOS and the low output impedance of bipolar transistors
- ❌ **You chose:** **A.** Its simplicity results in much less expensive devices than standard CMOS

---

#### 15/50 — E9G11

In what units are the wavelength scales on a Smith chart calibrated?

- ✅ **Correct answer:** **B.** In fractions of transmission line electrical wavelength
- ❌ **You chose:** **D.** In fractions of antenna electrical frequency

---

#### 16/50 — E5A13

What is an effect of increasing Q in a series resonant circuit?

- ✅ **Correct answer:** **C.** Internal voltages increase
- ❌ **You chose:** **B.** Parasitic effects are minimized

---

#### 17/50 — E2B05

Which of the following describes the use of vestigial sideband in analog fast-scan TV transmissions?

- ✅ **Correct answer:** **C.** Vestigial sideband reduces the bandwidth while increasing the fidelity of low frequency video components
- ❌ **You chose:** **A.** The vestigial sideband carries the audio information

---

#### 24/50 — E9A09

What is antenna efficiency?

- ✅ **Correct answer:** **B.** Radiation resistance divided by total resistance
- ❌ **You chose:** **D.** Effective radiated power divided by transmitter output

---

#### 30/50 — E7C04

How does an impedance-matching circuit transform a complex impedance to a resistive impedance?

- ✅ **Correct answer:** **C.** It cancels the reactive part of the impedance and changes the resistive part to the desired value
- ❌ **You chose:** **D.** Reactive currents are dissipated in matched resistances

---

#### 31/50 — E6E01

Why is gallium arsenide (GaAs) useful for semiconductor devices operating at UHF and higher frequencies?

- ✅ **Correct answer:** **B.** Higher electron mobility
- ❌ **You chose:** **D.** Lower transconductance

---

#### 32/50 — E9B04

What is the front-to-back ratio of the radiation pattern shown in Figure E9-2?

![Figure](https://hamstudy.org/api/pools/E4_2024/images/E9-2.png)

- ✅ **Correct answer:** **B.** 28 dB
- ❌ **You chose:** **D.** 38 dB

---

#### 34/50 — E7B05

What can be done to prevent unwanted oscillations in an RF power amplifier?

- ✅ **Correct answer:** **C.** Install parasitic suppressors and/or neutralize the stage
- ❌ **You chose:** **D.** Use a phase inverter in the output filter

---

#### 36/50 — E7H07

How can an oscillator’s microphonic responses be reduced?

- ✅ **Correct answer:** **D.** Mechanically isolate the oscillator circuitry from its enclosure
- ❌ **You chose:** **A.** Use NP0 capacitors

---

#### 38/50 — E4B08

Which of the following can be used to determine the Q of a series-tuned circuit?

- ✅ **Correct answer:** **C.** The bandwidth of the circuit's frequency response
- ❌ **You chose:** **A.** The ratio of inductive reactance to capacitive reactance

---

#### 39/50 — E1C07

What notifications must be given before transmitting on the 630- or 2200-meter bands?

- ✅ **Correct answer:** **D.** Operators must inform the Utilities Technology Council (UTC) of their call sign and coordinates of the station
- ❌ **You chose:** **C.** Operators must inform the FAA of their intent to operate, giving their call sign and distance to the nearest runway

---

#### 40/50 — E5C12

Which point on Figure E5-1 best represents the impedance of a series circuit consisting of a 300-ohm resistor and a 19-picofarad capacitor at 21.200 MHz?

![Figure](https://hamstudy.org/api/pools/E4_2024/images/E5-1.png)

- ✅ **Correct answer:** **A.** Point 1
- ❌ **You chose:** **D.** Point 8

---

#### 42/50 — E6A05

How does DC input impedance at the gate of a field-effect transistor (FET) compare with that of a bipolar transistor?

- ✅ **Correct answer:** **C.** An FET has higher input impedance
- ❌ **You chose:** **B.** An FET has lower input impedance

---

#### 45/50 — E3A08

When a meteor strikes the Earth’s atmosphere, a linear ionized region is formed at what region of the ionosphere?

- ✅ **Correct answer:** **A.** The E region
- ❌ **You chose:** **C.** The F2 region

---

#### 47/50 — E3C05

What orientation of Bz (B sub z) increases the likelihood that charged particles from the Sun will cause disturbed conditions?

- ✅ **Correct answer:** **A.** Southward
- ❌ **You chose:** **B.** Northward

---

#### 49/50 — E5B07

What is the phase angle between the voltage across and the current through a series RLC circuit if XC is 500 ohms, R is 1 kilohm, and XL is 250 ohms?

- ✅ **Correct answer:** **C.** 14.0 degrees with the voltage lagging the current
- ❌ **You chose:** **A.** 68.2 degrees with the voltage leading the current

---

#### 50/50 — E2C06

During a VHF/UHF contest, in which band segment would you expect to find the highest level of SSB or CW activity?

- ✅ **Correct answer:** **C.** In the weak signal segment of the band, with most of the activity near the calling frequency
- ❌ **You chose:** **D.** In the middle of the band, usually 25 kHz above the national calling frequency

---

# Session 2 — Merging a second failed exam

**Date:** 2026-11-02

## Request

> I just put a new complete web page into this folder. It's the second failed exam. Merge all of the questions I got wrong here in with the previous results.

## What happened

- The first save of `HamStudy.org_ Ham Radio Practice Test.html` was only the "Exam Failed" results screen (score 31/50 and a chart of misses per section), with no questions. The user re-saved it from the "Review questions" screen.
- The re-saved page is "Webpage, Complete" (`.html` plus a `_files/` folder) and uses the same `flashcard_container` / `li.answer` markup as the first exam. Figures point at local copies (e.g. `./..._files/E5-1.png`).

## Script changes (`missed_questions.py`)

- Reads any number of exams, as `.mhtml` or `.html`. With no arguments it uses every `.mhtml`/`.html` file in the folder, oldest first. The output path is now `-o/--output`.
- Figures are read only from a question's `div.image`. Local figure paths are rewritten to `https://hamstudy.org/api/pools/<pool>/images/<name>` so the links work anywhere.
- Misses are merged by question ID. Each question appears once with the correct answer and one ❌ line per exam where it was missed. Questions missed more than once are marked 🔁 and listed first; the rest are in question-pool order.
- Pages with no questions (such as a results screen) are skipped.

## Result

| Exam | File | Score | Missed |
|---|---|---|---|
| 1 | `HamStudy.org_ Ham Radio Practice Test.mhtml` | 30/50 | 20 |
| 2 | `HamStudy.org_ Ham Radio Practice Test.html` | 31/50 | 19 |

38 different questions missed. Only E9A09 ("What is antenna efficiency?") was missed on both exams, with a different wrong answer each time.
