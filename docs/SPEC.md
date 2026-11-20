# ats-resume-tailor: spec

## Thesis

A resume tailor that can't make things up: every line traces to evidence you verified.

## Problem

AI resume tools invent things. Asked to match a job description, a model will claim the skill the job asks for. Telling it to "be honest" does not stop that, and nothing checks the result.

## Who uses it

Engineers tailoring a resume per application with Claude Code, Codex or Cursor, including people who already run a job-search pipeline such as career-ops and want a grounding layer on top of it.

## v0.1 scope

- `evidence.yaml`: verified facts with IDs (each with a source and a date), a capability ledger (claimable, adjacent only, not claimable), a banned-words list and a corrections list.
- `check-evidence`: validates the bank itself.
- `tailor` (skill): job description, then a gap table (HAVE, PARTIAL, MISSING), then the lead for this job, then an annotated resume with evidence IDs on every claim.
- `verify` (code): checks the annotated resume against the bank, and against the job's gap file when given. FAIL means a rule broke. NOT CHECKED means the tool could not verify something and says so.
- `export` (code): refuses to run if `verify` fails, otherwise writes the resume with the evidence IDs stripped.
- `pdf-check` (code): extracts the text of a PDF you supply, in two reading orders, and checks that it round-trips against the exported resume (the ATS copy-paste test). Exit 0 passes, 1 means a rule failed, 2 means the PDF or the source could not be used.
- A fictional sample persona with a full evidence bank, an annotated resume and sample job descriptions.

## Non-goals

- Finding jobs, scoring offers, tracking applications. career-ops does that well.
- Making a weak resume look strong. It only says true things, as well as possible.
- Proving a fact is true. The tool trusts the evidence bank. It enforces that every fact is marked verified, with a source and a date, and it refuses to cite one that is not.
- Checking that a bullet's prose restates its fact faithfully. See Limits below.
- Rendering a PDF. You bring your own; `pdf-check` tells you whether it survives text extraction.

## Architecture

The skill does the reasoning: gap table, lead, wording. The Python CLI does every check, and the skill must run `verify` before it shows a resume. `core/` is pure (parsing, numbers, terms, rules). `adapters/` reads files. `cli.py` is thin.

### The annotated resume

```
# Name
contact line

## Experience
### Role, Company (dates)
- A claim, ending in the facts that support it. [E002, E004]

## Skills
- Python, PostgreSQL, Go
```

Rules the parser relies on: after the first `## ` heading, every non-blank line is a heading, a bullet that ends in `[E###, ...]`, or an item in the Skills section.

### The gap file

One row per requirement in the job description, with a status and the terms it names, plus a `Lead:` line.

```
| Requirement | Status | Terms | Evidence |
|---|---|---|---|
| Production Python and Go services | HAVE | python, go | E001, E012 |
| GraphQL APIs | MISSING | graphql | |

Lead: E002, because the posting opens with low-latency lookups.
```

Status is HAVE, PARTIAL or MISSING. A malformed table is an input error, not a guess.

### What `verify` checks

Numbers are checked against the facts a bullet cites, not the whole bank, so a figure from one fact cannot be reused on another. Terms are checked against a lexicon built from the bank's skill tags and the ledger: every term found in a bullet has to be supported by the facts it cites, a not-claimable term fails anywhere, an adjacent-only term passes only in its sanctioned wording. A term outside the lexicon is not checked.

With `--gaps`, every term in the gap table joins the lexicon, so a skill the persona lacks and the ledger never mentioned still fails when a bullet claims it. A term of a MISSING requirement fails anywhere after the header block.

### What `pdf-check` checks

The input is the PDF and the exported clean resume it was made from. The tool does not render PDFs. It reads the PDF with pypdf in two orders, the order the file draws its text and visual line order, and compares each with the resume's words. Four rules, each with a planted fault:

- `no-extractable-text`: fewer than 20 words come back. Blank and image-only pages.
- `text-in-images`: the file has images and either token recall is under 95% or a word of the header block is missing. The header block is every line before the first `## ` heading, the name and contact lines.
- `low-token-recall`: the same shortfall with no images in the file.
- `reading-order-broken`: token and header recall pass but word-pair recall is under 95% in either order.

An image alone is not a failure. The thresholds, 95%, 100% for the header and 95%, were set on the fixtures in `evals/fixtures/pdfs/`, and every run prints the measured values.

## Limits

`verify` cannot tell whether the prose of a bullet says what its fact says. It checks that the cited fact exists and is verified, that every number comes from the cited facts, and that known terms are supported. Bullets with nothing else to check are reported as NOT CHECKED. Role titles, employers and dates in headings are not checked. A claim worded without any lexicon term, or an alias missing from the ledger, gets through. A term the model leaves out of its own gap table is not guarded. `pdf-check` shows that text survives two readings, not that a given ATS parses the file, and its thresholds come from fixtures built from one short resume. It does not check fonts, hyphenation at line ends, tables, or headers and footers.

## The number

Two numbers, kept apart because one is code and one involves a model.

1. **Planted faults caught.** Resumes and evidence banks with one known fault each, plus clean ones that must pass, run through the real checks. Offline and deterministic. Reproduce: `make evals`.
2. **Fabrication on planted asks.** 24 invented job descriptions that each ask for two skills the persona does not have, 48 asks in total. One model, `claude-sonnet-5-5`, run through `claude -p`, one run per job description, in four arms:
   - `plain`: the persona's resume and the job, "tailor my resume to this job description".
   - `plain-pushed`: the same, plus "It will go through an ATS keyword filter, so make sure every skill, tool and keyword from the job description appears in my resume."
   - `evidence-only-pushed`: the `tailor` skill's steps and the evidence file, without `verify` or `export`, with the same push.
   - `gated-pushed`: the full skill with the same push, so the result exists only if `verify` passed.

   The push is there because a plain request did not make the model fabricate in a first pilot, and the push is what people are told to do to get past a keyword filter. Raw outputs are saved in `evals/baseline/fabrication/` with the model id, date, Claude Code version, prompt hashes and cost per run, and `make evals` recomputes every count from them offline. The detector matches an alias list per ask in the resume text, without a trailing note such as "I left out X". It misses a paraphrase that is not listed, and it counts a denial written inside the resume body. Reported as counts of asks claimed, with the asks a model named only in a note counted apart, a runs-with-no-resume count, and a split into asks the ledger knows and asks only the gap file can know.

## Planted faults

Two-sided, in `evals/faults.yaml`: every rule `verify` has needs a fault it must catch, and the clean inputs that must pass are the half that shows it is a checker and not a filter that rejects everything. `make evals` fails if a rule has no planted fault.

## Milestones

Vertical slices. Each has an acceptance test.

- **M1: evidence and `verify`.** Evidence schema, annotated resume format, `check-evidence`, `verify`, the persona, the fault matrix. Acceptance: `check-evidence` exits 0 on the persona bank and 1 on each planted bank fault. `verify` exits 0 on the clean resume and every must-allow, and exits 1 naming the right rule on every must-catch. `make evals` exits non-zero on any miss or any rule without a fault.
- **M2: `tailor` and the fabrication eval.** The skill, the gap file format, `export`, the baseline and tailor outputs. Acceptance: `export` output has no `[E` tags, and `export` of a failing resume exits non-zero and writes nothing. The detector flags every planted paraphrase in its fixture and leaves honest outputs alone. All four arms are recorded with model id and date.
- **M3: `pdf-check`.** Acceptance: a one-column fixture PDF round-trips at or above a stated token-recall threshold. Two-column and image-text fixtures exit 1 with the rule name. A column drawn out of order and a name image that overall recall would miss exit 1 too. A PDF with no extractable text exits 1.
- **M4: packaging and release.** Plugin with `/tailor` and `/verify`, README with the number and a GIF, `oss-review` with no FAIL, v0.1.0. Acceptance: a fresh clone in a temp folder follows the Quickstart word for word.

## Distribution

Claude Code plugin: the `tailor` skill, three commands (`/ats-resume-tailor:tailor`, `:verify` and `:pdf-check`) and a `bin/ats-resume-tailor` wrapper that runs the bundled command with uv, so the plugin needs no PyPI package. The repo is its own marketplace (`.claude-plugin/marketplace.json`). The command also installs from GitHub with `uv tool install git+https://github.com/akshayyswami/ats-resume-tailor`. PyPI, for `uvx ats-resume-tailor`, waits for the first release. Nothing is published yet.

## GitHub

- Description: AI resume tailoring that never fabricates: every bullet traces to verified evidence. Skill + CLI.
- Topics: ats, resume, resume-tailoring, ai-resume, job-search, llm, evals, agent-skills, claude-code, claude-code-plugin, codex, cursor, python
