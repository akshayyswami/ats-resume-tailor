"""The starter evidence bank that `init` writes. It fails `check-evidence` as written, on purpose.

Its one fact is a placeholder. A bank that passed untouched would let a resume cite a fact that
nobody verified, so the checks refuse the template's text and source until they are replaced.
"""

from __future__ import annotations

from typing import Final

# Both strings appear in EVIDENCE_TEMPLATE, and the checks look for them.
# A test keeps the two in step.
PLACEHOLDER_TEXT: Final = "EXAMPLE, replace me"
PLACEHOLDER_SOURCE: Final = "where you can prove it"

EVIDENCE_TEMPLATE = """\
# Your evidence bank. ats-resume-tailor trusts what is in this file, so put only things you can
# back up. Every fact needs a source and a date: what proves it, and when you checked.

persona: Your Name

facts:
  # kind is one of: role, metric, project, skill.
  # A metric needs a number in its text. skills are tags the checker matches against bullets.
  - id: E001
    kind: metric
    text: EXAMPLE, replace me. Cut the nightly report from 4 hours to 35 minutes.
    skills: [python]
    verified:
      source: where you can prove it (a review, a repo, a manager who would confirm)
      date: 2026-01-01

# What you may claim. status is one of:
#   claimable      you have done it, and a verified fact lists it as a skill
#   adjacent       you did something near it; the resume may only use the say_instead wording,
#                  and only when it cites one of the supported_by facts
#   not_claimable  never write it
ledger:
  - term: python
    status: claimable
  - term: rust
    status: not_claimable

# Extra words you never want on your resume, on top of the built-in list.
banned_words: []

# Claims you have made before that were wrong. A resume that repeats one fails.
corrections: []
"""
