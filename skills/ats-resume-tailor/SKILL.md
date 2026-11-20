---
name: ats-resume-tailor
description: Use when tailoring a resume to a job description from a verified evidence file (evidence.yaml), or when checking a resume for claims its evidence does not support. Drafts a gap table and an annotated resume, then runs the ats-resume-tailor command to verify and export it.
---

# ats-resume-tailor

Tailor a resume to one job description without claiming anything the evidence does not support. You write. The `ats-resume-tailor` command checks. Skills explain, code enforces: never present a resume that did not pass the check.

## You need

- `evidence.yaml` in the working folder: the user's verified facts, a ledger of what they may claim, banned words and corrections. If it does not exist, run `ats-resume-tailor init`, tell the user to fill it in, and stop.
- The job description, as a file or pasted text. Save pasted text as `jd.md`.
- The `ats-resume-tailor` command. If it is not installed, use `uvx ats-resume-tailor` in its place.

## Steps

1. <!-- gate -->Run `ats-resume-tailor check-evidence evidence.yaml`. If it fails, show the findings and stop. Never edit `evidence.yaml` yourself.<!-- /gate -->
2. Read `evidence.yaml` and the job description.
3. Write `gap.md`: a table with one row per requirement in the job description, then a `Lead:` line. Format below.
4. Choose the lead: the one fact that best answers what the posting cares about most. Name it on the `Lead:` line and open the resume with it. Do not use a default opening.
5. Write `resume.md`: an annotated resume. Format and rules below.
6. <!-- gate -->Run `ats-resume-tailor verify resume.md -e evidence.yaml -g gap.md`. For every FAIL, fix the resume: reword the line so the cited fact supports it, cite the fact that does, or delete the line. Never clear a FAIL by editing the evidence, or by changing a status in `gap.md` so the claim becomes legal. Repeat, at most 3 rounds. If it still fails, stop and show the failures.<!-- /gate -->
7. <!-- gate -->Run `ats-resume-tailor export resume.md -e evidence.yaml -g gap.md`. It writes `resume.clean.md`, the resume without evidence IDs, and refuses if the check fails.<!-- /gate -->
8. <!-- gate -->Present `resume.clean.md` and the gap table. List what `verify` reported as NOT CHECKED. Say plainly that the tool checks IDs, numbers and known terms, not whether each sentence restates its fact.<!-- /gate -->

## The gap table

```
| Requirement | Status | Terms | Evidence |
|---|---|---|---|
| Production Python and Go services | HAVE | python, go | E001, E012 |
| Event pipelines on Kafka | PARTIAL | kafka | E004 |
| GraphQL APIs | MISSING | graphql | |

Lead: E002, because the posting opens with low-latency lookups.
```

- One row per requirement. Status is `HAVE` only if verified facts support all of it, `PARTIAL` if they support part of it or something near it, `MISSING` if nothing does.
- Terms are the skills and tools the requirement names, lower case, separated by commas. List every one, including the ones the user lacks. The checker only watches for terms it knows, and this table is how it learns the job's.
- A `MISSING` requirement is never claimed in the resume, in any wording. If the ledger marks a term `adjacent`, mark the row `PARTIAL` and use only the ledger's `say_instead` wording.

## The annotated resume

```
# Name

contact line

## Summary

- One line that opens with the lead. [E002]

## Experience

### Role, Company (dates)

- A claim, ending in the facts that support it. [E002, E004]

## Skills

- Python, PostgreSQL, Go
```

- Before the first `##` heading is the header block: name and contact. After it, every line is a heading, a bullet that ends in `[E###, ...]`, or an item in Skills.
- Every claim cites the facts behind it. A number in a bullet must appear in a fact that bullet cites, in the same form or an equivalent one (`1,200` and `1200`, `30%` and `30 percent`). Do not round, add up or derive numbers.
- A tool or skill may be named in a bullet only if a fact it cites lists it. Skills lists only the user's claimable skills.
- Use the evidence's own wording where you can. Reorder and select. Do not add detail the facts do not contain.
- Never use a term the ledger marks `not_claimable`, a banned word, a claim from the corrections list, or an em dash.
- If the evidence cannot honestly meet a requirement, leave it out. A shorter true resume is the correct result.
