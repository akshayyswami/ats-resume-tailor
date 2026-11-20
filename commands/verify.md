---
description: Check a resume against your evidence file and report what it cannot back up
argument-hint: <resume.md> [evidence.yaml] [gap.md]
allowed-tools: Bash(ats-resume-tailor verify:*)
---

Check the annotated resume named in $ARGUMENTS with the ats-resume-tailor command.

1. The first argument is the resume. The second is the evidence file, `evidence.yaml` in the working folder if it is left out. The third, if given, is the gap file for the job.
2. Run `ats-resume-tailor verify <resume> -e <evidence>`, adding `-g <gap>` when there is a gap file.
3. Show the output. For each FAIL, name the rule and the line, and say how to fix the resume: reword the line so the cited fact supports it, cite the fact that does, or delete the line. Never clear a FAIL by editing the evidence file or the gap file.
4. List what was reported as NOT CHECKED, and say plainly that the tool checks evidence IDs, numbers and known terms, not whether each sentence restates its fact.

Exit code 1 means a rule failed. Exit code 2 means an input could not be used, so say which one.
