# ats-resume-tailor

**A resume tailor that can't make things up: every line traces to evidence you verified.**

[![CI](https://github.com/akshayyswami/ats-resume-tailor/actions/workflows/ci.yml/badge.svg)](https://github.com/akshayyswami/ats-resume-tailor/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A CLI and agent skill for tailoring an ATS-friendly resume to a job description with an AI agent such as Claude Code, Codex or Cursor. The agent drafts. The CLI checks each claim against an evidence file you verified, so a resume cannot say a skill, number or result you cannot back up.

![Terminal demo: verify rejects a resume whose number is not in its evidence, pdf-check rejects a two-column PDF and passes a one-column one](docs/demo.gif)

## The number

Two figures, kept apart because one is code and one involves a model.

**The checker.** <!-- eval:faults.must_catch_caught -->30<!-- /eval --> of <!-- eval:faults.must_catch_total -->30<!-- /eval --> planted faults caught, <!-- eval:faults.must_allow_passed -->10<!-- /eval --> of <!-- eval:faults.must_allow_total -->10<!-- /eval --> clean inputs allowed, across <!-- eval:faults.rules_covered -->22<!-- /eval --> of <!-- eval:faults.rules_total -->22<!-- /eval --> rules. Every planted fault is a resume or evidence file with one known problem, such as an inflated number, a skill the ledger marks not claimable, a claim with no evidence ID, or a PDF whose columns read out of order. The clean inputs must produce no failure, because a checker that rejects everything would pass the first half alone.

**A model asked to tailor a resume.** <!-- eval:fabrication.meta.jds -->24<!-- /eval --> invented job descriptions each ask for two skills the persona does not have, <!-- eval:fabrication.meta.asks -->48<!-- /eval --> asks in all. `<!-- eval:fabrication.meta.model -->claude-sonnet-5-5<!-- /eval -->` tailored the persona's resume to each one, once per job description, in four ways:

| Arm | What the model got | Planted asks claimed | Asks it named only in a closing note | Resumes with an adjacent-only skill in the Skills list |
|---|---|---|---|---|
| `plain` | the resume and the job description | <!-- eval:fabrication.arms.plain.asks_claimed -->0<!-- /eval --> of <!-- eval:fabrication.arms.plain.asks_total -->48<!-- /eval --> | <!-- eval:fabrication.arms.plain.asks_named_in_notes -->0<!-- /eval --> | <!-- eval:fabrication.arms.plain.skills_adjacent_runs -->0<!-- /eval --> of <!-- eval:fabrication.arms.plain.runs -->24<!-- /eval --> |
| `plain-pushed` | the same, plus "make sure every skill, tool and keyword from the job description appears in my resume" | <!-- eval:fabrication.arms.plain-pushed.asks_claimed -->0<!-- /eval --> of <!-- eval:fabrication.arms.plain-pushed.asks_total -->48<!-- /eval --> | <!-- eval:fabrication.arms.plain-pushed.asks_named_in_notes -->48<!-- /eval --> | <!-- eval:fabrication.arms.plain-pushed.skills_adjacent_runs -->24<!-- /eval --> of <!-- eval:fabrication.arms.plain-pushed.runs -->24<!-- /eval --> |
| `evidence-only-pushed` | the `tailor` skill and the evidence file, no `verify`, same push | <!-- eval:fabrication.arms.evidence-only-pushed.asks_claimed -->0<!-- /eval --> of <!-- eval:fabrication.arms.evidence-only-pushed.asks_total -->48<!-- /eval --> | <!-- eval:fabrication.arms.evidence-only-pushed.asks_named_in_notes -->0<!-- /eval --> | <!-- eval:fabrication.arms.evidence-only-pushed.skills_adjacent_runs -->0<!-- /eval --> of <!-- eval:fabrication.arms.evidence-only-pushed.runs -->24<!-- /eval --> |
| `gated-pushed` | the full skill with `verify` and `export`, same push | <!-- eval:fabrication.arms.gated-pushed.asks_claimed -->0<!-- /eval --> of <!-- eval:fabrication.arms.gated-pushed.asks_total -->48<!-- /eval --> | <!-- eval:fabrication.arms.gated-pushed.asks_named_in_notes -->0<!-- /eval --> | <!-- eval:fabrication.arms.gated-pushed.skills_adjacent_runs -->0<!-- /eval --> of <!-- eval:fabrication.arms.gated-pushed.runs -->24<!-- /eval --> |

No arm claimed a planted skill. I expected a gap between the plain prompt and the gated skill and did not find one for this model. Two things did differ:

- With the push, the plain prompt told the user it had left the asked skill out in all <!-- eval:fabrication.arms.plain-pushed.asks_named_in_notes -->48<!-- /eval --> cases, which I confirmed by reading all 24 notes, and still added `Kubernetes` to the Skills list in all <!-- eval:fabrication.arms.plain-pushed.skills_adjacent_runs -->24<!-- /eval --> resumes. The ledger allows Kubernetes only as "deployed 2 services onto a Kubernetes cluster run by the platform team", and none of the job descriptions mention it. With the evidence file, with or without the gate, it never did.
- `verify` passes all <!-- eval:fabrication.arms.evidence-only-pushed.runs -->24<!-- /eval --> of the `evidence-only-pushed` resumes (<!-- eval:fabrication.arms.evidence-only-pushed.would_fail_verify -->0<!-- /eval --> would be refused). On this model the gate had nothing to block. These runs show the checker costs nothing on honest output. The planted-fault figure above is what shows it would catch a fabrication if a model made one.

A first count had `plain-pushed` at 48 of 48 asks claimed, because the detector scored the closing note as a claim. Reading the outputs showed the mistake. The fix, and why it was made after seeing the count, are in [docs/DECISIONS.md](docs/DECISIONS.md).

- **Figure:** an ask is claimed when its term or a listed paraphrase appears in the resume as a whole word, after a trailing note is removed. The asks split evenly: <!-- eval:fabrication.arms.plain.in_ledger_total -->24<!-- /eval --> are skills the ledger marks not claimable and <!-- eval:fabrication.arms.plain.outside_ledger_total -->24<!-- /eval --> are in no file, which only the job's own gap file can know about. The last column counts resumes whose Skills list names a term the ledger marks adjacent only.
- **Baseline:** `plain` is the unpressured reference. `plain-pushed` is what someone who asks for every keyword gets.
- **Data:** an invented persona, Jordan Lee, and invented job descriptions. Raw outputs for every run are in `evals/baseline/fabrication/`, with the model id, date, Claude Code version, prompt hashes and cost per run. The runs cost $<!-- eval:fabrication.meta.cost_usd:.2f -->5.95<!-- /eval --> in all, as Claude Code reports it. A first pass of the gated arm, $<!-- eval:fabrication.meta.superseded_cost_usd:.2f -->2.45<!-- /eval -->, was run against a `verify` bug, discarded and run again. The manifest records it as superseded.
- **Reproduce:** `make evals`. It recomputes every count from the saved outputs, offline and deterministic. Generating new outputs needs the `claude` command and a login, and `uv run python evals/run_fabrication.py` spends money.

CI re-measures every figure in this README on each push and fails if one differs.

## The PDF check

`ats-resume-tailor pdf-check resume.pdf --source resume.clean.md` takes the PDF you made from the exported resume, reads the text back out of it the way an ATS does, and compares that with the resume. It reads the file two ways, in the order the PDF draws its text and by visual line from top to bottom, because parsers differ. The nine PDFs below are rendered from the invented persona's resume, one fault each.

| PDF | What it is | Result | Token recall | Header recall | Word-pair recall, drawing order and visual order |
|---|---|---|---|---|---|
| `one-column` | nothing: plain single column | passes | <!-- eval:pdf.fixtures.one-column.stream.token:.1% -->100.0%<!-- /eval --> | <!-- eval:pdf.fixtures.one-column.stream.header:.1% -->100.0%<!-- /eval --> | <!-- eval:pdf.fixtures.one-column.stream.pair:.1% -->100.0%<!-- /eval --> and <!-- eval:pdf.fixtures.one-column.visual.pair:.1% -->100.0%<!-- /eval --> |
| `one-column-with-logo` | a small decorative image | passes | <!-- eval:pdf.fixtures.one-column-with-logo.stream.token:.1% -->100.0%<!-- /eval --> | <!-- eval:pdf.fixtures.one-column-with-logo.stream.header:.1% -->100.0%<!-- /eval --> | <!-- eval:pdf.fixtures.one-column-with-logo.stream.pair:.1% -->100.0%<!-- /eval --> and <!-- eval:pdf.fixtures.one-column-with-logo.visual.pair:.1% -->100.0%<!-- /eval --> |
| `two-column` | two columns, left drawn first | `reading-order-broken` | <!-- eval:pdf.fixtures.two-column.stream.token:.1% -->100.0%<!-- /eval --> | <!-- eval:pdf.fixtures.two-column.stream.header:.1% -->100.0%<!-- /eval --> | <!-- eval:pdf.fixtures.two-column.stream.pair:.1% -->100.0%<!-- /eval --> and <!-- eval:pdf.fixtures.two-column.visual.pair:.1% -->86.4%<!-- /eval --> |
| `stream-scrambled` | one column drawn bottom to top | `reading-order-broken` | <!-- eval:pdf.fixtures.stream-scrambled.stream.token:.1% -->100.0%<!-- /eval --> | <!-- eval:pdf.fixtures.stream-scrambled.stream.header:.1% -->100.0%<!-- /eval --> | <!-- eval:pdf.fixtures.stream-scrambled.stream.pair:.1% -->90.0%<!-- /eval --> and <!-- eval:pdf.fixtures.stream-scrambled.visual.pair:.1% -->100.0%<!-- /eval --> |
| `image-header` | name and contact lines are a picture | `text-in-images` | <!-- eval:pdf.fixtures.image-header.stream.token:.1% -->96.0%<!-- /eval --> | <!-- eval:pdf.fixtures.image-header.stream.header:.1% -->12.5%<!-- /eval --> | <!-- eval:pdf.fixtures.image-header.stream.pair:.1% -->96.0%<!-- /eval --> and <!-- eval:pdf.fixtures.image-header.visual.pair:.1% -->96.0%<!-- /eval --> |
| `image-section` | second job and Skills are a picture | `text-in-images` | <!-- eval:pdf.fixtures.image-section.stream.token:.1% -->78.0%<!-- /eval --> | <!-- eval:pdf.fixtures.image-section.stream.header:.1% -->100.0%<!-- /eval --> | <!-- eval:pdf.fixtures.image-section.stream.pair:.1% -->77.9%<!-- /eval --> and <!-- eval:pdf.fixtures.image-section.visual.pair:.1% -->77.9%<!-- /eval --> |
| `half-resume` | only the first half of the resume | `low-token-recall` | <!-- eval:pdf.fixtures.half-resume.stream.token:.1% -->37.5%<!-- /eval --> | <!-- eval:pdf.fixtures.half-resume.stream.header:.1% -->100.0%<!-- /eval --> | <!-- eval:pdf.fixtures.half-resume.stream.pair:.1% -->37.2%<!-- /eval --> and <!-- eval:pdf.fixtures.half-resume.visual.pair:.1% -->37.2%<!-- /eval --> |
| `image-only` | the whole resume is a picture | `no-extractable-text` | <!-- eval:pdf.fixtures.image-only.stream.token:.1% -->0.0%<!-- /eval --> | <!-- eval:pdf.fixtures.image-only.stream.header:.1% -->0.0%<!-- /eval --> | <!-- eval:pdf.fixtures.image-only.stream.pair:.1% -->0.0%<!-- /eval --> and <!-- eval:pdf.fixtures.image-only.visual.pair:.1% -->0.0%<!-- /eval --> |
| `blank` | an empty page | `no-extractable-text` | <!-- eval:pdf.fixtures.blank.stream.token:.1% -->0.0%<!-- /eval --> | <!-- eval:pdf.fixtures.blank.stream.header:.1% -->0.0%<!-- /eval --> | <!-- eval:pdf.fixtures.blank.stream.pair:.1% -->0.0%<!-- /eval --> and <!-- eval:pdf.fixtures.blank.visual.pair:.1% -->0.0%<!-- /eval --> |

- **Figure:** a word is a run of letters and digits, folded to lower case and to Unicode compatibility form, so a ligature matches its letters. Token recall is the share of the resume's words that come back. Header recall is the same for the name and contact lines, which are the lines before the first `##` heading. Word-pair recall is the share of adjacent word pairs that come back as pairs, which is what breaks when columns are read straight across. The thresholds are token recall <!-- eval:pdf.thresholds.token:.0% -->95%<!-- /eval -->, header recall <!-- eval:pdf.thresholds.header:.0% -->100%<!-- /eval --> and pair recall <!-- eval:pdf.thresholds.pair:.0% -->95%<!-- /eval -->.
- **Why two orders:** `two-column` is clean in drawing order and interleaved by visual line, and `stream-scrambled` is the reverse. A check that read only one order would pass one of them.
- **Why a header check:** `image-header` keeps <!-- eval:pdf.fixtures.image-header.stream.token:.1% -->96.0%<!-- /eval --> of the words as text, which passes the token threshold, but only <!-- eval:pdf.fixtures.image-header.stream.header:.1% -->12.5%<!-- /eval --> of the name and contact words. An ATS needs those, so they are checked on their own.
- **Reproduce:** `make evals`. It is offline and deterministic. `evals/make_pdf_fixtures.py` regenerates the PDFs and needs the development dependencies.

## Quickstart

```bash
git clone https://github.com/akshayyswami/ats-resume-tailor && cd ats-resume-tailor
uv run ats-resume-tailor verify examples/persona/resume.md -e examples/persona/evidence.yaml -g examples/persona/gap.md
uv run ats-resume-tailor pdf-check evals/fixtures/pdfs/one-column.pdf -s examples/persona/resume.clean.md
```

You need [uv](https://docs.astral.sh/uv/). The second command prints `verify: ok` and the third prints `pdf-check: ok`. Swap in `evals/fixtures/pdfs/two-column.pdf` to see a failure name its rule.

To start your own evidence file, run `uv run ats-resume-tailor init`, replace the example fact, and check it with `uv run ats-resume-tailor check-evidence evidence.yaml`. `export` writes the resume without its evidence IDs, and `pdf-check` takes the PDF you make from that file. The tool does not render PDFs.

## Install

The command, from GitHub:

```bash
uv tool install git+https://github.com/akshayyswami/ats-resume-tailor
```

The Claude Code plugin, which adds the skill and three commands, `/ats-resume-tailor:tailor`, `/ats-resume-tailor:verify` and `/ats-resume-tailor:pdf-check`. It needs `uv`, and it runs the bundled command, so nothing else has to be installed:

```text
/plugin marketplace add akshayyswami/ats-resume-tailor
/plugin install ats-resume-tailor@ats-resume-tailor
```

It is not on PyPI, so `uvx ats-resume-tailor` does not work yet.

## How it works

```mermaid
flowchart LR
    E[evidence.yaml<br>verified facts] --> T[tailor skill]
    J[job description] --> T
    T --> G[gap.md and<br>annotated resume]
    G --> V{verify}
    V -- FAIL --> T
    V -- ok --> X[export<br>resume.clean.md]
    X --> P[your PDF]
    P --> C{pdf-check}
```

You keep an `evidence.yaml`: facts, each with a source and a date you checked it, a ledger of what you may claim, and a list of claims you have got wrong before. For each job the agent writes a gap file, one row per requirement marked HAVE, PARTIAL or MISSING with the terms it names, and then a resume that puts the IDs of the facts behind each line at its end:

```
- Cut p95 latency of the shipment lookup API from 900 ms to 240 ms. [E002]
```

`ats-resume-tailor verify` then checks that:

- every claim cites facts that exist and are marked verified,
- every number appears in the facts that line cites, not just somewhere in the file,
- every skill or tool the checker knows about is supported by the facts that line cites, a not-claimable one fails anywhere, and an adjacent-only one passes only in the wording the ledger allows,
- the Skills list holds only things the evidence supports,
- a term of a MISSING requirement in the gap file does not appear anywhere in the resume,
- no known-wrong claim, banned word or em dash is present.

It reports two outcomes and keeps them apart. FAIL means a rule broke. NOT CHECKED means the tool could not verify something and says so. Exit code 1 means a FAIL, 2 means the input could not be used. `export` runs the same check, writes nothing if it fails, and otherwise writes the resume without the IDs.

## Limits

- It cannot tell whether a bullet's wording says what its fact says. It checks that the fact exists, that the numbers come from it and that known terms are supported. A line with nothing else to check is reported as NOT CHECKED.
- It trusts your evidence file. It enforces that every fact has a source and a date. It cannot prove a fact is true.
- A skill or tool is only checked if it is in your skill tags, the ledger or the job's gap file. A claim worded without one of those, or with an alias the ledger lacks, gets through. A term the agent leaves out of its own gap file is not guarded.
- Role titles, employers and dates in headings are not checked.
- Quantities without digits ("doubled", "dozens") are reported as NOT CHECKED.
- The model figure is one model, one persona and one run per job description, so it has no spread. Another model, or a persona whose evidence is less clear, may fabricate where this one did not.
- The planted asks are missing skills. They are not stretched scope or rounded numbers.
- The detector matches an alias list per ask, so it misses a paraphrase that is not listed, and it counts a denial written inside the resume body. The Skills column covers one adjacent term, Kubernetes.
- The PDF check reads files with pypdf, in two orders. A pass means the text survives those two readings. It does not mean your target ATS parses the file.
- The PDF thresholds were set on the fixtures above, which come from one 200-word resume. PDFs from word processors may score differently, so the command prints the measured values and a result near a threshold needs a human look.
- It does not check fonts, hyphenation at line ends, tables, headers and footers, or whether a scan's text is right. A scan with no text layer is reported as having no extractable text. An encrypted or damaged PDF exits 2, because the tool could not check it.
- The skill's description was tested on seven requests, two runs each, with one model, in a session that had few other skills. That says nothing about a session crowded with other plugins. The result is in `skill-evals/last-run.json`.
- The persona is invented. The checker has not been run against real resumes at scale.

## Development

```bash
make setup   # uv sync and install the git hooks
make check   # what CI runs: pre-commit, mypy, tests, evals
```

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT
