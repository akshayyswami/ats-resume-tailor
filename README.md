# ats-resume-tailor

**A resume tailor that can't make things up: every line traces to evidence you verified.**

[![CI](https://github.com/akshayyswami/ats-resume-tailor/actions/workflows/ci.yml/badge.svg)](https://github.com/akshayyswami/ats-resume-tailor/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A CLI and agent skill for tailoring an ATS-friendly resume to a job description with an AI agent such as Claude Code, Codex or Cursor. The agent drafts. The CLI checks each claim against an evidence file you verified, so a resume cannot say a skill, number or result you cannot back up.

> Status: pre-alpha, milestone 1 of 4. The evidence file format and the checker work. The `tailor` skill, the fabrication comparison and the PDF check are not built yet. See [docs/SPEC.md](docs/SPEC.md).

## The number

Not the headline yet. The fabrication comparison against a plain "tailor my resume" prompt arrives with milestone 2. What is measured today is the checker itself: <!-- eval:faults.must_catch_caught -->20<!-- /eval --> of <!-- eval:faults.must_catch_total -->20<!-- /eval --> planted faults caught, and <!-- eval:faults.must_allow_passed -->6<!-- /eval --> of <!-- eval:faults.must_allow_total -->6<!-- /eval --> clean inputs allowed, across <!-- eval:faults.rules_covered -->17<!-- /eval --> of <!-- eval:faults.rules_total -->17<!-- /eval --> rules.

- **Figure:** every planted fault is a resume or evidence file with one known problem, such as an inflated number, a skill the ledger marks not claimable, or a claim with no evidence ID. The checker must report the rule that names it. The clean inputs must produce no failure, because a checker that rejects everything would pass the first half alone.
- **Baseline:** none for this figure. It is a regression bar, not a comparison.
- **Data:** an invented persona, Jordan Lee, in `examples/persona/`. Every name, employer and number is fictional.
- **Reproduce:** `make evals`. It is offline and deterministic, and `make evals` fails if a rule has no planted fault.

CI re-measures every figure in this README on each push and fails if one differs.

## Demo

A terminal recording goes here once the `tailor` skill exists.

## Quickstart

```bash
git clone https://github.com/akshayyswami/ats-resume-tailor && cd ats-resume-tailor
uv sync
uv run ats-resume-tailor verify examples/persona/resume.md --evidence examples/persona/evidence.yaml
```

You need [uv](https://docs.astral.sh/uv/). The last command prints `verify: ok`. Not on PyPI yet.

To start your own evidence file, run `uv run ats-resume-tailor init`, replace the example fact, and check it with `uv run ats-resume-tailor check-evidence evidence.yaml`.

## How it works

You keep an `evidence.yaml`: facts, each with a source and a date you checked it, a ledger of what you may claim, and a list of claims you have got wrong before. A resume written for the checker puts the IDs of the facts behind each line at its end:

```
- Cut p95 latency of the shipment lookup API from 900 ms to 240 ms. [E002]
```

`ats-resume-tailor verify` then checks that:

- every claim cites facts that exist and are marked verified,
- every number appears in the facts that line cites, not just somewhere in the file,
- every skill or tool the checker knows about is supported by those facts, a not-claimable one fails anywhere, and an adjacent-only one passes only in the wording the ledger allows,
- the Skills list holds only things the evidence supports,
- no known-wrong claim, banned word or em dash is present.

It reports two outcomes and keeps them apart. FAIL means a rule broke. NOT CHECKED means the tool could not verify something and says so. Exit code 1 means a FAIL, 2 means the input could not be used.

## Limits

- It cannot tell whether a bullet's wording says what its fact says. It checks that the fact exists, that the numbers come from it and that known terms are supported. A line with nothing else to check is reported as NOT CHECKED.
- It trusts your evidence file. It enforces that every fact has a source and a date. It cannot prove a fact is true.
- A skill or tool is only checked if it is in your skill tags or ledger. A claim worded without one of those, or with an alias the ledger lacks, gets through.
- Role titles, employers and dates in headings are not checked.
- Quantities without digits ("doubled", "dozens") are reported as NOT CHECKED.
- The synthetic persona is one profile. The checker has not been run against real resumes at scale.

## Development

```bash
make setup   # uv sync and install the git hooks
make check   # what CI runs: pre-commit, mypy, tests, evals
```

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT
