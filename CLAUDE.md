# ats-resume-tailor: notes for Claude Code

Thesis: A resume tailor that can't make things up: every line traces to evidence you verified.

Read first: `docs/SPEC.md` for scope and milestones.

## House rules (same in every repo)

1. Evals before features. The number in `docs/SPEC.md` must be measurable from the first milestone, even if it starts out bad.
2. Every figure in the README comes from a script in `evals/` and CI re-measures it on every push. No estimated numbers.
3. Ship planted faults: known-bad inputs the tool must catch, run in CI.
4. Fail closed. When the tool can't verify something it says "not checked". It never guesses.
5. One milestone per session. End each session with tests green and a `CHANGELOG.md` entry.
6. Use plan mode before changing architecture. Record decisions in `docs/DECISIONS.md` (date, decision, why, alternatives).
7. No company code, data, client names or screenshots. Public or fabricated sample data only.
8. Writing: plain and specific. No em dashes, no marketing words.
9. Run `/security-review` before tagging a release.
10. Python 3.12+, uv, ruff, mypy strict, pytest, src layout, `core/` free of I/O. Follow the oss-kit skills (oss-new-repo, oss-evals, oss-docs, oss-release, oss-review).
11. Finish every session with `make check` green.
12. No AI attribution in commits or PRs: no `Co-Authored-By`, no `Claude-Session`, no "Generated with Claude Code".

## Current milestone

M1 to M4 are done: the checker, the `tailor` skill, `export`, the gap file, the fabrication eval, `pdf-check`, and the plugin with its demo and trigger test. v0.1.0 is the first release. Publishing to PyPI, and any later tag or publish, needs Akshay's go. See `docs/SPEC.md`.
