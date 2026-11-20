# Trigger test for the skill description

Seven requests. The three `fires-` cases must invoke one of this plugin's skills or commands, and
the four `quiet-` cases must not. The description is the only thing that decides, so this tests it.
A `quiet-` case only forbids this plugin's skills, so an unrelated built-in skill firing is not a
failure here.

```bash
uv run python evals/run_trigger.py --runs 2
```

That runs each request through `claude -p` in a clean session: project settings only, no MCP
servers, this plugin as the only extra source of skills. It calls a live model and costs money.
`last-run.json` records the last run: the model, the date, the pass count for every case and the
skills the session could see.

The cases also work with `claude plugin eval . --ablation none`, which runs in your own
environment with all your plugins loaded. `--ablation none` matters: in the default mode the
skill-fired grader is reported as an indicator and left out of the score.
