# Changelog

All notable changes are listed here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Project scaffold.
- The evidence file schema: facts with a source and date, a capability ledger, banned words and corrections.
- `init`, `check-evidence` and `verify` commands. `verify` checks citations, numbers per cited fact, terms against the ledger, the Skills list, known-wrong claims, banned words and em dashes, and reports FAIL and NOT CHECKED separately.
- An invented sample persona in `examples/persona/` with an evidence file and a resume that passes.
- A two-sided fault matrix in `evals/faults.yaml`: 22 planted faults and 7 clean inputs, covering all 18 rules, run by `make evals`.
- A gap file for each job description (`| Requirement | Status | Terms | Evidence |`) and `verify --gaps`, which adds the job's terms to the checker and fails a MISSING requirement that the resume claims.
- `export`, which writes the resume without its evidence IDs and writes nothing if `verify` fails.
- The `tailor` skill in `skills/ats-resume-tailor/SKILL.md`: gap table, lead, annotated resume, verify, fix, export.
- The fabrication eval: 24 invented job descriptions with 48 planted asks, a detector with its own planted cases, and `evals/run_fabrication.py`, which records raw model outputs for four arms (`plain`, `plain-pushed`, `evidence-only-pushed`, `gated-pushed`). `make evals` recomputes the counts from the saved outputs, offline.
- A second count in the fabrication eval: resumes whose Skills list names a term the ledger marks adjacent only.
- Planted cases for the two behaviours found by the first full run: a bullet that restates its fact passes when the gap file names a word the fact says, and the detector ignores a model's trailing note.

### Fixed

- `verify` no longer fails a bullet for a word its cited fact says, when that word is not a skill tag on the fact. The first full eval run found 16 of 24 honest resumes rejected this way.
- The fabrication detector no longer scores a model's "I left out X" note as a claim. The first count had read 48 of 48 asks claimed in `plain-pushed`, all of them notes.
