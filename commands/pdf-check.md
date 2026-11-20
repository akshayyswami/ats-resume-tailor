---
description: Check that a resume PDF gives its text back, in order, the way an ATS reads it
argument-hint: <resume.pdf> [resume.clean.md]
allowed-tools: Bash(ats-resume-tailor pdf-check:*)
---

Check the PDF named in $ARGUMENTS with the ats-resume-tailor command.

1. The first argument is the PDF. The second is the exported clean resume it was made from, `resume.clean.md` in the working folder if it is left out.
2. Run `ats-resume-tailor pdf-check <pdf> -s <source>`.
3. Show the output. Name each rule that failed and what it means: `no-extractable-text` and `text-in-images` mean text is locked in pictures or missing, `low-token-recall` means words are missing, `reading-order-broken` means the text comes back in the wrong order, usually from columns.
4. Say plainly that a pass means the text survives two readings of the file, not that any particular ATS parses it.

Exit code 1 means a rule failed. Exit code 2 means the PDF or the source could not be used, so say which one.
