# Contributing

Issues and pull requests are welcome.

## Set up

You need [uv](https://docs.astral.sh/uv/) and `make`.

```bash
make setup
```

This installs the dependencies and the git hooks.

## Before you open a pull request

- Run `make check`. It runs the same checks as CI: lint, types, tests with coverage, and the evals.
- Add a test for what you changed.
- If your change moves a number the README quotes, run `make evals` and commit `evals/results/latest.json`. CI fails when a README figure and the measured result disagree.
- Keep writing plain and specific. A pre-commit hook rejects em dashes and a short list of marketing words.

## Reporting bugs

Use the bug report template. For security problems, see [SECURITY.md](SECURITY.md) instead of opening an issue.
