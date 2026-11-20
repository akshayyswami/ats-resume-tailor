# Changelog

All notable changes are listed here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Project scaffold.
- The evidence file schema: facts with a source and date, a capability ledger, banned words and corrections.
- `init`, `check-evidence` and `verify` commands. `verify` checks citations, numbers per cited fact, terms against the ledger, the Skills list, known-wrong claims, banned words and em dashes, and reports FAIL and NOT CHECKED separately.
- An invented sample persona in `examples/persona/` with an evidence file and a resume that passes.
- A two-sided fault matrix in `evals/faults.yaml`: 20 planted faults and 6 clean inputs, covering all 17 rules, run by `make evals`.
